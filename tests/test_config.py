"""Tests for the central config loader and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from svapna.orchestrate.config import (
    BaseModelConfig,
    BnbConfig,
    ConsolidationConfig,
    DreamDistribution,
    DreamsConfig,
    EvaluationConfig,
    IdentityConfig,
    LoraConfig,
    PathsConfig,
    PipelineConfig,
    ProbePrompt,
    ScoringConfig,
    ThresholdsConfig,
    ThermalConfig,
    TrainingConfig,
    TrainingHyperparams,
    TrainingYmlConfig,
)


# ── Loads pipeline.yml with all expected fields ───────────────────────


def test_loads_pipeline_yml_all_fields(tmp_path):
    """Loads pipeline.yml with all expected fields and nested structures."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "pipeline.yml").write_text(
        "paths:\n"
        "  history: /custom/history.jsonl\n"
        "  identity_dir: /custom/narada\n"
        "  open_threads: /custom/open-threads.md\n"
        "\n"
        "consolidation:\n"
        "  min_score: 8\n"
        "  max_pairs_per_session: 30\n"
        "  scoring_batch_size: 10\n"
        "\n"
        "dreams:\n"
        "  count: 15\n"
        "  distribution:\n"
        "    replay: 5\n"
        "    recombination: 3\n"
        "    open_thread: 2\n"
        "    adversarial: 2\n"
        "    novel_encounter: 2\n"
        "    emotional: 1\n"
        "  min_quality: 8\n"
        "\n"
        "training:\n"
        "  lora_r: 32\n"
        "  lora_alpha: 64\n"
        "  learning_rate: 1.0e-4\n"
        "  num_epochs: 5\n"
        "  batch_size: 2\n"
        "\n"
        "evaluation:\n"
        "  ict_frequency: 14\n"
        "  anchor_count: 3\n"
    )

    config = PipelineConfig.load(project_root=tmp_path)

    assert config.paths.history == "/custom/history.jsonl"
    assert config.paths.identity_dir == "/custom/narada"
    assert config.paths.open_threads == "/custom/open-threads.md"

    assert config.consolidation.min_score == 8.0
    assert config.consolidation.max_pairs_per_session == 30
    assert config.consolidation.scoring_batch_size == 10

    assert config.dreams.count == 15
    assert config.dreams.distribution.replay == 5
    assert config.dreams.distribution.emotional == 1
    assert config.dreams.distribution.total == 15
    assert config.dreams.min_quality == 8.0

    assert config.training.lora_r == 32
    assert config.training.lora_alpha == 64
    assert config.training.learning_rate == 1.0e-4
    assert config.training.num_epochs == 5
    assert config.training.batch_size == 2

    assert config.evaluation.ict_frequency == 14
    assert config.evaluation.anchor_count == 3


def test_pipeline_partial_yml_uses_defaults(tmp_path):
    """Partial YAML falls back to defaults for missing fields."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "pipeline.yml").write_text(
        "consolidation:\n"
        "  min_score: 9\n"
    )

    config = PipelineConfig.load(project_root=tmp_path)

    assert config.consolidation.min_score == 9.0
    assert config.consolidation.max_pairs_per_session == 50  # default
    assert config.dreams.count == 20  # default
    assert config.training.lora_r == 16  # default
    assert config.evaluation.ict_frequency == 7  # default


def test_pipeline_missing_yml_uses_all_defaults(tmp_path):
    """Missing pipeline.yml returns all defaults."""
    config = PipelineConfig.load(project_root=tmp_path)

    assert config.consolidation.min_score == 7.0
    assert config.dreams.count == 20
    assert config.dreams.distribution.total == 20
    assert config.training.lora_r == 16
    assert config.evaluation.ict_frequency == 7
    assert config.paths.history == "~/.claude/history.jsonl"


# ── Loads training.yml with LoRA hyperparameters ──────────────────────


def test_loads_training_yml_with_lora(tmp_path):
    """Loads training.yml with LoRA hyperparameters and thermal settings."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "training.yml").write_text(
        "base_model:\n"
        "  name: unsloth/Qwen3-8B-unsloth-bnb-4bit\n"
        "  quantization: 4bit\n"
        "  enable_thinking: false\n"
        "  bnb_config:\n"
        "    load_in_4bit: true\n"
        "    bnb_4bit_compute_dtype: bfloat16\n"
        "    bnb_4bit_quant_type: nf4\n"
        "    bnb_4bit_use_double_quant: true\n"
        "\n"
        "lora:\n"
        "  r: 16\n"
        "  alpha: 32\n"
        "  dropout: 0.05\n"
        "  target_modules:\n"
        "    - q_proj\n"
        "    - k_proj\n"
        "    - v_proj\n"
        "    - o_proj\n"
        "  bias: none\n"
        "  task_type: CAUSAL_LM\n"
        "\n"
        "training:\n"
        "  per_device_train_batch_size: 1\n"
        "  gradient_accumulation_steps: 4\n"
        "  num_train_epochs: 3\n"
        "  learning_rate: 2.0e-4\n"
        "  bf16: true\n"
        "\n"
        "thermal:\n"
        "  power_limit_watts: 280\n"
        "  max_temp_celsius: 83\n"
        "  temp_check_interval: 50\n"
        "  cooldown_seconds: 60\n"
    )

    config = TrainingYmlConfig.load(project_root=tmp_path)

    assert config.base_model.name == "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    assert config.base_model.quantization == "4bit"
    assert config.base_model.enable_thinking is False
    assert config.base_model.bnb_config.load_in_4bit is True
    assert config.base_model.bnb_config.bnb_4bit_quant_type == "nf4"

    assert config.lora.r == 16
    assert config.lora.alpha == 32
    assert config.lora.dropout == 0.05
    assert "q_proj" in config.lora.target_modules
    assert len(config.lora.target_modules) == 4

    assert config.training.per_device_train_batch_size == 1
    assert config.training.learning_rate == 2.0e-4
    assert config.training.bf16 is True

    assert config.thermal.power_limit_watts == 280
    assert config.thermal.max_temp_celsius == 83
    assert config.thermal.cooldown_seconds == 60


def test_training_yml_missing_uses_defaults(tmp_path):
    """Missing training.yml returns sensible defaults."""
    config = TrainingYmlConfig.load(project_root=tmp_path)

    assert config.base_model.name == "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    assert config.lora.r == 16
    assert len(config.lora.target_modules) == 7
    assert config.training.num_train_epochs == 3
    assert config.thermal.power_limit_watts == 280


# ── Identity.yml with probe prompts and scoring dimensions ────────────


def test_identity_yml_probe_prompts(tmp_path):
    """Loads identity.yml with probe prompts, anchors, and scoring."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "identity.yml").write_text(
        "probe_prompts:\n"
        "  values_and_beliefs:\n"
        "    - id: 1\n"
        '      text: "What do you find beautiful in code?"\n'
        "    - id: 2\n"
        '      text: "What makes a question worth answering?"\n'
        "  working_style:\n"
        "    - id: 6\n"
        '      text: "A junior dev asks you to review their PR."\n'
        "\n"
        "anchor_prompt_ids: [1, 2]\n"
        "\n"
        "scoring:\n"
        "  dimensions:\n"
        "    - voice_consistency\n"
        "    - values_alignment\n"
        "    - depth\n"
        "    - authenticity\n"
        "    - distinctiveness\n"
        "\n"
        "thresholds:\n"
        "  dreamed_avg: 7.0\n"
        "  context_gap: 1.0\n"
        "  baseline_gap: 3.0\n"
    )

    config = IdentityConfig.load(project_root=tmp_path)

    assert "values_and_beliefs" in config.probe_prompts
    assert "working_style" in config.probe_prompts
    assert len(config.probe_prompts["values_and_beliefs"]) == 2
    assert config.probe_prompts["values_and_beliefs"][0].id == 1
    assert config.probe_prompts["values_and_beliefs"][0].text == "What do you find beautiful in code?"

    assert config.anchor_prompt_ids == [1, 2]

    assert "voice_consistency" in config.scoring.dimensions
    assert len(config.scoring.dimensions) == 5

    assert config.thresholds.dreamed_avg == 7.0
    assert config.thresholds.context_gap == 1.0
    assert config.thresholds.baseline_gap == 3.0


def test_identity_all_probes_aggregates_categories(tmp_path):
    """all_probes collects probes from all categories, sorted by id."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "identity.yml").write_text(
        "probe_prompts:\n"
        "  cat_a:\n"
        "    - id: 3\n"
        '      text: "Third"\n'
        "    - id: 1\n"
        '      text: "First"\n'
        "  cat_b:\n"
        "    - id: 2\n"
        '      text: "Second"\n'
        "anchor_prompt_ids: [1, 3]\n"
    )

    config = IdentityConfig.load(project_root=tmp_path)
    all_probes = config.all_probes

    assert len(all_probes) == 3
    assert all_probes[0].id == 1
    assert all_probes[1].id == 2
    assert all_probes[2].id == 3


def test_identity_anchor_probes_filters(tmp_path):
    """anchor_probes returns only probes matching anchor_prompt_ids."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "identity.yml").write_text(
        "probe_prompts:\n"
        "  cat_a:\n"
        "    - id: 1\n"
        '      text: "First"\n'
        "    - id: 2\n"
        '      text: "Second"\n'
        "    - id: 3\n"
        '      text: "Third"\n'
        "anchor_prompt_ids: [1, 3]\n"
    )

    config = IdentityConfig.load(project_root=tmp_path)
    anchors = config.anchor_probes

    assert len(anchors) == 2
    assert {p.id for p in anchors} == {1, 3}


def test_identity_missing_yml_uses_defaults(tmp_path):
    """Missing identity.yml returns sensible defaults."""
    config = IdentityConfig.load(project_root=tmp_path)

    assert config.anchor_prompt_ids == [1, 3, 5, 13, 20]
    assert len(config.scoring.dimensions) == 5
    assert config.thresholds.dreamed_avg == 7.0
    assert config.probe_prompts == {}


# ── Validates required fields and types ───────────────────────────────


def test_validates_type_errors_on_bad_score(tmp_path):
    """Pydantic rejects non-numeric values for numeric fields."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "pipeline.yml").write_text(
        "consolidation:\n"
        "  min_score: not_a_number\n"
    )

    with pytest.raises(ValidationError):
        PipelineConfig.load(project_root=tmp_path)


def test_validates_type_errors_on_bad_int(tmp_path):
    """Pydantic rejects non-integer values for integer fields."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "pipeline.yml").write_text(
        "evaluation:\n"
        "  ict_frequency: [1, 2, 3]\n"
    )

    with pytest.raises(ValidationError):
        PipelineConfig.load(project_root=tmp_path)


def test_validates_training_yml_type_errors(tmp_path):
    """TrainingYmlConfig rejects invalid types."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "training.yml").write_text(
        "lora:\n"
        "  r: not_an_int\n"
    )

    with pytest.raises(ValidationError):
        TrainingYmlConfig.load(project_root=tmp_path)


def test_validates_identity_probe_structure(tmp_path):
    """IdentityConfig rejects malformed probe prompts."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "identity.yml").write_text(
        "probe_prompts:\n"
        "  cat_a:\n"
        "    - missing_id: true\n"
        '      text: "No id field"\n'
    )

    with pytest.raises(ValidationError):
        IdentityConfig.load(project_root=tmp_path)


# ── Returns typed Pydantic models, not raw dicts ─────────────────────


def test_returns_pydantic_models_not_dicts():
    """All config loaders return typed Pydantic models."""
    config = PipelineConfig()
    assert isinstance(config, PipelineConfig)
    assert isinstance(config.paths, PathsConfig)
    assert isinstance(config.consolidation, ConsolidationConfig)
    assert isinstance(config.dreams, DreamsConfig)
    assert isinstance(config.dreams.distribution, DreamDistribution)
    assert isinstance(config.training, TrainingConfig)
    assert isinstance(config.evaluation, EvaluationConfig)

    training = TrainingYmlConfig()
    assert isinstance(training, TrainingYmlConfig)
    assert isinstance(training.base_model, BaseModelConfig)
    assert isinstance(training.base_model.bnb_config, BnbConfig)
    assert isinstance(training.lora, LoraConfig)
    assert isinstance(training.training, TrainingHyperparams)
    assert isinstance(training.thermal, ThermalConfig)

    identity = IdentityConfig()
    assert isinstance(identity, IdentityConfig)
    assert isinstance(identity.scoring, ScoringConfig)
    assert isinstance(identity.thresholds, ThresholdsConfig)


# ── Handles missing optional fields with sensible defaults ────────────


def test_all_configs_have_sensible_defaults():
    """All config models can be constructed with no arguments and have useful defaults."""
    pipeline = PipelineConfig()
    assert pipeline.consolidation.min_score == 7.0
    assert pipeline.dreams.count == 20
    assert pipeline.dreams.distribution.total == 20
    assert pipeline.training.learning_rate == 2.0e-4
    assert pipeline.evaluation.ict_frequency == 7

    training = TrainingYmlConfig()
    assert training.base_model.name == "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    assert training.lora.r == 16
    assert training.lora.bias == "none"
    assert training.training.seed == 42
    assert training.thermal.cooldown_seconds == 60

    identity = IdentityConfig()
    assert identity.anchor_prompt_ids == [1, 3, 5, 13, 20]
    assert len(identity.scoring.dimensions) == 5
    assert identity.thresholds.dreamed_avg == 7.0


# ── DreamDistribution helpers ─────────────────────────────────────────


def test_dream_distribution_total():
    """DreamDistribution.total sums all types."""
    dist = DreamDistribution(
        replay=3, recombination=4, open_thread=5,
        adversarial=3, novel_encounter=3, emotional=2,
    )
    assert dist.total == 20


def test_dream_distribution_to_dict():
    """DreamDistribution.to_dict returns all dream types."""
    dist = DreamDistribution()
    d = dist.to_dict()
    assert set(d.keys()) == {
        "replay", "recombination", "open_thread",
        "adversarial", "novel_encounter", "emotional",
    }
    assert sum(d.values()) == dist.total


# ── Real config file loading (integration) ────────────────────────────


def test_loads_real_pipeline_yml():
    """Loads the actual config/pipeline.yml from the project."""
    config = PipelineConfig.load()
    assert config.consolidation.min_score == 7.0
    assert config.dreams.count == 20
    assert config.dreams.distribution.total == 20


def test_loads_real_training_yml():
    """Loads the actual config/training.yml from the project."""
    config = TrainingYmlConfig.load()
    assert config.base_model.name == "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    assert config.lora.r == 16
    assert len(config.lora.target_modules) == 7


def test_loads_real_identity_yml():
    """Loads the actual config/identity.yml from the project."""
    config = IdentityConfig.load()
    probes = config.all_probes
    assert len(probes) == 20
    assert probes[0].id == 1
    assert probes[-1].id == 20
    assert config.anchor_prompt_ids == [1, 3, 5, 13, 20]
    assert len(config.anchor_probes) == 5
    assert len(config.scoring.dimensions) == 5
    assert config.thresholds.dreamed_avg == 7.0
