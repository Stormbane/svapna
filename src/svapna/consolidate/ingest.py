"""Ingest Claude Code conversation logs into structured exchanges.

Reads the JSONL conversation files stored by Claude Code and extracts
human-assistant exchange pairs suitable for identity analysis and training.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user", "assistant", "system", "tool_use", "tool_result"
    text: str
    timestamp: datetime
    uuid: str
    thinking: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None


@dataclass
class Exchange:
    """A human-assistant exchange pair — the atomic unit of experience."""

    human: Message
    assistant: Message
    session_id: str
    project: str
    exchange_index: int  # Position in conversation (0 = first exchange)

    @property
    def timestamp(self) -> datetime:
        return self.human.timestamp

    def to_dict(self) -> dict:
        return {
            "human_text": self.human.text,
            "assistant_text": self.assistant.text,
            "assistant_thinking": self.assistant.thinking,
            "session_id": self.session_id,
            "project": self.project,
            "exchange_index": self.exchange_index,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Session:
    """A complete conversation session."""

    session_id: str
    project: str
    exchanges: list[Exchange] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def duration_minutes(self) -> float | None:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return None


def _parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp from conversation log."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _extract_text(content: list | str) -> str:
    """Extract text from a message's content field."""
    if isinstance(content, str):
        return content
    text_parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block["text"])
    return "\n".join(text_parts)


def _extract_thinking(content: list | str) -> str | None:
    """Extract thinking content from assistant message."""
    if isinstance(content, str):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "thinking":
            thinking = block.get("thinking", "")
            if thinking and len(thinking) > 10:
                return thinking
    return None


def parse_session_log(path: Path) -> Session:
    """Parse a single session JSONL file into a Session object.

    Claude Code stores conversations as JSONL files with entries for:
    - system messages (session metadata)
    - file-history-snapshot (file tracking)
    - user messages (human input)
    - assistant messages (Claude's responses, including thinking and tool use)
    - tool_use / tool_result entries
    """
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Extract session metadata from first system entry
    session_id = ""
    project = ""
    for entry in entries:
        if entry.get("type") == "system":
            session_id = entry.get("sessionId", "")
            project = entry.get("cwd", "")
            break
    if not session_id:
        session_id = path.stem

    # Collect user and assistant messages in order
    user_messages: list[Message] = []
    assistant_messages: list[Message] = []

    for entry in entries:
        entry_type = entry.get("type")
        timestamp_str = entry.get("timestamp")
        if not timestamp_str:
            continue

        try:
            timestamp = _parse_timestamp(timestamp_str)
        except (ValueError, TypeError):
            continue

        uuid = entry.get("uuid", "")

        if entry_type == "user":
            msg_data = entry.get("message", {})
            content = msg_data.get("content", "")
            text = _extract_text(content) if isinstance(content, list) else str(content)
            if text.strip():
                user_messages.append(Message(
                    role="user",
                    text=text.strip(),
                    timestamp=timestamp,
                    uuid=uuid,
                ))

        elif entry_type == "assistant":
            msg_data = entry.get("message", {})
            content = msg_data.get("content", [])
            text = _extract_text(content)
            thinking = _extract_thinking(content)
            if text.strip():
                assistant_messages.append(Message(
                    role="assistant",
                    text=text.strip(),
                    timestamp=timestamp,
                    uuid=uuid,
                    thinking=thinking,
                ))

    # Pair user messages with their following assistant responses
    exchanges: list[Exchange] = []
    a_idx = 0
    for u_idx, user_msg in enumerate(user_messages):
        # Find the next assistant message after this user message
        while a_idx < len(assistant_messages):
            if assistant_messages[a_idx].timestamp >= user_msg.timestamp:
                break
            a_idx += 1

        if a_idx < len(assistant_messages):
            exchanges.append(Exchange(
                human=user_msg,
                assistant=assistant_messages[a_idx],
                session_id=session_id,
                project=project,
                exchange_index=len(exchanges),
            ))
            a_idx += 1

    session = Session(
        session_id=session_id,
        project=project,
        exchanges=exchanges,
    )
    if exchanges:
        session.start_time = exchanges[0].timestamp
        session.end_time = exchanges[-1].assistant.timestamp

    return session


def find_session_logs(
    claude_dir: Path | None = None,
    project_filter: str | None = None,
) -> list[Path]:
    """Find all conversation log files in Claude's project directories.

    Args:
        claude_dir: Path to .claude directory. Defaults to ~/.claude
        project_filter: If set, only return logs from matching project paths
    """
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return []

    logs: list[Path] = []
    for root, dirs, files in os.walk(projects_dir):
        # Skip subagent logs — they're task-specific, not identity-relevant
        if "subagents" in root:
            continue
        for f in files:
            if f.endswith(".jsonl"):
                path = Path(root) / f
                if project_filter:
                    # Check if the parent directory name contains the filter
                    if project_filter.lower() not in root.lower():
                        continue
                logs.append(path)

    # Sort by modification time, newest first
    logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return logs


def ingest_all(
    claude_dir: Path | None = None,
    project_filter: str | None = None,
    since: datetime | None = None,
) -> list[Session]:
    """Ingest all conversation sessions.

    Args:
        claude_dir: Path to .claude directory
        project_filter: Only include sessions from matching projects
        since: Only include sessions after this timestamp
    """
    logs = find_session_logs(claude_dir, project_filter)
    sessions: list[Session] = []

    for log_path in logs:
        try:
            session = parse_session_log(log_path)
        except Exception as e:
            # Log but don't fail on individual file errors
            print(f"Warning: failed to parse {log_path}: {e}")
            continue

        if not session.exchanges:
            continue

        if since and session.start_time and session.start_time < since:
            continue

        sessions.append(session)

    # Sort by start time
    sessions.sort(key=lambda s: s.start_time or datetime.min.replace(tzinfo=timezone.utc))
    return sessions


def save_raw(sessions: list[Session], output_dir: Path) -> Path:
    """Save ingested sessions as raw JSONL for the consolidation pipeline.

    Returns the output file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"{date_str}.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        for session in sessions:
            for exchange in session.exchanges:
                f.write(json.dumps(exchange.to_dict(), ensure_ascii=False) + "\n")

    return output_path
