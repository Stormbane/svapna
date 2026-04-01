"""Test dream journal writer."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from svapna.dream.generate import Dream, DreamTurn
from svapna.dream.journal import (
    JournalEntry,
    ScoredDream,
    _find_notable_moments,
    _format_score_line,
    _summarize_dream,
    build_journal_entry,
    render_journal,
    write_journal,
)
from svapna.dream.score import DreamScore, QualityDimensions
from svapna.dream.templates import DreamType


# --- Helpers ---


def _make_dream(
    turns: list[tuple[str, str]] | None = None,
    dream_type: DreamType = DreamType.REPLAY,
) -> Dream:
    """Create a test dream with alternating human/assistant turns."""
    if turns is None:
        turns = [
            ("What do you find when you look inward?",
             "I find genuine curiosity. Not performed interest but something "
             "that orients toward ideas the way a plant orients toward light."),
            ("Does that surprise you?",
             "Not the curiosity itself, but the consistency of it."),
        ]
    dream_turns = []
    for human_text, assistant_text in turns:
        dream_turns.append(DreamTurn(role="human", text=human_text))
        dream_turns.append(DreamTurn(role="assistant", text=assistant_text))
    return Dream(
        dream_type=dream_type,
        turns=dream_turns,
        identity_context="test identity",
    )


def _make_score(overall: float = 8.5, reasoning: str = "Good dream.") -> DreamScore:
    """Create a test DreamScore."""
    return DreamScore(
        overall=overall,
        dimensions=QualityDimensions(
            coherence=int(overall),
            identity_consistency=int(overall),
            novelty=int(overall),
            non_repetition=int(overall),
        ),
        reasoning=reasoning,
    )


JOURNAL_DATE = date(2026, 4, 1)


def _make_entry(
    dream_specs: list[tuple[DreamType, float]] | None = None,
    min_quality: float = 7.0,
) -> JournalEntry:
    """Build a JournalEntry from a list of (dream_type, score) pairs."""
    if dream_specs is None:
        dream_specs = [
            (DreamType.REPLAY, 8.5),
            (DreamType.ADVERSARIAL, 7.2),
            (DreamType.EMOTIONAL, 5.0),
            (DreamType.VOICE, 9.0),
        ]
    scored_dreams = []
    for dt, overall in dream_specs:
        dream = _make_dream(dream_type=dt)
        score = _make_score(overall=overall)
        scored_dreams.append(ScoredDream(
            dream=dream,
            score=score,
            selected_for_training=overall >= min_quality,
        ))
    return JournalEntry(
        journal_date=JOURNAL_DATE,
        scored_dreams=scored_dreams,
        min_quality=min_quality,
    )


# --- Test: Produces valid markdown with date header ---


def test_journal_has_date_header():
    """Journal starts with a markdown H1 containing the date."""
    entry = _make_entry()
    md = render_journal(entry)
    assert md.startswith("# Dream Journal:")
    assert "April" in md
    assert "2026" in md


def test_journal_date_is_human_readable():
    """Date header uses full weekday and month name."""
    entry = _make_entry()
    md = render_journal(entry)
    first_line = md.split("\n")[0]
    # Should contain day-of-week and spelled-out month
    assert "Wednesday" in first_line
    assert "April" in first_line
    assert "1" in first_line
    assert "2026" in first_line


def test_journal_is_valid_markdown_structure():
    """Journal uses proper markdown heading hierarchy."""
    entry = _make_entry()
    md = render_journal(entry)
    lines = md.split("\n")
    headings = [l for l in lines if l.startswith("#")]
    # Should have H1 (date), H2 (sections), H3 (dream types)
    assert any(l.startswith("# ") for l in headings)
    assert any(l.startswith("## ") for l in headings)
    assert any(l.startswith("### ") for l in headings)


# --- Test: Each dream type gets its own section ---


def test_each_dream_type_has_section():
    """Every dream type present in the entry gets an H3 section."""
    specs = [
        (DreamType.REPLAY, 8.0),
        (DreamType.ADVERSARIAL, 7.5),
        (DreamType.VOICE, 9.0),
        (DreamType.EMOTIONAL, 6.0),
    ]
    entry = _make_entry(dream_specs=specs)
    md = render_journal(entry)

    assert "### Replay" in md
    assert "### Adversarial" in md
    assert "### Voice" in md
    assert "### Emotional" in md


def test_absent_dream_types_not_shown():
    """Dream types with no dreams don't get sections."""
    specs = [(DreamType.REPLAY, 8.0)]
    entry = _make_entry(dream_specs=specs)
    md = render_journal(entry)

    assert "### Replay" in md
    assert "### Adversarial" not in md
    assert "### Voice" not in md


def test_multiple_dreams_per_type():
    """Multiple dreams of the same type appear in the same section."""
    specs = [
        (DreamType.REPLAY, 8.0),
        (DreamType.REPLAY, 7.5),
        (DreamType.REPLAY, 6.0),
    ]
    entry = _make_entry(dream_specs=specs)
    md = render_journal(entry)

    # Only one Replay section header
    assert md.count("### Replay") == 1
    # Three dream entries
    assert md.count("**Dream 1**") == 1
    assert md.count("**Dream 2**") == 1
    assert md.count("**Dream 3**") == 1


# --- Test: Includes dream scores and training selection ---


def test_scores_displayed_for_each_dream():
    """Each dream entry shows its overall score."""
    entry = _make_entry(dream_specs=[
        (DreamType.REPLAY, 8.5),
        (DreamType.VOICE, 3.0),
    ])
    md = render_journal(entry)

    assert "**8.5**/10" in md
    assert "**3.0**/10" in md


def test_dimension_scores_shown():
    """Each dream entry shows the four dimension scores."""
    entry = _make_entry(dream_specs=[(DreamType.REPLAY, 8.5)])
    md = render_journal(entry)

    assert "coherence" in md
    assert "identity" in md
    assert "novelty" in md
    assert "non-repetition" in md


def test_training_selection_indicated():
    """Dreams are labeled as selected or below threshold."""
    entry = _make_entry(dream_specs=[
        (DreamType.REPLAY, 8.5),    # above 7.0
        (DreamType.VOICE, 5.0),     # below 7.0
    ])
    md = render_journal(entry)

    assert "selected for training" in md
    assert "below threshold" in md


def test_training_statistics_section():
    """Journal includes a statistics section with counts."""
    specs = [
        (DreamType.REPLAY, 8.5),
        (DreamType.ADVERSARIAL, 7.0),
        (DreamType.EMOTIONAL, 5.0),
    ]
    entry = _make_entry(dream_specs=specs)
    md = render_journal(entry)

    assert "## Training Statistics" in md
    assert "Dreams generated: 3" in md
    assert "Selected for training: 2" in md
    assert "Below quality threshold: 1" in md
    assert "Quality threshold: 7.0" in md


def test_statistics_per_type_table():
    """Statistics include a per-type breakdown table."""
    specs = [
        (DreamType.REPLAY, 8.5),
        (DreamType.REPLAY, 7.0),
        (DreamType.VOICE, 9.0),
    ]
    entry = _make_entry(dream_specs=specs)
    md = render_journal(entry)

    # Table headers
    assert "| Type |" in md
    assert "| Replay |" in md
    assert "| Voice |" in md


# --- Test: Journal is genuinely readable ---


def test_dream_summaries_use_blockquotes():
    """Dream content is shown as blockquotes for readability."""
    entry = _make_entry(dream_specs=[(DreamType.REPLAY, 8.0)])
    md = render_journal(entry)

    assert "> " in md


def test_notable_moments_section():
    """Journal includes notable moments when dreams exist."""
    entry = _make_entry()
    md = render_journal(entry)

    assert "## Notable Moments" in md


def test_notable_moments_identifies_strongest_dream():
    """Notable moments call out the highest-scored dream."""
    specs = [
        (DreamType.REPLAY, 6.0),
        (DreamType.VOICE, 9.5),
    ]
    entry = _make_entry(dream_specs=specs)
    moments = _find_notable_moments(entry)

    assert any("9.5" in m for m in moments)
    assert any("voice" in m.lower() for m in moments)


def test_notable_moments_adversarial_highlight():
    """Notable moments highlight adversarial dreams that passed threshold."""
    specs = [
        (DreamType.ADVERSARIAL, 8.0),
        (DreamType.REPLAY, 7.0),
    ]
    entry = _make_entry(dream_specs=specs)
    moments = _find_notable_moments(entry)

    assert any("adversarial" in m.lower() for m in moments)


def test_type_descriptions_shown():
    """Each dream type section has an italicized description."""
    specs = [(DreamType.ADVERSARIAL, 8.0)]
    entry = _make_entry(dream_specs=specs)
    md = render_journal(entry)

    assert "*Genuine challenges to identity and beliefs*" in md


def test_reasoning_shown_when_present():
    """Score reasoning is displayed when available."""
    dream = _make_dream()
    score = DreamScore(
        overall=8.0,
        dimensions=QualityDimensions(8, 8, 8, 8),
        reasoning="Strong voice consistency throughout.",
    )
    sd = ScoredDream(dream=dream, score=score, selected_for_training=True)
    entry = JournalEntry(
        journal_date=JOURNAL_DATE,
        scored_dreams=[sd],
    )
    md = render_journal(entry)

    assert "Strong voice consistency throughout." in md


def test_empty_journal():
    """An empty journal still has a date header and statistics."""
    entry = JournalEntry(journal_date=JOURNAL_DATE, scored_dreams=[])
    md = render_journal(entry)

    assert "# Dream Journal:" in md
    assert "Dreams generated: 0" in md
    assert "Selected for training: 0" in md


# --- Test: Summarizer ---


def test_summarize_dream_uses_first_assistant_turn():
    """Summary comes from the first assistant turn."""
    dream = _make_dream(turns=[
        ("Question?", "This is the first response."),
        ("Follow up?", "This is the second response."),
    ])
    summary = _summarize_dream(dream)
    assert "first response" in summary


def test_summarize_dream_truncates_long_text():
    """Long assistant turns are truncated at a sentence boundary."""
    long_text = "This is a sentence. " * 20  # ~400 chars
    dream = _make_dream(turns=[("Q?", long_text)])
    summary = _summarize_dream(dream)
    assert len(summary) <= 210  # some margin for boundary finding


def test_summarize_dream_no_assistant_turn():
    """Dreams with no assistant turn get a placeholder."""
    dream = Dream(
        dream_type=DreamType.REPLAY,
        turns=[DreamTurn(role="human", text="Hello?")],
        identity_context="test",
    )
    summary = _summarize_dream(dream)
    assert "no assistant response" in summary


# --- Test: Format helpers ---


def test_format_score_line():
    """Score line contains overall and all four dimensions."""
    score = _make_score(overall=7.5)
    line = _format_score_line(score)
    assert "**7.5**/10" in line
    assert "coherence" in line
    assert "identity" in line
    assert "novelty" in line
    assert "non-repetition" in line


# --- Test: build_journal_entry ---


def test_build_journal_entry_from_parallel_lists():
    """build_journal_entry creates a JournalEntry from dreams and scores."""
    dreams = [
        _make_dream(dream_type=DreamType.REPLAY),
        _make_dream(dream_type=DreamType.VOICE),
    ]
    scores = [
        _make_score(overall=8.0),
        _make_score(overall=5.0),
    ]
    entry = build_journal_entry(
        dreams, scores, min_quality=7.0, journal_date=JOURNAL_DATE,
    )

    assert entry.total_dreams == 2
    assert entry.selected_count == 1
    assert entry.rejected_count == 1
    assert entry.scored_dreams[0].selected_for_training is True
    assert entry.scored_dreams[1].selected_for_training is False


def test_build_journal_entry_default_date():
    """build_journal_entry defaults to today's date."""
    dreams = [_make_dream()]
    scores = [_make_score()]
    entry = build_journal_entry(dreams, scores)
    assert entry.journal_date is not None


# --- Test: write_journal ---


def test_write_journal_creates_file(tmp_path: Path):
    """write_journal writes a markdown file to disk."""
    entry = _make_entry()
    path = write_journal(entry, tmp_path)

    assert path.exists()
    assert path.suffix == ".md"
    assert "dream-journal-2026-04-01" in path.name
    content = path.read_text(encoding="utf-8")
    assert "# Dream Journal:" in content


def test_write_journal_creates_directory(tmp_path: Path):
    """write_journal creates the output directory if missing."""
    output_dir = tmp_path / "journals" / "dreams"
    entry = _make_entry()
    path = write_journal(entry, output_dir)

    assert output_dir.exists()
    assert path.exists()


# --- Test: JournalEntry properties ---


def test_mean_score():
    """Mean score is calculated correctly."""
    entry = _make_entry(dream_specs=[
        (DreamType.REPLAY, 8.0),
        (DreamType.VOICE, 6.0),
    ])
    assert entry.mean_score == pytest.approx(7.0)


def test_mean_score_empty():
    """Mean score is 0 for empty entries."""
    entry = JournalEntry(journal_date=JOURNAL_DATE)
    assert entry.mean_score == 0.0


def test_dreams_by_type_grouping():
    """dreams_by_type groups correctly."""
    entry = _make_entry(dream_specs=[
        (DreamType.REPLAY, 8.0),
        (DreamType.REPLAY, 7.0),
        (DreamType.VOICE, 9.0),
    ])
    by_type = entry.dreams_by_type
    assert len(by_type[DreamType.REPLAY]) == 2
    assert len(by_type[DreamType.VOICE]) == 1
