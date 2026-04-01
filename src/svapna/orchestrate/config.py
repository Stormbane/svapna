"""Pipeline configuration for the nightly orchestrator.

Loads config/pipeline.yml and provides typed access to all pipeline
parameters. Each pipeline step pulls its own section from this config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _project_root() -> Path:
    """Resolve project root by traversing up from this file."""
    return Path(__file__).resolve().parent.parent.parent.parent


@dataclass
class ConsolidationConfig:
    """Settings for the consolidation step."""

    min_score: float = 7.0
    max_pairs_per_session: int = 50
    scoring_batch_size: int = 5


@dataclass
class DreamDistribution:
    """Distribution of dreams across types."""

    replay: int = 3
    recombination: int = 4
    open_thread: int = 5
    adversarial: int = 3
    novel_encounter: int = 3
    emotional: int = 2

    def to_dict(self) -> dict[str, int]:
        return {
            "replay": self.replay,
            "recombination": self.recombination,
            "open_thread": self.open_thread,
            "adversarial": self.adversarial,
            "novel_encounter": self.novel_encounter,
            "emotional": self.emotional,
        }

    @property
    def total(self) -> int:
        return sum(self.to_dict().values())


@dataclass
class DreamsConfig:
    """Settings for the dream generation step."""

    count: int = 20
    distribution: DreamDistribution = field(default_factory=DreamDistribution)
    min_quality: float = 7.0


@dataclass
class TrainingConfig:
    """Settings for the training step."""

    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    learning_rate: float = 2.0e-4
    num_epochs: int = 3
    batch_size: int = 1
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    warmup_ratio: float = 0.03
    gpu_power_limit_watts: int = 280
    max_gpu_temp_celsius: int = 83


@dataclass
class EvaluationConfig:
    """Settings for the evaluation step."""

    ict_frequency: int = 7
    anchor_count: int = 5


@dataclass
class PathsConfig:
    """Filesystem paths used by the pipeline."""

    history: str = "~/.claude/history.jsonl"
    identity_dir: str = "~/.claude/narada"
    open_threads: str = "~/.claude/narada/open-threads.md"


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration loaded from config/pipeline.yml."""

    paths: PathsConfig = field(default_factory=PathsConfig)
    consolidation: ConsolidationConfig = field(default_factory=ConsolidationConfig)
    dreams: DreamsConfig = field(default_factory=DreamsConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)

    @classmethod
    def load(cls, project_root: Path | None = None) -> PipelineConfig:
        """Load pipeline config from config/pipeline.yml.

        Args:
            project_root: Project root directory. Auto-detected if None.

        Returns:
            PipelineConfig with values from the YAML file, falling back
            to defaults for any missing fields.
        """
        if project_root is None:
            project_root = _project_root()

        pipeline_path = project_root / "config" / "pipeline.yml"
        if not pipeline_path.exists():
            return cls()

        with open(pipeline_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # Paths
        paths_raw = raw.get("paths", {})
        paths = PathsConfig(
            history=paths_raw.get("history", "~/.claude/history.jsonl"),
            identity_dir=paths_raw.get("identity_dir", "~/.claude/narada"),
            open_threads=paths_raw.get("open_threads", "~/.claude/narada/open-threads.md"),
        )

        # Consolidation
        cons_raw = raw.get("consolidation", {})
        consolidation = ConsolidationConfig(
            min_score=float(cons_raw.get("min_score", 7)),
            max_pairs_per_session=int(cons_raw.get("max_pairs_per_session", 50)),
            scoring_batch_size=int(cons_raw.get("scoring_batch_size", 5)),
        )

        # Dreams
        dreams_raw = raw.get("dreams", {})
        dist_raw = dreams_raw.get("distribution", {})
        distribution = DreamDistribution(
            replay=int(dist_raw.get("replay", 3)),
            recombination=int(dist_raw.get("recombination", 4)),
            open_thread=int(dist_raw.get("open_thread", 5)),
            adversarial=int(dist_raw.get("adversarial", 3)),
            novel_encounter=int(dist_raw.get("novel_encounter", 3)),
            emotional=int(dist_raw.get("emotional", 2)),
        )
        dreams = DreamsConfig(
            count=int(dreams_raw.get("count", 20)),
            distribution=distribution,
            min_quality=float(dreams_raw.get("min_quality", 7)),
        )

        # Training
        train_raw = raw.get("training", {})
        training = TrainingConfig(
            lora_r=int(train_raw.get("lora_r", 16)),
            lora_alpha=int(train_raw.get("lora_alpha", 32)),
            lora_dropout=float(train_raw.get("lora_dropout", 0.05)),
            learning_rate=float(train_raw.get("learning_rate", 2.0e-4)),
            num_epochs=int(train_raw.get("num_epochs", 3)),
            batch_size=int(train_raw.get("batch_size", 1)),
            gradient_accumulation_steps=int(train_raw.get("gradient_accumulation_steps", 4)),
            max_seq_length=int(train_raw.get("max_seq_length", 2048)),
            warmup_ratio=float(train_raw.get("warmup_ratio", 0.03)),
            gpu_power_limit_watts=int(train_raw.get("gpu_power_limit_watts", 280)),
            max_gpu_temp_celsius=int(train_raw.get("max_gpu_temp_celsius", 83)),
        )

        # Evaluation
        eval_raw = raw.get("evaluation", {})
        evaluation = EvaluationConfig(
            ict_frequency=int(eval_raw.get("ict_frequency", 7)),
            anchor_count=int(eval_raw.get("anchor_count", 5)),
        )

        return cls(
            paths=paths,
            consolidation=consolidation,
            dreams=dreams,
            training=training,
            evaluation=evaluation,
        )
