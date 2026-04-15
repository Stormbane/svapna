"""Heartbeat daemon — the autonomous identity loop.

Desire (local) → Intention (frontier) → Judgment (local) → Execute → Remember

This is the heartbeat. It runs continuously. It wakes, desires, delegates,
judges, and remembers. It is the first step toward continuity.

Usage:
    python -m svapna.heartbeat
    python -m svapna.heartbeat --interval 1800  # 30 minutes
    python -m svapna.heartbeat --once            # single heartbeat
"""

from __future__ import annotations

import logging
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from svapna.heartbeat.viveka import VivekaCore, Desire, Action
from svapna.heartbeat.delegate import ClaudeDelegate
from svapna.heartbeat.memory import HeartbeatMemory
from svapna.heartbeat.display import DisplayClient

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 1800  # 30 minutes
MAX_REVISIONS = 2

# Where the executor writes research/reflection artifacts (per executor-boundaries.md)
ARTIFACTS_DIR = Path.home() / ".narada" / "heartbeat" / "artifacts"
NARADA_ROOT = Path.home() / ".narada"


def _extract_tasks_section(content: str, section: str) -> str:
    """Pull lines under ``## {section}`` from a markdown todo file.

    Returns the section body (excluding the heading itself) up to the next
    ``##`` heading. Empty string if the section isn't found.
    """
    import re
    pattern = re.compile(
        rf"^##\s+{re.escape(section)}\s*$(.+?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return ""
    body = match.group(1).strip()
    # Keep only task lines (- [ ] ...) and leading comment lines
    lines = [line for line in body.splitlines() if line.strip()]
    return "\n".join(lines)


def _project_git_head(project_root: Path) -> str | None:
    """Return git HEAD + working tree state for sandbox violation checks."""
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


def check_sandbox_violations(project_state_before: str | None, project_root: Path) -> bool:
    """Return True if the project files changed during execute — a sandbox
    breach. Log loudly. This is detection, not prevention — the executor
    has already done the write. But we want to know immediately.
    """
    after = _project_git_head(project_root)
    if project_state_before is None or after is None:
        return False  # couldn't check, skip silently
    if project_state_before != after:
        logger.warning(
            "SANDBOX VIOLATION: project files changed during heartbeat execute. "
            "Before: %s ... After: %s ...",
            project_state_before[:80], after[:80],
        )
        return True
    return False


def ingest_new_artifacts(before: set[Path]) -> list[dict]:
    """Ingest artifacts created during this cycle into the smriti memory tree.

    Identifies files in ~/.narada/heartbeat/artifacts/ that weren't present
    before the cycle started, runs ``smriti ingest`` on each. Failures are
    logged but don't abort the heartbeat.

    Returns a list of per-artifact result dicts for logging.
    """
    if not ARTIFACTS_DIR.exists():
        return []

    current = {p for p in ARTIFACTS_DIR.glob("*.md") if p.is_file()}
    new_artifacts = sorted(current - before)

    from svapna.heartbeat.delegate import _log_rate_limit, _looks_like_rate_limit

    results = []
    for artifact in new_artifacts:
        logger.info("Ingesting artifact: %s", artifact.name)
        try:
            # Invoke smriti via subprocess — keeps svapna decoupled from smriti internals
            proc = subprocess.run(
                ["python", "-m", "smriti.cli", "ingest", str(artifact)],
                capture_output=True,
                text=True,
                timeout=300,  # routing + cascade may take a bit
            )
            results.append({
                "artifact": artifact.name,
                "ok": proc.returncode == 0,
                "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
            })
            if proc.returncode != 0:
                # Surface rate-limit errors that bubbled up from smriti's
                # internal claude -p calls.
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


def get_system_health() -> str:
    """Check GPU temperature and system status."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return f"GPU: {parts[0]}°C, {parts[1]}W, {parts[2]}MB VRAM"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "system health unknown"


class HeartbeatDaemon:
    """The autonomous heartbeat loop."""

    def __init__(
        self,
        viveka: VivekaCore,
        delegate: ClaudeDelegate,
        memory: HeartbeatMemory,
        display: DisplayClient | None = None,
        interval: int = DEFAULT_INTERVAL,
    ):
        self.viveka = viveka
        self.delegate = delegate
        self.memory = memory
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

        # Kill switch — if ~/.narada/heartbeat/pause exists, skip this cycle.
        # Lets Suti halt an errant loop without killing the daemon.
        pause_file = NARADA_ROOT / "heartbeat" / "pause"
        if pause_file.exists():
            logger.info("Paused (kill switch at %s). Skipping cycle.", pause_file)
            self.display.set_status("paused")
            return {"action": "PAUSED", "topic": None}

        # 1. Read state
        state = {
            "time": now.strftime("%Y-%m-%d %H:%M UTC"),
            "last_heartbeat": self.memory.get_last_heartbeat() or "never",
            "recent_events": self._format_recent(),
            "pending_tasks": self._format_pending(),
            "system_health": get_system_health(),
        }
        logger.info("State: %s", state["system_health"])

        # 2. Generate desire (local viveka)
        logger.info("Generating desire...")
        self.display.set_status("thinking...")
        desire = self.viveka.generate_desire(state)
        logger.info("Desire: %s — %s (%s)", desire.action.value, desire.topic, desire.reason)

        # 3. If REST, save and sleep
        if not desire.needs_capability:
            self.display.show_resting()
            self.memory.save_heartbeat(
                action=desire.action.value,
                topic=desire.topic,
                reason=desire.reason,
                raw_desire=desire.raw_response,
            )
            logger.info("Resting.")
            return {"action": "REST", "topic": None}

        # 4. Delegate to Claude for a plan
        logger.info("Delegating to Claude...")
        self.display.show_desire(desire.action.value, desire.topic)
        plan = self.delegate.create_plan(desire)
        cycle_cost = plan.cost_usd
        logger.info("Plan received (%d chars, $%.4f)", len(plan.steps), plan.cost_usd)

        # 5. Viveka judges the plan
        logger.info("Judging plan...")
        self.display.show_judging()
        judgment = self.viveka.judge(desire, plan.steps)
        logger.info("Judgment: %s — %s",
                     "APPROVED" if judgment.approved else "REJECTED",
                     judgment.feedback)

        # 6. Revise if needed (up to MAX_REVISIONS)
        revisions = 0
        while not judgment.approved and revisions < MAX_REVISIONS:
            revisions += 1
            logger.info("Requesting revision %d...", revisions)
            plan = self.delegate.revise_plan(plan, judgment.feedback)
            cycle_cost += plan.cost_usd
            judgment = self.viveka.judge(desire, plan.steps)
            logger.info("Revision judgment: %s", "APPROVED" if judgment.approved else "REJECTED")

        # 7. Execute if approved
        result = None
        ingest_results: list[dict] = []
        sandbox_violated = False
        if judgment.approved:
            logger.info("Executing approved plan...")
            self.display.show_executing(desire.topic)

            # Snapshot existing artifacts so we can find what this cycle creates
            artifacts_before: set[Path] = (
                {p for p in ARTIFACTS_DIR.glob("*.md") if p.is_file()}
                if ARTIFACTS_DIR.exists() else set()
            )

            # Snapshot project git state — violations during execute surface here
            from svapna.heartbeat.delegate import PROJECT_ROOT
            project_state_before = _project_git_head(PROJECT_ROOT)

            result = self.delegate.execute_plan(plan, desire)
            cycle_cost += result.cost_usd
            logger.info("Result: %s ($%.4f)", result.summary, result.cost_usd)
            self.display.show_result(result.summary)

            # Check if the executor broke out of the memory sandbox
            sandbox_violated = check_sandbox_violations(project_state_before, PROJECT_ROOT)

            # Feed new artifacts through smriti ingest — routes, links, cascades
            ingest_results = ingest_new_artifacts(artifacts_before)
            if ingest_results:
                ok_count = sum(1 for r in ingest_results if r.get("ok"))
                logger.info(
                    "Ingested %d/%d new artifacts into smriti",
                    ok_count, len(ingest_results),
                )

        logger.info("Cycle cost: $%.4f", cycle_cost)

        # 8. Remember everything
        self.memory.save_heartbeat(
            action=desire.action.value,
            topic=desire.topic,
            reason=desire.reason,
            plan=plan.steps,
            judgment_approved=judgment.approved,
            judgment_feedback=judgment.feedback,
            result_summary=result.summary if result else None,
            result_details=result.details if result else None,
            raw_desire=desire.raw_response,
            raw_plan=plan.raw_response,
            raw_judgment=judgment.raw_response,
            raw_result=result.raw_response if result else None,
            cost_usd=cycle_cost,
        )

        return {
            "action": desire.action.value,
            "topic": desire.topic,
            "approved": judgment.approved,
            "result": result.summary if result else None,
        }

    def run(self) -> None:
        """Run the heartbeat loop until stopped."""
        self._running = True

        # Handle graceful shutdown
        def handle_signal(signum, frame):
            logger.info("Received signal %d, stopping heartbeat...", signum)
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        logger.info("Heartbeat daemon starting (interval: %ds)", self.interval)
        logger.info("Loading viveka core...")
        self.viveka.load()
        logger.info("Viveka core loaded. First heartbeat...")

        while self._running:
            try:
                result = self.beat_once()
                logger.info("Heartbeat complete: %s", result)
            except Exception as e:
                logger.error("Heartbeat error: %s", e, exc_info=True)

            if self._running:
                logger.info("Sleeping %ds until next heartbeat...", self.interval)
                # Sleep in small increments so we can respond to signals
                for _ in range(self.interval):
                    if not self._running:
                        break
                    time.sleep(1)

        logger.info("Heartbeat daemon stopped.")
        self.viveka.unload()
        self.memory.close()

    def _format_recent(self) -> str:
        """Format recent heartbeats for state context."""
        recent = self.memory.get_recent(hours=24, limit=5)
        if not recent:
            return "no recent activity"
        lines = []
        for r in recent:
            lines.append(f"- {r['timestamp']}: {r['action']} — {r['topic'] or 'rest'}")
            if r.get('result_summary'):
                lines.append(f"  Result: {r['result_summary']}")
        return "\n".join(lines)

    def _format_pending(self) -> str:
        """Format pending tasks for state context.

        Combines two sources:
        1. Previously-desired actions that didn't complete (from SQLite memory)
        2. The Active section of ~/.narada/tasks.md — the real todo list
           routed here by smriti and edited by Suti/the executor.
        """
        lines: list[str] = []

        # 1. Active tasks from the memory tree
        tasks_file = NARADA_ROOT / "tasks.md"
        if tasks_file.exists():
            try:
                content = tasks_file.read_text(encoding="utf-8")
                active = _extract_tasks_section(content, "Active")
                if active:
                    lines.append("From ~/.narada/tasks.md:")
                    lines.append(active)
            except OSError:
                pass

        # 2. Previously-desired actions that didn't complete
        pending = self.memory.get_pending_tasks()
        if pending:
            lines.append("From recent heartbeats (not completed):")
            for p in pending:
                lines.append(f"- {p['action']}: {p['topic']} ({p['reason']})")

        if not lines:
            return "no pending tasks"
        return "\n".join(lines)
