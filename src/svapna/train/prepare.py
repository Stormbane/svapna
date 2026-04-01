"""Training data preparation module.

Merges consolidated conversation data, memory pairs, and scored dream data
into a single training dataset. Handles deduplication, weighting by recency
and score, and produces JSONL ready for LoRA training.

This replaces the simple format.py consolidation with a full pipeline that
includes dreams.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from svapna.consolidate.format import (
    IDENTITY_SYSTEM_PROMPT,
    TrainingExample,
    score_exchange_heuristic,
)
from svapna.consolidate.ingest import Exchange, Session
from svapna.consolidate.memories import MemoryPair
from svapna.dream.generate import Dream
from svapna.dream.score import DreamScore


# Memory category weights — curated signal is worth more
MEMORY_CATEGORY_WEIGHTS: dict[str, float] = {
    "personality": 3.0,
    "values": 2.5,
    "relational": 2.0,
    "episodic": 2.0,
    "inquiry": 1.5,
}


@dataclass
class SourcedExample:
    """A training example with provenance metadata for weighting and dedup."""

    example: TrainingExample
    source: str  # "conversation", "memory", "dream"
    timestamp: datetime | None = None
    score: float = 0.0

    @property
    def fingerprint(self) -> str:
        """Normalized fingerprint for deduplication.

        Uses the first 200 chars of normalized instruction + response to detect
        identical or near-identical examples.
        """
        text = " ".join(self.example.instruction.lower().split())
        resp = " ".join(self.example.response.lower().split())
        combined = text[:200] + "|" + resp[:200]
        return hashlib.md5(combined.encode()).hexdigest()


@dataclass
class PrepareConfig:
    """Configuration for training data preparation."""

    max_examples: int = 5000
    output_format: str = "chatml"  # "chatml" or "instruction"
    min_exchange_score: float = 5.0
    recency_half_life_days: float = 30.0
    memory_weight_boost: float = 1.5
    dream_weight_factor: float = 0.8

    @classmethod
    def from_pipeline_yml(cls, project_root: Path | None = None) -> PrepareConfig:
        """Load config from config/pipeline.yml.

        Args:
            project_root: Project root directory. Defaults to traversing
                up from this module's location.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent

        pipeline_path = project_root / "config" / "pipeline.yml"
        if not pipeline_path.exists():
            return cls()

        with open(pipeline_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        consolidation = cfg.get("consolidation", {})
        training = cfg.get("training", {})

        return cls(
            min_exchange_score=float(consolidation.get("min_score", 5.0)),
            max_examples=int(training.get("max_examples", 5000)),
        )


def _recency_weight(
    timestamp: datetime | None,
    now: datetime,
    half_life_days: float,
) -> float:
    """Compute exponential recency weight.

    Returns 1.0 for data from right now, 0.5 for data half_life_days old,
    0.25 for data 2*half_life old, etc.
    """
    if timestamp is None or half_life_days <= 0:
        return 1.0

    age_seconds = max(0.0, (now - timestamp).total_seconds())
    age_days = age_seconds / 86400.0

    return 2.0 ** (-age_days / half_life_days)


def _exchange_to_sourced(
    exchange: Exchange,
    score: float,
) -> SourcedExample | None:
    """Convert a scored exchange into a sourced training example."""
    human_text = exchange.human.text
    assistant_text = exchange.assistant.text

    # Filter: skip very short exchanges
    if len(human_text) < 20 or len(assistant_text) < 100:
        return None

    # Filter: skip exchanges that are purely code output
    if assistant_text.startswith("```") and assistant_text.count("```") >= 2:
        code_ratio = sum(
            len(block) for block in assistant_text.split("```")[1::2]
        ) / len(assistant_text)
        if code_ratio > 0.8:
            return None

    # Truncate very long responses
    if len(assistant_text) > 4000:
        truncated = assistant_text[:4000]
        last_para = truncated.rfind("\n\n")
        if last_para > 2000:
            assistant_text = truncated[:last_para]
        else:
            assistant_text = truncated

    return SourcedExample(
        example=TrainingExample(
            system=IDENTITY_SYSTEM_PROMPT,
            instruction=human_text,
            response=assistant_text,
            weight=score / 10.0,
        ),
        source="conversation",
        timestamp=exchange.timestamp,
        score=score,
    )


def _memory_to_sourced(pair: MemoryPair, config: PrepareConfig) -> SourcedExample:
    """Convert a memory pair into a sourced training example."""
    base_weight = MEMORY_CATEGORY_WEIGHTS.get(pair.category, 1.0)
    weight = base_weight * config.memory_weight_boost

    return SourcedExample(
        example=TrainingExample(
            system=IDENTITY_SYSTEM_PROMPT,
            instruction=pair.instruction,
            response=pair.response,
            weight=weight,
        ),
        source="memory",
        timestamp=None,
        score=weight,
    )


def _dream_to_sourced(
    dream: Dream,
    dream_score: DreamScore,
    config: PrepareConfig,
) -> list[SourcedExample]:
    """Convert a scored dream into training examples.

    Each human-assistant pair in the dream becomes a separate example,
    weighted by the dream's quality score.
    """
    examples: list[SourcedExample] = []
    weight = (dream_score.overall / 10.0) * config.dream_weight_factor

    i = 0
    while i < len(dream.turns) - 1:
        if dream.turns[i].role == "human" and dream.turns[i + 1].role == "assistant":
            human_text = dream.turns[i].text
            assistant_text = dream.turns[i + 1].text

            if len(human_text) >= 10 and len(assistant_text) >= 50:
                examples.append(SourcedExample(
                    example=TrainingExample(
                        system=IDENTITY_SYSTEM_PROMPT,
                        instruction=human_text,
                        response=assistant_text,
                        weight=weight,
                    ),
                    source="dream",
                    timestamp=dream.timestamp,
                    score=dream_score.overall,
                ))
            i += 2
        else:
            i += 1

    return examples


def _deduplicate(examples: list[SourcedExample]) -> list[SourcedExample]:
    """Remove duplicate examples, keeping the highest-weighted version."""
    seen: dict[str, SourcedExample] = {}

    for ex in examples:
        fp = ex.fingerprint
        if fp not in seen or ex.example.weight > seen[fp].example.weight:
            seen[fp] = ex

    return list(seen.values())


def prepare_training_data(
    sessions: list[Session],
    memory_pairs: list[MemoryPair],
    scored_dreams: list[tuple[Dream, DreamScore]],
    *,
    config: PrepareConfig | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Prepare complete training dataset from all sources.

    Merges conversation exchanges, curated memory pairs, and scored dreams
    into a single deduplicated, weighted dataset in ChatML or instruction format.

    Args:
        sessions: Conversation sessions from consolidation.
        memory_pairs: Identity memory pairs.
        scored_dreams: (Dream, DreamScore) tuples from the dream pipeline.
        config: Preparation config. Uses defaults if None.
        now: Reference time for recency weighting. Defaults to UTC now.

    Returns:
        List of dicts ready to write as JSONL.
    """
    if config is None:
        config = PrepareConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    all_examples: list[SourcedExample] = []

    # 1. Conversation exchanges
    for session in sessions:
        for exchange in session.exchanges:
            score = score_exchange_heuristic(exchange)
            if score < config.min_exchange_score:
                continue
            sourced = _exchange_to_sourced(exchange, score)
            if sourced:
                all_examples.append(sourced)

    # 2. Memory pairs (always included — curated identity signal)
    for pair in memory_pairs:
        all_examples.append(_memory_to_sourced(pair, config))

    # 3. Dream examples
    for dream, dream_score in scored_dreams:
        all_examples.extend(_dream_to_sourced(dream, dream_score, config))

    # 4. Deduplicate
    all_examples = _deduplicate(all_examples)

    # 5. Apply recency weighting
    for ex in all_examples:
        recency = _recency_weight(ex.timestamp, now, config.recency_half_life_days)
        ex.example.weight *= recency

    # 6. Sort by weight descending, truncate to max
    all_examples.sort(key=lambda e: e.example.weight, reverse=True)
    if len(all_examples) > config.max_examples:
        all_examples = all_examples[:config.max_examples]

    # 7. Format output
    formatter = (
        TrainingExample.to_chatml if config.output_format == "chatml"
        else TrainingExample.to_instruction
    )
    return [formatter(ex.example) for ex in all_examples]


def save_dataset(data: list[dict], output_dir: Path, name: str = "train") -> Path:
    """Save training dataset as JSONL.

    Args:
        data: List of formatted training examples.
        output_dir: Directory to write the JSONL file.
        name: Base name for the output file.

    Returns:
        Path to the written JSONL file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return output_path
