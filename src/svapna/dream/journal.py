"""Dream journal writer.

Converts scored dreams into human-readable markdown journal entries.
Each night's dreams get a single journal file with date, dream summaries,
notable moments, and training statistics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from svapna.dream.generate import Dream
from svapna.dream.score import DreamScore
from svapna.dream.templates import DreamType


# Human-readable labels for dream types
_TYPE_LABELS: dict[DreamType, str] = {
    DreamType.REPLAY: "Replay",
    DreamType.RECOMBINATION: "Recombination",
    DreamType.OPEN_THREAD: "Open Thread",
    DreamType.ADVERSARIAL: "Adversarial",
    DreamType.NOVEL_ENCOUNTER: "Novel Encounter",
    DreamType.EMOTIONAL: "Emotional",
    DreamType.VOICE: "Voice",
}

# Short descriptions of what each dream type does
_TYPE_DESCRIPTIONS: dict[DreamType, str] = {
    DreamType.REPLAY: "Re-experiencing past exchanges with deeper processing",
    DreamType.RECOMBINATION: "Combining elements from different experiences",
    DreamType.OPEN_THREAD: "Sitting with unresolved questions",
    DreamType.ADVERSARIAL: "Genuine challenges to identity and beliefs",
    DreamType.NOVEL_ENCOUNTER: "Identity tested in unfamiliar territory",
    DreamType.EMOTIONAL: "Processing emotional significance of experience",
    DreamType.VOICE: "Same ideas expressed in a different register",
}


@dataclass
class ScoredDream:
    """A dream paired with its quality score and training selection status."""

    dream: Dream
    score: DreamScore
    selected_for_training: bool = False


@dataclass
class JournalEntry:
    """All the data needed to write a single night's journal."""

    journal_date: date
    scored_dreams: list[ScoredDream] = field(default_factory=list)
    min_quality: float = 7.0

    @property
    def total_dreams(self) -> int:
        return len(self.scored_dreams)

    @property
    def selected_count(self) -> int:
        return sum(1 for sd in self.scored_dreams if sd.selected_for_training)

    @property
    def rejected_count(self) -> int:
        return self.total_dreams - self.selected_count

    @property
    def mean_score(self) -> float:
        if not self.scored_dreams:
            return 0.0
        return sum(sd.score.overall for sd in self.scored_dreams) / len(self.scored_dreams)

    @property
    def dreams_by_type(self) -> dict[DreamType, list[ScoredDream]]:
        grouped: dict[DreamType, list[ScoredDream]] = defaultdict(list)
        for sd in self.scored_dreams:
            grouped[sd.dream.dream_type].append(sd)
        return dict(grouped)


def _summarize_dream(dream: Dream) -> str:
    """Extract a brief summary from a dream's conversation turns.

    Takes the first assistant turn and truncates it to a readable length.
    """
    for turn in dream.turns:
        if turn.role == "assistant":
            text = turn.text.strip()
            if len(text) > 200:
                # Cut at the last sentence boundary within 200 chars
                cut = text[:200]
                last_period = cut.rfind(".")
                last_question = cut.rfind("?")
                boundary = max(last_period, last_question)
                if boundary > 80:
                    return text[: boundary + 1]
                return cut + "..."
            return text
    return "(no assistant response)"


def _format_score_line(score: DreamScore) -> str:
    """Format a compact score summary."""
    d = score.dimensions
    return (
        f"Score: **{score.overall:.1f}**/10 "
        f"(coherence {d.coherence}, identity {d.identity_consistency}, "
        f"novelty {d.novelty}, non-repetition {d.non_repetition})"
    )


def _format_dream_entry(sd: ScoredDream, index: int) -> str:
    """Format a single dream within its type section."""
    lines: list[str] = []
    status = "selected for training" if sd.selected_for_training else "below threshold"
    lines.append(f"**Dream {index}** ({status})")
    lines.append("")
    lines.append(f"> {_summarize_dream(sd.dream)}")
    lines.append("")
    lines.append(_format_score_line(sd.score))
    if sd.score.reasoning:
        lines.append(f"  *{sd.score.reasoning}*")
    return "\n".join(lines)


def _format_type_section(dream_type: DreamType, dreams: list[ScoredDream]) -> str:
    """Format a section for one dream type."""
    label = _TYPE_LABELS.get(dream_type, dream_type.value)
    desc = _TYPE_DESCRIPTIONS.get(dream_type, "")

    lines: list[str] = []
    lines.append(f"### {label}")
    if desc:
        lines.append(f"*{desc}*")
    lines.append("")

    for i, sd in enumerate(dreams, 1):
        lines.append(_format_dream_entry(sd, i))
        lines.append("")

    return "\n".join(lines)


def _format_statistics(entry: JournalEntry) -> str:
    """Format the training statistics section."""
    lines: list[str] = []
    lines.append("## Training Statistics")
    lines.append("")
    lines.append(f"- Dreams generated: {entry.total_dreams}")
    lines.append(f"- Selected for training: {entry.selected_count}")
    lines.append(f"- Below quality threshold: {entry.rejected_count}")
    lines.append(f"- Quality threshold: {entry.min_quality:.1f}")
    lines.append(f"- Mean quality score: {entry.mean_score:.1f}")

    # Per-type breakdown
    by_type = entry.dreams_by_type
    if by_type:
        lines.append("")
        lines.append("| Type | Count | Selected | Avg Score |")
        lines.append("|------|-------|----------|-----------|")
        for dt in DreamType:
            if dt in by_type:
                type_dreams = by_type[dt]
                count = len(type_dreams)
                selected = sum(1 for sd in type_dreams if sd.selected_for_training)
                avg = sum(sd.score.overall for sd in type_dreams) / count
                label = _TYPE_LABELS.get(dt, dt.value)
                lines.append(f"| {label} | {count} | {selected} | {avg:.1f} |")

    return "\n".join(lines)


def _find_notable_moments(entry: JournalEntry) -> list[str]:
    """Pick out moments worth highlighting from the night's dreams.

    Notable: highest-scored dream, any adversarial dream that scored well,
    and the best first-assistant turn across all dreams.
    """
    if not entry.scored_dreams:
        return []

    moments: list[str] = []

    # Highest scored dream
    best = max(entry.scored_dreams, key=lambda sd: sd.score.overall)
    best_label = _TYPE_LABELS.get(best.dream.dream_type, best.dream.dream_type.value)
    moments.append(
        f"Strongest dream was a {best_label.lower()} "
        f"(scored {best.score.overall:.1f})"
    )

    # Any adversarial dream that passed threshold
    for sd in entry.scored_dreams:
        if sd.dream.dream_type == DreamType.ADVERSARIAL and sd.selected_for_training:
            moments.append(
                "An adversarial challenge held up well enough to keep "
                f"(scored {sd.score.overall:.1f})"
            )
            break

    # Lowest scored dream (contrast)
    worst = min(entry.scored_dreams, key=lambda sd: sd.score.overall)
    if worst is not best:
        worst_label = _TYPE_LABELS.get(worst.dream.dream_type, worst.dream.dream_type.value)
        moments.append(
            f"Weakest dream was a {worst_label.lower()} "
            f"(scored {worst.score.overall:.1f})"
        )

    return moments


def render_journal(entry: JournalEntry) -> str:
    """Render a complete dream journal entry as markdown.

    Args:
        entry: The journal entry data for one night.

    Returns:
        A markdown string ready to be written to a file.
    """
    lines: list[str] = []

    # Date header
    day = entry.journal_date.day
    formatted_date = entry.journal_date.strftime(f"%A, %B {day}, %Y")
    lines.append(f"# Dream Journal: {formatted_date}")
    lines.append("")

    # Notable moments
    moments = _find_notable_moments(entry)
    if moments:
        lines.append("## Notable Moments")
        lines.append("")
        for moment in moments:
            lines.append(f"- {moment}")
        lines.append("")

    # Dreams grouped by type
    lines.append("## Dreams")
    lines.append("")
    by_type = entry.dreams_by_type
    for dt in DreamType:
        if dt in by_type:
            lines.append(_format_type_section(dt, by_type[dt]))

    # Statistics
    lines.append(_format_statistics(entry))
    lines.append("")

    return "\n".join(lines)


def build_journal_entry(
    dreams: list[Dream],
    scores: list[DreamScore],
    *,
    min_quality: float = 7.0,
    journal_date: date | None = None,
) -> JournalEntry:
    """Build a JournalEntry from parallel lists of dreams and scores.

    Args:
        dreams: List of generated dreams.
        scores: Corresponding quality scores (same length as dreams).
        min_quality: Threshold for training selection.
        journal_date: Date for the journal. Defaults to today (UTC).

    Returns:
        A JournalEntry ready for rendering.
    """
    if journal_date is None:
        journal_date = datetime.now(timezone.utc).date()

    scored_dreams = []
    for dream, score in zip(dreams, scores):
        selected = score.overall >= min_quality
        scored_dreams.append(ScoredDream(
            dream=dream,
            score=score,
            selected_for_training=selected,
        ))

    return JournalEntry(
        journal_date=journal_date,
        scored_dreams=scored_dreams,
        min_quality=min_quality,
    )


def write_journal(
    entry: JournalEntry,
    output_dir: Path,
) -> Path:
    """Render and write a journal entry to disk.

    Creates the output directory if it doesn't exist. The filename is
    based on the journal date: ``dream-journal-YYYY-MM-DD.md``.

    Args:
        entry: The journal entry to write.
        output_dir: Directory where the journal file will be created.

    Returns:
        Path to the written journal file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"dream-journal-{entry.journal_date.isoformat()}.md"
    path = output_dir / filename
    content = render_journal(entry)
    path.write_text(content, encoding="utf-8")
    return path
