"""Test nightly pipeline orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from svapna.orchestrate.config import (
    ConsolidationConfig,
    DreamDistribution,
    DreamsConfig,
    EvaluationConfig,
    PathsConfig,
    PipelineConfig,
    TrainingConfig,
)
from svapna.orchestrate.nightly import (
    ALL_STEPS,
    RunState,
    Step,
    StepResult,
    _save_metrics_summary,
    load_run_state,
    run_consolidate,
    run_dream,
    run_evaluate,
    run_pipeline,
    run_prepare,
    run_score,
    run_train,
    save_run_state,
)


# --- Test data ---

def _default_config() -> PipelineConfig:
    return PipelineConfig(
        paths=PathsConfig(),
        consolidation=ConsolidationConfig(),
        dreams=DreamsConfig(),
        training=TrainingConfig(),
        evaluation=EvaluationConfig(),
    )


# --- Test: Step enum ---


def test_step_ordering():
    """Steps are ordered correctly for pipeline execution."""
    assert Step.CONSOLIDATE < Step.DREAM < Step.SCORE < Step.PREPARE < Step.TRAIN < Step.EVALUATE


def test_step_from_name():
    """Step.from_name resolves lowercase names."""
    assert Step.from_name("consolidate") == Step.CONSOLIDATE
    assert Step.from_name("dream") == Step.DREAM
    assert Step.from_name("train") == Step.TRAIN
    assert Step.from_name("evaluate") == Step.EVALUATE


def test_step_from_name_invalid():
    """Step.from_name raises ValueError for unknown steps."""
    with pytest.raises(ValueError, match="Unknown step"):
        Step.from_name("nonexistent")


def test_all_steps_contains_all_members():
    """ALL_STEPS has all 6 pipeline steps."""
    assert len(ALL_STEPS) == 6
    assert ALL_STEPS == [
        Step.CONSOLIDATE, Step.DREAM, Step.SCORE,
        Step.PREPARE, Step.TRAIN, Step.EVALUATE,
    ]


# --- Test: RunState persistence ---


def test_save_and_load_run_state(tmp_path):
    """RunState can be saved and loaded back."""
    state = RunState(
        run_date="2026-04-02",
        last_completed_step=3,
        step_results=[{"step": "consolidate", "status": "success"}],
        started_at="2026-04-02T00:00:00+00:00",
    )

    save_run_state(state, tmp_path)
    loaded = load_run_state(tmp_path, "2026-04-02")

    assert loaded is not None
    assert loaded.run_date == "2026-04-02"
    assert loaded.last_completed_step == 3
    assert len(loaded.step_results) == 1


def test_load_run_state_missing(tmp_path):
    """load_run_state returns None when no state file exists."""
    assert load_run_state(tmp_path, "2026-01-01") is None


def test_run_state_to_dict():
    """RunState serializes to dict correctly."""
    state = RunState(
        run_date="2026-04-02",
        last_completed_step=2,
        step_results=[],
        started_at="2026-04-02T00:00:00+00:00",
        finished_at="2026-04-02T01:00:00+00:00",
    )
    d = state.to_dict()
    assert d["run_date"] == "2026-04-02"
    assert d["last_completed_step"] == 2
    assert d["finished_at"] == "2026-04-02T01:00:00+00:00"


# --- Test: StepResult ---


def test_step_result_to_dict():
    """StepResult serializes with all fields."""
    result = StepResult(
        step="consolidate",
        status="success",
        started_at="2026-04-02T00:00:00+00:00",
        finished_at="2026-04-02T00:01:00+00:00",
        message="Done",
        metrics={"sessions": 5},
    )
    d = result.to_dict()
    assert d["step"] == "consolidate"
    assert d["status"] == "success"
    assert d["metrics"]["sessions"] == 5


# --- Test: Pipeline runs all steps in correct order ---


@patch("svapna.orchestrate.nightly.run_evaluate")
@patch("svapna.orchestrate.nightly.run_train")
@patch("svapna.orchestrate.nightly.run_prepare")
@patch("svapna.orchestrate.nightly.run_score")
@patch("svapna.orchestrate.nightly.run_dream")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_runs_all_steps_in_order(
    mock_consolidate, mock_dream, mock_score,
    mock_prepare, mock_train, mock_evaluate,
    tmp_path,
):
    """Pipeline runs all steps in the correct order."""
    call_order: list[str] = []

    def _make_result(name: str):
        def _runner(config, project_root):
            call_order.append(name)
            return StepResult(step=name, status="success", message="ok")
        return _runner

    mock_consolidate.side_effect = _make_result("consolidate")
    mock_dream.side_effect = _make_result("dream")
    mock_score.side_effect = _make_result("score")
    mock_prepare.side_effect = _make_result("prepare")
    mock_train.side_effect = _make_result("train")
    mock_evaluate.side_effect = _make_result("evaluate")

    config = _default_config()
    results = run_pipeline(config=config, project_root=tmp_path)

    assert len(results) == 6
    assert call_order == ["consolidate", "dream", "score", "prepare", "train", "evaluate"]
    assert all(r.status == "success" for r in results)


# --- Test: Each step can be run independently via CLI flags ---


@patch("svapna.orchestrate.nightly.run_dream")
def test_pipeline_runs_single_step(mock_dream, tmp_path):
    """Pipeline can run a single step when specified."""
    mock_dream.side_effect = lambda config, project_root: StepResult(
        step="dream", status="success", message="Generated 20 dreams",
    )

    config = _default_config()
    results = run_pipeline(
        steps=[Step.DREAM],
        config=config,
        project_root=tmp_path,
    )

    assert len(results) == 1
    assert results[0].step == "dream"
    mock_dream.assert_called_once()


@patch("svapna.orchestrate.nightly.run_prepare")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_runs_specific_steps(mock_consolidate, mock_prepare, tmp_path):
    """Pipeline runs only the specified steps."""
    mock_consolidate.side_effect = lambda c, p: StepResult(
        step="consolidate", status="success", message="ok",
    )
    mock_prepare.side_effect = lambda c, p: StepResult(
        step="prepare", status="success", message="ok",
    )

    config = _default_config()
    results = run_pipeline(
        steps=[Step.CONSOLIDATE, Step.PREPARE],
        config=config,
        project_root=tmp_path,
    )

    assert len(results) == 2
    assert results[0].step == "consolidate"
    assert results[1].step == "prepare"


# --- Test: Skips training step if --no-train flag is set ---


@patch("svapna.orchestrate.nightly.run_evaluate")
@patch("svapna.orchestrate.nightly.run_train")
@patch("svapna.orchestrate.nightly.run_prepare")
@patch("svapna.orchestrate.nightly.run_score")
@patch("svapna.orchestrate.nightly.run_dream")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_skips_training_with_no_train(
    mock_consolidate, mock_dream, mock_score,
    mock_prepare, mock_train, mock_evaluate,
    tmp_path,
):
    """Pipeline skips the TRAIN step when skip_training=True."""
    for mock in (mock_consolidate, mock_dream, mock_score, mock_prepare, mock_evaluate):
        mock.side_effect = lambda c, p, _n=mock: StepResult(
            step="step", status="success", message="ok",
        )

    config = _default_config()
    results = run_pipeline(
        skip_training=True,
        config=config,
        project_root=tmp_path,
    )

    # TRAIN should not appear in results
    step_names = [r.step for r in results]
    mock_train.assert_not_called()
    assert len(results) == 5  # 6 steps minus TRAIN


# --- Test: Logs progress to data/metrics/ ---


@patch("svapna.orchestrate.nightly.run_evaluate")
@patch("svapna.orchestrate.nightly.run_train")
@patch("svapna.orchestrate.nightly.run_prepare")
@patch("svapna.orchestrate.nightly.run_score")
@patch("svapna.orchestrate.nightly.run_dream")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_logs_to_metrics(
    mock_consolidate, mock_dream, mock_score,
    mock_prepare, mock_train, mock_evaluate,
    tmp_path,
):
    """Pipeline saves metrics summary to data/metrics/."""
    for mock in (mock_consolidate, mock_dream, mock_score, mock_prepare, mock_train, mock_evaluate):
        mock.side_effect = lambda c, p: StepResult(
            step="step", status="success", message="ok",
        )

    config = _default_config()
    run_pipeline(config=config, project_root=tmp_path)

    metrics_dir = tmp_path / "data" / "metrics"
    assert metrics_dir.exists()

    # Should have a nightly metrics file and a run-state file
    nightly_files = list(metrics_dir.glob("nightly-*.json"))
    state_files = list(metrics_dir.glob("run-state-*.json"))
    assert len(nightly_files) == 1
    assert len(state_files) == 1

    # Validate metrics content
    with open(nightly_files[0]) as f:
        metrics = json.load(f)
    assert metrics["total_steps"] == 6
    assert metrics["successful"] == 6
    assert metrics["failed"] == 0


def test_save_metrics_summary(tmp_path):
    """_save_metrics_summary writes valid JSON with expected structure."""
    results = [
        StepResult(step="consolidate", status="success", message="ok"),
        StepResult(step="dream", status="failed", message="API error"),
    ]

    path = _save_metrics_summary(results, tmp_path, "2026-04-02")

    assert path.exists()
    with open(path) as f:
        data = json.load(f)
    assert data["run_date"] == "2026-04-02"
    assert data["total_steps"] == 2
    assert data["successful"] == 1
    assert data["failed"] == 1


# --- Test: Can resume from a specific step if previous run was interrupted ---


@patch("svapna.orchestrate.nightly.run_evaluate")
@patch("svapna.orchestrate.nightly.run_train")
@patch("svapna.orchestrate.nightly.run_prepare")
@patch("svapna.orchestrate.nightly.run_score")
@patch("svapna.orchestrate.nightly.run_dream")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_resumes_from_last_completed(
    mock_consolidate, mock_dream, mock_score,
    mock_prepare, mock_train, mock_evaluate,
    tmp_path,
):
    """Pipeline resumes from the last completed step when resume=True."""
    call_order: list[str] = []

    def _make_result(name: str):
        def _runner(config, project_root):
            call_order.append(name)
            return StepResult(step=name, status="success", message="ok")
        return _runner

    mock_consolidate.side_effect = _make_result("consolidate")
    mock_dream.side_effect = _make_result("dream")
    mock_score.side_effect = _make_result("score")
    mock_prepare.side_effect = _make_result("prepare")
    mock_train.side_effect = _make_result("train")
    mock_evaluate.side_effect = _make_result("evaluate")

    config = _default_config()

    # Simulate a previous run that completed through SCORE (step 3)
    from datetime import date
    today = date.today().isoformat()
    state = RunState(
        run_date=today,
        last_completed_step=3,  # SCORE = 3
        step_results=[
            {"step": "consolidate", "status": "success"},
            {"step": "dream", "status": "success"},
            {"step": "score", "status": "success"},
        ],
        started_at="2026-04-02T00:00:00+00:00",
    )
    metrics_dir = tmp_path / "data" / "metrics"
    save_run_state(state, metrics_dir)

    # Resume pipeline
    results = run_pipeline(
        resume=True,
        config=config,
        project_root=tmp_path,
    )

    # Should only run steps 4, 5, 6 (PREPARE, TRAIN, EVALUATE)
    assert call_order == ["prepare", "train", "evaluate"]
    assert len(results) == 3
    mock_consolidate.assert_not_called()
    mock_dream.assert_not_called()
    mock_score.assert_not_called()


@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_resume_no_previous_state(mock_consolidate, tmp_path):
    """Resume with no previous state runs from the beginning."""
    mock_consolidate.side_effect = lambda c, p: StepResult(
        step="consolidate", status="success", message="ok",
    )

    config = _default_config()
    # Only run consolidate to keep test fast
    results = run_pipeline(
        steps=[Step.CONSOLIDATE],
        resume=True,
        config=config,
        project_root=tmp_path,
    )

    assert len(results) == 1
    mock_consolidate.assert_called_once()


# --- Test: Respects pipeline.yml configuration for all parameters ---


def test_config_loads_from_pipeline_yml(tmp_path):
    """PipelineConfig loads values from pipeline.yml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    pipeline_yml = config_dir / "pipeline.yml"
    pipeline_yml.write_text(
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
        "  learning_rate: 1.0e-4\n"
        "  num_epochs: 5\n"
        "\n"
        "evaluation:\n"
        "  ict_frequency: 14\n"
        "  anchor_count: 3\n"
    )

    config = PipelineConfig.load(project_root=tmp_path)

    # Consolidation
    assert config.consolidation.min_score == 8.0
    assert config.consolidation.max_pairs_per_session == 30
    assert config.consolidation.scoring_batch_size == 10

    # Dreams
    assert config.dreams.count == 15
    assert config.dreams.distribution.replay == 5
    assert config.dreams.distribution.adversarial == 2
    assert config.dreams.min_quality == 8.0

    # Training
    assert config.training.lora_r == 32
    assert config.training.learning_rate == 1.0e-4
    assert config.training.num_epochs == 5

    # Evaluation
    assert config.evaluation.ict_frequency == 14
    assert config.evaluation.anchor_count == 3


def test_config_defaults_without_pipeline_yml(tmp_path):
    """PipelineConfig uses defaults when pipeline.yml is missing."""
    config = PipelineConfig.load(project_root=tmp_path)

    assert config.consolidation.min_score == 7.0
    assert config.dreams.count == 20
    assert config.training.lora_r == 16
    assert config.evaluation.ict_frequency == 7


def test_config_partial_yml(tmp_path):
    """PipelineConfig handles partial YAML with defaults for missing fields."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    pipeline_yml = config_dir / "pipeline.yml"
    pipeline_yml.write_text(
        "consolidation:\n"
        "  min_score: 9\n"
    )

    config = PipelineConfig.load(project_root=tmp_path)

    assert config.consolidation.min_score == 9.0
    # Other sections should have defaults
    assert config.dreams.count == 20
    assert config.training.lora_r == 16


def test_config_paths_loaded(tmp_path):
    """PipelineConfig loads paths section from YAML."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    pipeline_yml = config_dir / "pipeline.yml"
    pipeline_yml.write_text(
        "paths:\n"
        "  history: /custom/history.jsonl\n"
        "  identity_dir: /custom/narada\n"
    )

    config = PipelineConfig.load(project_root=tmp_path)

    assert config.paths.history == "/custom/history.jsonl"
    assert config.paths.identity_dir == "/custom/narada"


def test_dream_distribution_total():
    """DreamDistribution.total sums all types."""
    dist = DreamDistribution(
        replay=3, recombination=4, open_thread=5,
        adversarial=3, novel_encounter=3, emotional=2,
    )
    assert dist.total == 20


# --- Test: Pipeline halts on failure ---


@patch("svapna.orchestrate.nightly.run_dream")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_pipeline_halts_on_failure(mock_consolidate, mock_dream, tmp_path):
    """Pipeline stops executing after a step fails."""
    mock_consolidate.side_effect = lambda c, p: StepResult(
        step="consolidate", status="failed", message="Ingest error",
    )
    mock_dream.side_effect = lambda c, p: StepResult(
        step="dream", status="success", message="ok",
    )

    config = _default_config()
    results = run_pipeline(
        steps=[Step.CONSOLIDATE, Step.DREAM],
        config=config,
        project_root=tmp_path,
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    mock_dream.assert_not_called()


# --- Test: Individual step runners ---


def test_run_consolidate_success(tmp_path):
    """run_consolidate returns success with metrics."""
    with patch("svapna.consolidate.ingest.ingest_all") as mock_ingest, \
         patch("svapna.consolidate.memories.convert_memory_files") as mock_memory:

        mock_session = MagicMock()
        mock_session.exchanges = [MagicMock(), MagicMock()]
        mock_ingest.return_value = [mock_session]
        mock_memory.return_value = [MagicMock(), MagicMock(), MagicMock()]

        config = _default_config()
        result = run_consolidate(config, tmp_path)

    assert result.status == "success"
    assert result.metrics["sessions"] == 1
    assert result.metrics["exchanges"] == 2
    assert result.metrics["memory_pairs"] == 3


def test_run_consolidate_handles_error(tmp_path):
    """run_consolidate returns failure on exception."""
    with patch("svapna.consolidate.ingest.ingest_all") as mock_ingest:
        mock_ingest.side_effect = RuntimeError("Ingest failed")

        config = _default_config()
        result = run_consolidate(config, tmp_path)

    assert result.status == "failed"
    assert "Ingest failed" in result.message


def test_run_train_with_training_data(tmp_path):
    """run_train succeeds when training data file exists."""
    training_dir = tmp_path / "data" / "training"
    training_dir.mkdir(parents=True)

    from datetime import date
    today = date.today().isoformat()
    training_file = training_dir / f"{today}.jsonl"
    training_file.write_text('{"messages": []}\n{"messages": []}\n')

    config = _default_config()
    result = run_train(config, tmp_path)

    assert result.status == "success"
    assert result.metrics["training_examples"] == 2


def test_run_train_skips_without_data(tmp_path):
    """run_train is skipped when no training data exists."""
    config = _default_config()
    result = run_train(config, tmp_path)

    assert result.status == "skipped"


def test_run_evaluate_skips_by_frequency(tmp_path):
    """run_evaluate skips when not on a frequency boundary."""
    eval_dir = tmp_path / "data" / "evaluations"
    eval_dir.mkdir(parents=True)

    # Create some existing reports (not on a frequency boundary)
    for i in range(3):
        (eval_dir / f"ict-report-2026-03-{20+i}.json").write_text("{}")

    config = _default_config()  # ict_frequency = 7
    result = run_evaluate(config, tmp_path)

    assert result.status == "skipped"
    assert "cycle 3" in result.message


def test_run_evaluate_runs_at_zero_reports(tmp_path):
    """run_evaluate runs when no previous reports exist (cycle 0)."""
    config = _default_config()
    result = run_evaluate(config, tmp_path)

    assert result.status == "success"
    assert result.metrics["cycle"] == 0


def test_run_evaluate_runs_on_frequency(tmp_path):
    """run_evaluate runs when report count is on a frequency boundary."""
    eval_dir = tmp_path / "data" / "evaluations"
    eval_dir.mkdir(parents=True)

    # Create exactly 7 reports (frequency = 7, 7 % 7 == 0)
    for i in range(7):
        (eval_dir / f"ict-report-2026-03-{20+i:02d}.json").write_text("{}")

    config = _default_config()
    result = run_evaluate(config, tmp_path)

    assert result.status == "success"


# --- Test: State file is updated after each step ---


@patch("svapna.orchestrate.nightly.run_dream")
@patch("svapna.orchestrate.nightly.run_consolidate")
def test_state_updated_incrementally(mock_consolidate, mock_dream, tmp_path):
    """Run state is saved after each step for resume capability."""
    mock_consolidate.side_effect = lambda c, p: StepResult(
        step="consolidate", status="success", message="ok",
    )
    mock_dream.side_effect = lambda c, p: StepResult(
        step="dream", status="success", message="ok",
    )

    config = _default_config()
    run_pipeline(
        steps=[Step.CONSOLIDATE, Step.DREAM],
        config=config,
        project_root=tmp_path,
    )

    from datetime import date
    today = date.today().isoformat()
    state = load_run_state(tmp_path / "data" / "metrics", today)

    assert state is not None
    assert state.last_completed_step == Step.DREAM.value
    assert len(state.step_results) == 2
    assert state.finished_at != ""
