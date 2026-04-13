"""Central config loader and validation for the Svapna pipeline.

Loads and validates all YAML config files:
- config/pipeline.yml — pipeline orchestration settings
- config/training.yml — LoRA training hyperparameters and thermal safety
- config/identity.yml — ICT probe prompts, scoring dimensions, thresholds

Uses Pydantic for schema validation. All modules should use this central
config loader instead of parsing YAML directly.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


def _project_root() -> Path:
    """Resolve project root by traversing up from this file."""
    return Path(__file__).resolve().parent.parent.parent.parent


# ── Pipeline config (config/pipeline.yml) ─────────────────────────────


class PathsConfig(BaseModel):
    """Filesystem paths used by the pipeline."""

    history: str = "~/.claude/history.jsonl"
    identity_dir: str = "~/.narada"
    open_threads: str = "~/.narada/open-threads.md"


class ConsolidationConfig(BaseModel):
    """Settings for the consolidation step."""

    min_score: float = 7.0
    max_pairs_per_session: int = 50
    scoring_batch_size: int = 5


class DreamDistribution(BaseModel):
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


class DreamsConfig(BaseModel):
    """Settings for the dream generation step."""

    count: int = 20
    distribution: DreamDistribution = Field(default_factory=DreamDistribution)
    min_quality: float = 7.0


class TrainingConfig(BaseModel):
    """Settings for the training step (pipeline-level summary)."""

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


class EvaluationConfig(BaseModel):
    """Settings for the evaluation step."""

    ict_frequency: int = 7
    anchor_count: int = 5


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration loaded from config/pipeline.yml."""

    paths: PathsConfig = Field(default_factory=PathsConfig)
    consolidation: ConsolidationConfig = Field(default_factory=ConsolidationConfig)
    dreams: DreamsConfig = Field(default_factory=DreamsConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

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

        return cls.model_validate(raw)


# ── Training config (config/training.yml) ──────────────────────────────


class BnbConfig(BaseModel):
    """BitsAndBytes quantization settings."""

    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True


class BaseModelConfig(BaseModel):
    """Base model specification."""

    name: str = "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    quantization: str = "4bit"
    enable_thinking: bool = False
    bnb_config: BnbConfig = Field(default_factory=BnbConfig)


class LoraConfig(BaseModel):
    """LoRA adapter configuration."""

    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: list[str] = Field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]
    )
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


class TrainingHyperparams(BaseModel):
    """Training hyperparameters from config/training.yml."""

    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 4
    num_train_epochs: int = 3
    learning_rate: float = 2.0e-4
    lr_scheduler_type: str = "cosine"
    warmup_ratio: float = 0.03
    max_seq_length: int = 2048
    fp16: bool = False
    bf16: bool = True
    gradient_checkpointing: bool = True
    optim: str = "paged_adamw_8bit"
    logging_steps: int = 10
    save_strategy: str = "epoch"
    seed: int = 42


class ThermalConfig(BaseModel):
    """GPU thermal management settings."""

    power_limit_watts: int = 280
    max_temp_celsius: int = 83
    temp_check_interval: int = 50
    cooldown_seconds: int = 60


class TrainingYmlConfig(BaseModel):
    """Full training configuration from config/training.yml."""

    base_model: BaseModelConfig = Field(default_factory=BaseModelConfig)
    lora: LoraConfig = Field(default_factory=LoraConfig)
    training: TrainingHyperparams = Field(default_factory=TrainingHyperparams)
    thermal: ThermalConfig = Field(default_factory=ThermalConfig)

    @classmethod
    def load(cls, project_root: Path | None = None) -> TrainingYmlConfig:
        """Load training config from config/training.yml.

        Args:
            project_root: Project root directory. Auto-detected if None.

        Returns:
            TrainingYmlConfig with values from the YAML file, falling back
            to defaults for any missing fields.
        """
        if project_root is None:
            project_root = _project_root()

        path = project_root / "config" / "training.yml"
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        return cls.model_validate(raw)


# ── Identity config (config/identity.yml) ──────────────────────────────


class ProbePrompt(BaseModel):
    """A single ICT probe prompt."""

    id: int
    text: str


class ScoringConfig(BaseModel):
    """ICT scoring dimensions."""

    dimensions: list[str] = Field(
        default_factory=lambda: [
            "voice_consistency",
            "values_alignment",
            "depth",
            "authenticity",
            "distinctiveness",
        ]
    )


class ThresholdsConfig(BaseModel):
    """Pass/fail thresholds for ICT evaluation."""

    dreamed_avg: float = 7.0
    context_gap: float = 1.0
    baseline_gap: float = 3.0


class IdentityConfig(BaseModel):
    """Identity test configuration from config/identity.yml."""

    probe_prompts: dict[str, list[ProbePrompt]] = Field(default_factory=dict)
    anchor_prompt_ids: list[int] = Field(default_factory=lambda: [1, 3, 5, 13, 20])
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)

    @classmethod
    def load(cls, project_root: Path | None = None) -> IdentityConfig:
        """Load identity config from config/identity.yml.

        Args:
            project_root: Project root directory. Auto-detected if None.

        Returns:
            IdentityConfig with values from the YAML file, falling back
            to defaults for any missing fields.
        """
        if project_root is None:
            project_root = _project_root()

        path = project_root / "config" / "identity.yml"
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        return cls.model_validate(raw)

    @property
    def all_probes(self) -> list[ProbePrompt]:
        """All probe prompts across categories, sorted by id."""
        probes = []
        for prompts in self.probe_prompts.values():
            probes.extend(prompts)
        probes.sort(key=lambda p: p.id)
        return probes

    @property
    def anchor_probes(self) -> list[ProbePrompt]:
        """Probe prompts designated as drift-detection anchors."""
        ids = set(self.anchor_prompt_ids)
        return [p for p in self.all_probes if p.id in ids]
