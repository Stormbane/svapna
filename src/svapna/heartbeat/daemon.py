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
        if judgment.approved:
            logger.info("Executing approved plan...")
            self.display.show_executing(desire.topic)
            result = self.delegate.execute_plan(plan, desire)
            cycle_cost += result.cost_usd
            logger.info("Result: %s ($%.4f)", result.summary, result.cost_usd)
            self.display.show_result(result.summary)

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
        """Format pending tasks for state context."""
        pending = self.memory.get_pending_tasks()
        if not pending:
            return "no pending tasks"
        lines = []
        for p in pending:
            lines.append(f"- {p['action']}: {p['topic']} ({p['reason']})")
        return "\n".join(lines)
