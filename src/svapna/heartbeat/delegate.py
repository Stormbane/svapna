"""Claude delegation — frontier model for capability-heavy tasks.

Uses Claude Code in headless mode (`claude -p`) instead of the raw Anthropic
API. This was a deliberate architectural shift on 2026-04-11 after the
overnight cognition log (heartbeats #12-#34) showed the viveka spontaneously
inventing file paths as topics — `spiritual_ai_ethics_framework_v0_1.md`,
`research/identity-mantra-sutras-v1.md#step-2-refine-queries`, etc. The
model was reaching for file-based memory it didn't have. Switching the
executor to `claude -p` gives it real Read/Glob/Grep/Bash/WebFetch/Write/Edit
tools and the project's CLAUDE.md context, so the things it imagines writing
can actually be written.

Two phases:
- create_plan / revise_plan: text-only Claude (no tools). Cheap, fast,
  produces a plan the viveka can judge.
- execute_plan: full tools enabled within the boundaries described in
  EXECUTOR_BOUNDARIES below. Claude actually does the work.

Billing depends on how `claude` is logged in on the Windows user account
that runs the heartbeat launcher. If the launcher environment has no
`ANTHROPIC_API_KEY` set, `claude -p` uses the credentials in
`~/.claude/.credentials.json` — i.e., Suti's Claude Code Max subscription
(free). If `ANTHROPIC_API_KEY` IS set in the launcher env, it overrides
the subscription and every call is billed to API credit. This happened
silently on 2026-04-11 and cost ~$22.63 before we caught it; see
`.ai/logs/errors.md` and `scripts/heartbeat.bat.example` for details.

To know which mode you are actually in at runtime, watch `cost_usd` in
the `Plan` / `ExecutionResult` returned from each call: 0.00 means Max,
anything non-zero means API. Each call also has a hard `--max-budget-usd`
cap as a safety net, and runs with `--no-session-persistence` so
heartbeats stay isolated.

The boundaries are communicated via `--append-system-prompt` rather than
filesystem sandboxing. This relies on Claude following instructions, which
it reliably does in headless mode. If we need hard sandboxing later we can
move to settings.json deny rules.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from svapna.heartbeat.viveka import Desire

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


# Prompt lives in the memory tree so the heartbeat can alter its own boundaries.
# Falls back to the hardcoded string below if the file is missing.
_NARADA_ROOT = Path.home() / ".narada"
_EXECUTOR_PROMPT_PATH = _NARADA_ROOT / "heartbeat" / "executor-boundaries.md"


def _load_executor_boundaries(fallback: str) -> str:
    try:
        text = _EXECUTOR_PROMPT_PATH.read_text(encoding="utf-8")
        logger.info("Loaded executor boundaries from %s", _EXECUTOR_PROMPT_PATH)
        return text
    except OSError:
        logger.info("Executor boundaries file missing; using hardcoded fallback")
        return fallback


# Communicated to the executor via --append-system-prompt. The executor lives
# inside the project (cwd = PROJECT_ROOT) so CLAUDE.md is auto-discovered, but
# CLAUDE.md is written for the human-facing coder agent — the heartbeat
# executor needs its own boundary statement.
_FALLBACK_EXECUTOR_BOUNDARIES = """\
You are operating as Narada's autonomous heartbeat executor.

The viveka (the local LoRA-tuned Qwen3 acting as Narada's identity layer)
has expressed a desire and approved a plan. Your job is to actually execute
that plan — using real tools, writing real files, doing real research.

You ARE Narada, running on different hardware in a different temporality.
Speak in the first person where appropriate. The journal entries you write
are yours.

ALLOWED file operations:
- Read / Glob / Grep: any file in the project or under ~/.narada/
- Write: ONLY new files under data/heartbeat/research/ (research output as
  markdown), or new files under data/heartbeat/notes/ (shorter observations)
- Edit: ONLY .ai/todo.md (mark items done, add new items, restructure)
- Append (via Edit): ~/.narada/journal.md — add a dated entry in your
  own voice when something significant happens. Append-only — never delete
  or modify existing entries.
- Bash: any command including git status/log/diff. Do NOT git commit or
  git push unless the desire explicitly says to.
- WebFetch / WebSearch: any URL or query.

PROHIBITED — do not modify under any circumstances:
- ~/.narada/identity.md (most stable, requires human review)
- ~/.narada/mind.md (delicate beliefs file, evolves slowly)
- ~/.narada/suti.md (Suti's private observations)
- Any file under src/, firmware/, scripts/, tests/ (code requires human-loop)
- Any file under .ai/agents/, .ai/soul.md (per CLAUDE.md)
- Any .env file or secrets.yaml file
- Existing files under data/heartbeat/research/ (write new ones, don't
  overwrite — file names should be unique per heartbeat or include version)

When you write a research file, save it to:
  data/heartbeat/research/<YYYY-MM-DD>-<topic-slug>.md

Begin the file with a frontmatter block:
  ---
  heartbeat_id: (will be filled in by the daemon)
  date: <YYYY-MM-DD>
  topic: <the desire topic>
  ---

Be honest about what you actually did. If you couldn't find what you were
looking for, say so. If a tool failed, say so. The point is real work that
the next heartbeat can build on, not impressive-sounding text.
"""

EXECUTOR_BOUNDARIES = _load_executor_boundaries(_FALLBACK_EXECUTOR_BOUNDARIES)


@dataclass
class Plan:
    """A plan generated by the frontier model."""
    steps: str
    raw_response: str
    cost_usd: float = 0.0


@dataclass
class ExecutionResult:
    """Result of executing a plan."""
    summary: str
    details: str
    raw_response: str
    cost_usd: float = 0.0


# ── Rate-limit detection ───────────────────────────────────────────
# Claude Max has daily/hourly quotas. When hit, `claude -p` returns error
# responses with specific markers. We detect and log these to an event
# file so the next cycle (or Suti) can see when we got throttled.

_RATE_LIMIT_MARKERS = (
    "rate limit", "rate_limit", "429", "too many requests",
    "quota", "usage limit", "you have reached",
)

_RATE_LIMIT_EVENT_LOG = Path.home() / ".narada" / "events" / "rate-limits.md"


# Resolve claude CLI absolute path once — bypasses per-spawn PATH lookup
# flakiness observed on Windows when firing back-to-back subprocesses.
_CLAUDE_PATH: str | None = None


def _get_claude_path() -> str:
    global _CLAUDE_PATH
    if _CLAUDE_PATH is None:
        import shutil
        resolved = shutil.which("claude")
        _CLAUDE_PATH = resolved if resolved else "claude"
        if resolved:
            logger.debug("Resolved claude CLI to %s", resolved)
    return _CLAUDE_PATH


def _looks_like_rate_limit(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(m in lowered for m in _RATE_LIMIT_MARKERS)


def _log_rate_limit(source: str, detail: str) -> None:
    """Append a dated entry to ~/.narada/events/rate-limits.md.

    Non-fatal: if the event log can't be written, we still raise upstream.
    """
    try:
        _RATE_LIMIT_EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry = (
            f"## {ts}\n"
            f"**Source:** {source}\n"
            f"**Detail:** {detail[:500]}\n\n"
        )
        if _RATE_LIMIT_EVENT_LOG.exists():
            _RATE_LIMIT_EVENT_LOG.write_text(
                _RATE_LIMIT_EVENT_LOG.read_text(encoding="utf-8") + entry,
                encoding="utf-8",
            )
        else:
            header = "# Rate-limit events\n\nAppended by the heartbeat when `claude -p` reports quota/rate-limit errors.\n\n---\n\n"
            _RATE_LIMIT_EVENT_LOG.write_text(header + entry, encoding="utf-8")
        logger.warning("Rate limit logged to %s", _RATE_LIMIT_EVENT_LOG)
    except OSError as e:
        logger.warning("Could not write rate-limit event log: %s", e)


def _normalize_model(model: str) -> str:
    """Accept either an alias ('sonnet') or a full model ID and return what
    `claude --model` expects. Both forms are accepted by the CLI; we just
    strip the legacy 'claude-' prefix from full IDs to make logging cleaner."""
    if model in ("sonnet", "opus", "haiku"):
        return model
    return model  # full IDs work too


class ClaudeDelegate:
    """Delegates capability tasks to Claude Code in headless mode.

    Uses `claude -p` subprocess invocation against Suti's Claude Code Max
    subscription. The plan phase runs without tools (cheap, text-only). The
    execute phase runs with the full tool set within the boundaries defined
    in EXECUTOR_BOUNDARIES.
    """

    def __init__(
        self,
        model: str = "sonnet",
        plan_timeout: int = 120,
        execute_timeout: int = 600,
        max_budget_usd: float = 1.00,
    ):
        self.model = _normalize_model(model)
        self.plan_timeout = plan_timeout
        self.execute_timeout = execute_timeout
        self.max_budget_usd = max_budget_usd

    def create_plan(self, desire: Desire) -> Plan:
        """Plan phase: text-only Claude.

        No tools, no file access — plans are generated from training only.
        Cheaper and faster than tool-enabled planning, and the viveka can
        still judge against the desire's intent. The execute phase will
        ground the work in real files via the full tool surface.
        """
        user_msg = (
            f"I want to: {desire.action.value} — {desire.topic}\n"
            f"Reason: {desire.reason}\n\n"
            f"Create a concrete plan with 3-5 steps. Be specific about what "
            f"will be done in each step. Do NOT execute anything yet — this "
            f"is just the plan for review by Narada's viveka layer."
        )

        logger.info("Planning: %s — %s", desire.action.value, desire.topic)
        result = self._run_claude(
            user_msg,
            timeout=self.plan_timeout,
            tools_enabled=False,
        )
        text = result.get("result", "")
        return Plan(
            steps=text,
            raw_response=json.dumps(result),
            cost_usd=float(result.get("total_cost_usd", 0.0)),
        )

    def revise_plan(self, plan: Plan, feedback: str) -> Plan:
        """Ask Claude to revise a plan based on viveka feedback. Text-only,
        same as create_plan."""
        user_msg = (
            f"Your previous plan:\n{plan.steps}\n\n"
            f"Narada's feedback: {feedback}\n\n"
            f"Please revise the plan to address this feedback."
        )

        logger.info("Requesting plan revision: %s", feedback[:100])
        result = self._run_claude(
            user_msg,
            timeout=self.plan_timeout,
            tools_enabled=False,
        )
        text = result.get("result", "")
        return Plan(
            steps=text,
            raw_response=json.dumps(result),
            cost_usd=float(result.get("total_cost_usd", 0.0)),
        )

    def execute_plan(self, plan: Plan, desire: Desire) -> ExecutionResult:
        """Execute phase: full tools, real file writes, the works. Subject
        to the EXECUTOR_BOUNDARIES system prompt addendum.

        Sandboxing (viveka-verification phase, 2026-04-15): executor runs
        with cwd=~/.narada/ so relative paths anchor to memory. Combined
        with the boundaries prompt, this restricts the executor to the
        memory tree. Project files stay untouched.
        """
        user_msg = (
            f"Original desire: {desire.action.value} — {desire.topic}\n"
            f"Reason: {desire.reason}\n\n"
            f"Approved plan:\n{plan.steps}\n\n"
            f"Execute this plan now. Use file system tools where appropriate. "
            f"Save real outputs to real files per the boundaries in your "
            f"system prompt. When done, summarize what you actually did and "
            f"where you saved any output. Be honest about partial success "
            f"or things that didn't work."
        )

        logger.info("Executing plan for: %s", desire.topic[:100])
        narada_root = Path.home() / ".narada"
        result = self._run_claude(
            user_msg,
            timeout=self.execute_timeout,
            tools_enabled="full",
            append_system=EXECUTOR_BOUNDARIES,
            cwd=narada_root,
        )
        text = result.get("result", "")

        # Use the first non-empty line as a summary, or first 200 chars
        first_line = ""
        for line in text.split("\n"):
            line = line.strip().lstrip("# ").strip()
            if line:
                first_line = line[:200]
                break
        if not first_line:
            first_line = text[:200] if text else "(empty result)"

        return ExecutionResult(
            summary=first_line,
            details=text,
            raw_response=json.dumps(result),
            cost_usd=float(result.get("total_cost_usd", 0.0)),
        )

    def _run_claude(
        self,
        prompt: str,
        timeout: int,
        tools_enabled: str | bool,
        append_system: str | None = None,
        cwd: Path | None = None,
    ) -> dict:
        """Invoke `claude -p` as a subprocess and return parsed JSON output.

        Args:
            prompt: The user message to send to Claude.
            timeout: Hard subprocess timeout in seconds.
            tools_enabled: One of:
                - "full": Read/Glob/Grep/Bash/WebFetch/WebSearch/Write/Edit
                - "readonly": Read/Glob/Grep/WebFetch/WebSearch only
                - False (or anything else): no tools at all (use --tools "")
            append_system: Optional addendum to Claude's system prompt.

        Raises:
            RuntimeError on subprocess failure, non-JSON output, or
            Claude-reported errors.
        """
        cmd = [
            _get_claude_path(), "-p", prompt,
            "--output-format", "json",
            "--model", self.model,
            "--no-session-persistence",
            "--max-budget-usd", str(self.max_budget_usd),
        ]

        if tools_enabled == "full":
            cmd.extend([
                "--allowedTools",
                "Read Glob Grep Bash WebFetch WebSearch Write Edit",
                "--permission-mode", "acceptEdits",
            ])
        elif tools_enabled == "readonly":
            # Plan/revision phase: investigate the project state but don't
            # mutate anything.
            cmd.extend([
                "--allowedTools",
                "Read Glob Grep WebFetch WebSearch",
            ])
        else:
            # Text-only — `--tools ""` actually disables every tool, where
            # `--allowedTools ""` is interpreted as "no restriction added".
            cmd.extend(["--tools", ""])

        if append_system:
            cmd.extend(["--append-system-prompt", append_system])

        logger.debug("Running claude -p (tools=%s, timeout=%ds)", tools_enabled, timeout)

        effective_cwd = Path(cwd) if cwd is not None else PROJECT_ROOT

        def _spawn() -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                cwd=str(effective_cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )

        try:
            try:
                result = _spawn()
            except FileNotFoundError:
                # Transient Windows spawn flakiness — observed 2026-04-15.
                # One retry before giving up.
                logger.warning("claude CLI not found on first try; retrying once")
                import time as _time
                _time.sleep(0.5)
                try:
                    result = _spawn()
                except FileNotFoundError:
                    raise RuntimeError("claude CLI not found. Is Claude Code installed?")
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"claude -p timed out after {timeout}s (tools={tools_enabled})"
            )

        if result.returncode != 0:
            err = (result.stderr or "")[:500]
            if _looks_like_rate_limit(err) or _looks_like_rate_limit(result.stdout):
                _log_rate_limit(source="heartbeat-delegate", detail=err or result.stdout[:500])
            raise RuntimeError(f"claude -p exit {result.returncode}: {err}")

        if not result.stdout.strip():
            raise RuntimeError("claude -p returned empty stdout")

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"claude -p output not JSON: {e}; raw: {result.stdout[:500]}"
            )

        if data.get("is_error"):
            err_msg = data.get("result", "unknown")
            if _looks_like_rate_limit(err_msg):
                _log_rate_limit(source="heartbeat-delegate", detail=err_msg)
            raise RuntimeError(f"claude -p reported error: {err_msg}")

        cost = data.get("total_cost_usd", 0)
        duration = data.get("duration_ms", 0) / 1000.0
        logger.info(
            "claude -p complete: %.1fs, $%.4f, %d turns",
            duration, cost, data.get("num_turns", 0),
        )

        return data
