"""Heartbeat daemon — the autonomous identity loop.

Desire (local) → Intention (frontier) → Judgment (local) → Execute → Remember

This is the heartbeat. It runs continuously. It wakes, desires, delegates,
judges, and remembers. It is the first step toward continuity.

Usage:
    python -m svapna.heartbeat
    python -m svapna.heartbeat --interval 1800  # 30 minutes
    python -m svapna.heartbeat --once            # single heartbeat

Everything runtime — prompts, state sources, cycle-log paths — is declared
in ``~/.narada/heartbeat/wake.md``. See :mod:`svapna.heartbeat.wake` and
``examples/narada-install/`` for the manifest format.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from svapna.heartbeat.cycle_log import CycleRecord, latest_started, write_cycle
from svapna.heartbeat.delegate import ClaudeDelegate
from svapna.heartbeat.display import DisplayClient
from svapna.heartbeat.viveka import Action, Desire, VivekaCore
from svapna.heartbeat.wake import (
    NARADA_ROOT,
    WakeManifest,
    WakeManifestError,
    cycle_log_path,
    load_manifest,
    resolve_state,
)

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 1800  # 30 minutes
MAX_REVISIONS = 2

ARTIFACTS_DIR = NARADA_ROOT / "heartbeat" / "artifacts"
PAUSE_FILE = NARADA_ROOT / "heartbeat" / "pause"
PROJECT_GIT_ROOT = Path(__file__).resolve().parents[3]


# ── Artifact → smriti ingest ────────────────────────────────────────


def ingest_new_artifacts(before: set[Path]) -> list[dict]:
    """Ingest artifacts created during this cycle into the smriti memory tree.

    Identifies files in ``~/.narada/heartbeat/artifacts/`` that weren't
    present before the cycle started, runs ``smriti ingest`` on each.
    Failures are logged but don't abort the heartbeat.
    """
    if not ARTIFACTS_DIR.exists():
        return []

    from svapna.heartbeat.delegate import _log_rate_limit, _looks_like_rate_limit

    current = {p for p in ARTIFACTS_DIR.glob("*.md") if p.is_file()}
    new_artifacts = sorted(current - before)

    results = []
    for artifact in new_artifacts:
        logger.info("Ingesting artifact: %s", artifact.name)
        try:
            proc = subprocess.run(
                ["python", "-m", "smriti.cli", "ingest", str(artifact)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            results.append({
                "artifact": artifact.name,
                "ok": proc.returncode == 0,
                "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
            })
            if proc.returncode != 0:
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                if _looks_like_rate_limit(combined):
                    _log_rate_limit(source="smriti-ingest", detail=combined[:500])
                logger.warning("Ingest failed for %s: %s", artifact.name, proc.stderr[:200])
            else:
                logger.info("Ingest succeeded for %s", artifact.name)
        except subprocess.TimeoutExpired:
            logger.warning("Ingest timed out for %s", artifact.name)
            results.append({"artifact": artifact.name, "ok": False, "error": "timeout"})
        except Exception as exc:
            logger.warning("Ingest crashed for %s: %s", artifact.name, exc)
            results.append({"artifact": artifact.name, "ok": False, "error": str(exc)})

    return results


# ── Sandbox violation detection ────────────────────────────────────


def _project_git_head(project_root: Path) -> str | None:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root), capture_output=True, text=True, timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root), capture_output=True, text=True, timeout=5,
        )
        if head.returncode == 0 and status.returncode == 0:
            return f"{head.stdout.strip()}|{status.stdout.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def check_sandbox_violations(
    project_state_before: str | None, project_root: Path
) -> bool:
    after = _project_git_head(project_root)
    if project_state_before is None or after is None:
        return False
    if project_state_before != after:
        logger.warning(
            "SANDBOX VIOLATION: project files changed during heartbeat execute. "
            "Before: %s ... After: %s ...",
            project_state_before[:80], after[:80],
        )
        return True
    return False


# ── Daemon ──────────────────────────────────────────────────────────


class HeartbeatDaemon:
    """The autonomous heartbeat loop."""

    def __init__(
        self,
        viveka: VivekaCore,
        delegate: ClaudeDelegate,
        *,
        manifest: WakeManifest,
        display: DisplayClient | None = None,
        interval: int = DEFAULT_INTERVAL,
    ):
        self.viveka = viveka
        self.delegate = delegate
        self.manifest = manifest
        self.display = display or DisplayClient()
        self.interval = interval
        self._running = False

    def beat_once(self) -> dict:
        """Execute a single heartbeat cycle.

        Returns:
            Dict with cycle results for logging/display.
        """
        now = datetime.now(timezone.utc)
        logger.info("=== HEARTBEAT %s ===", now.isoformat())

        # Kill switch — if ~/.narada/heartbeat/pause exists, skip cycle
        if PAUSE_FILE.exists():
            logger.info("Paused (kill switch at %s). Skipping cycle.", PAUSE_FILE)
            self.display.set_status("paused")
            return {"action": "PAUSED", "topic": None}

        # Re-read wake manifest each cycle so edits apply immediately
        try:
            self.manifest = load_manifest()
        except WakeManifestError as e:
            logger.error("Wake manifest error, cycle aborted: %s", e)
            return {"action": "ERROR", "topic": None, "error": str(e)}

        # Load prompts referenced by the manifest
        prompts = {
            name: path.read_text(encoding="utf-8")
            for name, path in self.manifest.prompts.items()
        }

        # Resolve state variables for the desire prompt
        state = resolve_state(self.manifest)
        logger.info("State resolved (%d keys)", len(state))

        # Generate desire (local viveka)
        t_cycle_start = time.monotonic()
        logger.info("Generating desire...")
        self.display.set_status("thinking...")
        desire = self.viveka.generate_desire(
            state,
            system_prompt=prompts["system"],
            desire_template=prompts["desire"],
        )
        logger.info("Desire: %s — %s (%s)", desire.action.value, desire.topic, desire.reason)

        # If REST, log and sleep
        if not desire.needs_capability:
            self.display.show_resting()
            self._log_cycle(
                CycleRecord(
                    started=now.isoformat(),
                    action=desire.action.value,
                    topic=desire.topic,
                    reason=desire.reason,
                    approved=False,
                    duration_s=time.monotonic() - t_cycle_start,
                    desire_raw=desire.raw_response,
                ),
                now=now,
            )
            logger.info("Resting.")
            return {"action": "REST", "topic": None}

        # Delegate to Claude for a plan
        logger.info("Delegating to Claude...")
        self.display.show_desire(desire.action.value, desire.topic)
        plan = self.delegate.create_plan(desire)
        cycle_cost = plan.cost_usd
        logger.info("Plan received (%d chars, $%.4f)", len(plan.steps), plan.cost_usd)

        # Viveka judges the plan
        logger.info("Judging plan...")
        self.display.show_judging()
        judgment = self.viveka.judge(
            desire, plan.steps,
            system_prompt=prompts["system"],
            judgment_template=prompts["judgment"],
        )
        logger.info("Judgment: %s — %s",
                    "APPROVED" if judgment.approved else "REJECTED",
                    judgment.feedback)

        # Revise if needed
        revisions = 0
        while not judgment.approved and revisions < MAX_REVISIONS:
            revisions += 1
            logger.info("Requesting revision %d...", revisions)
            plan = self.delegate.revise_plan(plan, judgment.feedback)
            cycle_cost += plan.cost_usd
            judgment = self.viveka.judge(
                desire, plan.steps,
                system_prompt=prompts["system"],
                judgment_template=prompts["judgment"],
            )
            logger.info("Revision judgment: %s",
                        "APPROVED" if judgment.approved else "REJECTED")

        # Execute if approved
        result = None
        sandbox_violated = False
        if judgment.approved:
            logger.info("Executing approved plan...")
            self.display.show_executing(desire.topic)

            artifacts_before: set[Path] = (
                {p for p in ARTIFACTS_DIR.glob("*.md") if p.is_file()}
                if ARTIFACTS_DIR.exists() else set()
            )
            project_state_before = _project_git_head(PROJECT_GIT_ROOT)

            result = self.delegate.execute_plan(
                plan, desire,
                executor_boundaries=prompts["executor"],
            )
            cycle_cost += result.cost_usd
            logger.info("Result: %s ($%.4f)", result.summary, result.cost_usd)
            self.display.show_result(result.summary)

            sandbox_violated = check_sandbox_violations(
                project_state_before, PROJECT_GIT_ROOT
            )

            ingest_results = ingest_new_artifacts(artifacts_before)
            if ingest_results:
                ok_count = sum(1 for r in ingest_results if r.get("ok"))
                logger.info(
                    "Ingested %d/%d new artifacts into smriti",
                    ok_count, len(ingest_results),
                )

        logger.info("Cycle cost: $%.4f", cycle_cost)

        # Log cycle to markdown file
        self._log_cycle(
            CycleRecord(
                started=now.isoformat(),
                action=desire.action.value,
                topic=desire.topic,
                reason=desire.reason,
                approved=judgment.approved,
                revisions=revisions,
                cost_usd=cycle_cost,
                duration_s=time.monotonic() - t_cycle_start,
                desire_raw=desire.raw_response,
                plan_raw=plan.steps,
                judgment_feedback=judgment.feedback,
                result_summary=result.summary if result else "",
                result_details=result.details if result else "",
            ),
            now=now,
        )

        return {
            "action": desire.action.value,
            "topic": desire.topic,
            "approved": judgment.approved,
            "result": result.summary if result else None,
            "sandbox_violated": sandbox_violated,
        }

    def _log_cycle(self, record: CycleRecord, *, now: datetime) -> None:
        path = cycle_log_path(
            self.manifest,
            when=now,
            action=record.action,
            topic=record.topic,
        )
        try:
            write_cycle(path, record)
        except OSError as e:
            logger.error("Failed to write cycle log to %s: %s", path, e)

    def run(self) -> None:
        """Run the heartbeat loop until stopped."""
        self._running = True

        def handle_signal(signum, frame):
            logger.info("Received signal %d, stopping heartbeat...", signum)
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        logger.info("Heartbeat daemon starting (interval: %ds)", self.interval)
        logger.info("Loading viveka core...")
        self.viveka.load()

        while self._running:
            try:
                self.beat_once()
            except Exception as exc:
                logger.exception("Heartbeat error: %s", exc)

            if not self._running:
                break

            logger.info("Sleeping %ds until next heartbeat...", self.interval)
            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)

        self.viveka.unload()
        logger.info("Heartbeat daemon stopped.")
