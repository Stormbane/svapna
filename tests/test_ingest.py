"""Test conversation ingestion against real Claude Code data."""

from pathlib import Path

from svapna.consolidate.ingest import find_session_logs, ingest_all, parse_session_log


def test_find_session_logs():
    """Verify we can find conversation log files."""
    logs = find_session_logs()
    assert len(logs) > 0, "Should find at least one conversation log"
    for log in logs:
        assert log.suffix == ".jsonl"
        assert log.exists()


def test_parse_current_session():
    """Parse the current conversation (this session) as a smoke test."""
    # Find the most recent log
    logs = find_session_logs()
    assert logs, "No logs found"

    session = parse_session_log(logs[0])
    assert session.session_id, "Session should have an ID"
    assert len(session.exchanges) > 0, "Should have at least one exchange"

    # Check exchange structure
    first = session.exchanges[0]
    assert first.human.role == "user"
    assert first.assistant.role == "assistant"
    assert first.human.text, "Human message should have text"
    assert first.assistant.text, "Assistant message should have text"
    assert first.session_id == session.session_id


def test_ingest_all():
    """Verify full ingestion produces valid sessions."""
    sessions = ingest_all()
    assert len(sessions) > 0, "Should find at least one session"

    total_exchanges = sum(len(s.exchanges) for s in sessions)
    print(f"\nIngested {len(sessions)} sessions with {total_exchanges} total exchanges")

    # Print summary for manual review
    for s in sessions[:5]:
        duration = f" ({s.duration_minutes:.0f}min)" if s.duration_minutes else ""
        print(f"  {s.session_id[:8]}... : {len(s.exchanges)} exchanges{duration} — {s.project}")


def test_exchange_content_quality():
    """Verify extracted exchanges have meaningful content."""
    sessions = ingest_all()
    assert sessions, "No sessions found"

    # Check that we're getting real content, not just metadata
    for session in sessions[:3]:
        for exchange in session.exchanges[:3]:
            # Human messages should be real input, not system noise
            assert len(exchange.human.text) > 1, "Human message too short"
            # Assistant messages should be substantive
            assert len(exchange.assistant.text) > 10, "Assistant response too short"
