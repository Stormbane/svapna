"""Per-dream journal entry schema.

One DreamEntry per dream, persisted as YAML-frontmatter markdown:
  data/dreams/entries/YYYY/MM/DD-{id}.md
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from svapna.dream.journal import ScoredDream


@dataclass
class DreamEntry:
    """A single dream as a persistent journal record."""

    id: str
    entry_date: date
    dream_type: str
    content: str               # full first assistant turn
    turns: list[dict]          # all turns as {role, text}
    quality_score: float | None = None
    training_eligible: bool = False
    tags: list[str] = field(default_factory=list)
    source: str = "svapna.dream"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_scored_dream(
        cls,
        sd: ScoredDream,
        entry_date: date | None = None,
    ) -> DreamEntry:
        dream = sd.dream
        if entry_date is None:
            entry_date = dream.timestamp.date()

        content = ""
        for turn in dream.turns:
            if turn.role == "assistant":
                content = turn.text
                break

        id_src = f"{dream.dream_type.value}:{dream.timestamp.isoformat()}:{content[:64]}"
        dream_id = hashlib.sha1(id_src.encode()).hexdigest()[:12]

        return cls(
            id=dream_id,
            entry_date=entry_date,
            dream_type=dream.dream_type.value,
            content=content,
            turns=[{"role": t.role, "text": t.text} for t in dream.turns],
            quality_score=sd.score.overall if sd.score else None,
            training_eligible=sd.selected_for_training,
            source="svapna.dream",
            generated_at=dream.timestamp,
        )
