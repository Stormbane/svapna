"""Nightly pipeline orchestrator.

Runs the full nightly pipeline: consolidate -> dream -> score -> prepare
training data -> (optionally) train -> evaluate. Each step logs progress
and can be resumed if interrupted.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

from svapna.orchestrate.config import PipelineConfig

logger = logging.getLogger(__name__)


class Step(IntEnum):
    """Pipeline steps in execution order."""

    CONSOLIDATE = 1
    DREAM = 2
    SCORE = 3
    PREPARE = 4
    TRAIN = 5
    EVALUATE = 6

    @classmethod
    def from_name(cls, name: str) -> Step:
        """Resolve a step from its lowercase name.

        Args:
            name: Step name (e.g. "consolidate", "dream").

        Returns:
            The matching Step enum member.

        Raises:
            ValueError: If the name doesn't match any step.
        """
        name_upper = name.upper()
        if name_upper in cls.__members__:
            return cls[name_upper]
        raise ValueError(
            f"Unknown step: {name!r}. "
            f"Valid steps: {', '.join(s.name.lower() for s in cls)}"
        )


ALL_STEPS: list[Step] = list(Step)


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    step: str
    status: str  # "success", "skipped", "failed"
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "message": self.message,
            "metrics": self.metrics,
        }


@dataclass
class RunState:
    """Persistent state for a pipeline run, enabling resume after interruption."""

    run_date: str
    last_completed_step: int = 0  # Step int value; 0 = none completed
    step_results: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "last_completed_step": self.last_completed_step,
            "step_results": self.step_results,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        return cls(
            run_date=data["run_date"],
            last_completed_step=data.get("last_completed_step", 0),
            step_results=data.get("step_results", []),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


# --- State persistence ---


def _state_path(metrics_dir: Path, run_date: str) -> Path:
    return metrics_dir / f"run-state-{run_date}.json"


def save_run_state(state: RunState, metrics_dir: Path) -> Path:
    """Save run state to disk for resume capability.

    Args:
        state: Current run state.
        metrics_dir: Directory for metrics and state files.

    Returns:
        Path to the written state file.
    """
    metrics_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(metrics_dir, state.run_date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)
    return path


def load_run_state(metrics_dir: Path, run_date: str) -> RunState | None:
    """Load a previous run state if one exists.

    Args:
        metrics_dir: Directory where state files are stored.
        run_date: ISO date string for the run to resume.

    Returns:
        RunState if a state file exists, None otherwise.
    """
    path = _state_path(metrics_dir, run_date)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return RunState.from_dict(data)


# --- Individual step runners ---


def run_consolidate(
    config: PipelineConfig,
    project_root: Path,
) -> StepResult:
    """Run the consolidation step: ingest conversations and convert memories.

    Returns:
        StepResult with session and exchange counts.
    """
    started = _now_iso()
    try:
        from svapna.consolidate.ingest import ingest_all
        from svapna.consolidate.memories import convert_memory_files

        sessions = ingest_all(project_filter=None)
        total_exchanges = sum(len(s.exchanges) for s in sessions)
        memory_pairs = convert_memory_files()

        return StepResult(
            step="consolidate",
            status="success",
            started_at=started,
            finished_at=_now_iso(),
            message=f"{len(sessions)} sessions, {total_exchanges} exchanges, {len(memory_pairs)} memory pairs",
            metrics={
                "sessions": len(sessions),
                "exchanges": total_exchanges,
                "memory_pairs": len(memory_pairs),
            },
        )
    except Exception as e:
        logger.error("Consolidation failed: %s", e)
        return StepResult(
            step="consolidate",
            status="failed",
            started_at=started,
            finished_at=_now_iso(),
            message=str(e),
        )


def run_dream(
    config: PipelineConfig,
    project_root: Path,
) -> StepResult:
    """Run the dream generation step.

    Returns:
        StepResult with dream count.
    """
    started = _now_iso()
    try:
        from svapna.dream.generate import GeneratorConfig, generate_batch

        gen_config = GeneratorConfig.from_config(project_root)
        identity_context = _load_identity_context(project_root)
        recent = _load_recent_experiences(project_root)

        dreams = generate_batch(
            identity_context, recent, config=gen_config,
        )

        # Save dreams for later steps
        dreams_dir = project_root / "data" / "dreams"
        dreams_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        dreams_path = dreams_dir / f"dreams-{today}.json"
        with open(dreams_path, "w", encoding="utf-8") as f:
            json.dump([d.to_dict() for d in dreams], f, indent=2)

        return StepResult(
            step="dream",
            status="success",
            started_at=started,
            finished_at=_now_iso(),
            message=f"Generated {len(dreams)} dreams",
            metrics={"dreams_generated": len(dreams)},
        )
    except Exception as e:
        logger.error("Dream generation failed: %s", e)
        return StepResult(
            step="dream",
            status="failed",
            started_at=started,
            finished_at=_now_iso(),
            message=str(e),
        )


def run_score(
    config: PipelineConfig,
    project_root: Path,
) -> StepResult:
    """Run the dream scoring step.

    Returns:
        StepResult with scoring statistics.
    """
    started = _now_iso()
    try:
        from svapna.dream.journal import build_journal_entry, write_journal
        from svapna.dream.score import DreamScorerConfig, filter_by_quality, score_batch

        scorer_config = DreamScorerConfig.from_models_yml(project_root)
        identity_context = _load_identity_context(project_root)

        # Load dreams from the dream step output
        dreams = _load_todays_dreams(project_root)
        if not dreams:
            return StepResult(
                step="score",
                status="skipped",
                started_at=started,
                finished_at=_now_iso(),
                message="No dreams to score",
            )

        scores = score_batch(dreams, identity_context, config=scorer_config)
        valid_scores = [s for s in scores if s is not None]
        kept = filter_by_quality(dreams, scores, config.dreams.min_quality)

        # Write dream journal
        journal_entry = build_journal_entry(
            [d for d, _ in zip(dreams, scores) if _ is not None],
            valid_scores,
            min_quality=config.dreams.min_quality,
        )
        journal_dir = project_root / "data" / "journals"
        write_journal(journal_entry, journal_dir)

        return StepResult(
            step="score",
            status="success",
            started_at=started,
            finished_at=_now_iso(),
            message=f"Scored {len(valid_scores)}/{len(dreams)} dreams, {len(kept)} passed quality threshold",
            metrics={
                "scored": len(valid_scores),
                "passed": len(kept),
                "failed_scoring": len(dreams) - len(valid_scores),
            },
        )
    except Exception as e:
        logger.error("Dream scoring failed: %s", e)
        return StepResult(
            step="score",
            status="failed",
            started_at=started,
            finished_at=_now_iso(),
            message=str(e),
        )


def run_prepare(
    config: PipelineConfig,
    project_root: Path,
) -> StepResult:
    """Run the training data preparation step.

    Returns:
        StepResult with dataset size.
    """
    started = _now_iso()
    try:
        from svapna.consolidate.ingest import ingest_all
        from svapna.consolidate.memories import convert_memory_files
        from svapna.dream.score import DreamScore, DreamScorerConfig, filter_by_quality, score_batch
        from svapna.train.prepare import PrepareConfig, prepare_training_data, save_dataset

        sessions = ingest_all(project_filter=None)
        memory_pairs = convert_memory_files()

        # Load scored dreams if available
        scored_dreams = _load_scored_dreams(project_root)

        prep_config = PrepareConfig.from_pipeline_yml(project_root)
        data = prepare_training_data(
            sessions, memory_pairs, scored_dreams, config=prep_config,
        )

        output_dir = project_root / "data" / "training"
        today = date.today().isoformat()
        output_path = save_dataset(data, output_dir, name=today)

        return StepResult(
            step="prepare",
            status="success",
            started_at=started,
            finished_at=_now_iso(),
            message=f"Prepared {len(data)} training examples -> {output_path.name}",
            metrics={
                "examples": len(data),
                "output_file": str(output_path),
            },
        )
    except Exception as e:
        logger.error("Training data preparation failed: %s", e)
        return StepResult(
            step="prepare",
            status="failed",
            started_at=started,
            finished_at=_now_iso(),
            message=str(e),
        )


def run_train(
    config: PipelineConfig,
    project_root: Path,
) -> StepResult:
    """Run the LoRA training step.

    This step requires a GPU and the unsloth library. It is skipped
    via --no-train in production when training is handled separately.

    Returns:
        StepResult with training outcome.
    """
    started = _now_iso()
    try:
        # Training is a heavyweight operation that requires GPU libraries.
        # For now, we verify the training data exists and log that training
        # would run. Actual training invocation is done via the train module.
        today = date.today().isoformat()
        training_file = project_root / "data" / "training" / f"{today}.jsonl"

        if not training_file.exists():
            return StepResult(
                step="train",
                status="skipped",
                started_at=started,
                finished_at=_now_iso(),
                message="No training data file found for today",
            )

        line_count = sum(1 for _ in open(training_file, encoding="utf-8"))

        return StepResult(
            step="train",
            status="success",
            started_at=started,
            finished_at=_now_iso(),
            message=f"Training data ready: {line_count} examples in {training_file.name}",
            metrics={"training_examples": line_count},
        )
    except Exception as e:
        logger.error("Training step failed: %s", e)
        return StepResult(
            step="train",
            status="failed",
            started_at=started,
            finished_at=_now_iso(),
            message=str(e),
        )


def run_evaluate(
    config: PipelineConfig,
    project_root: Path,
) -> StepResult:
    """Run the ICT evaluation step.

    Only runs every ``config.evaluation.ict_frequency`` cycles, based
    on the count of existing evaluation reports.

    Returns:
        StepResult with evaluation outcome.
    """
    started = _now_iso()
    try:
        eval_dir = project_root / "data" / "evaluations"
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Check frequency: count existing reports
        existing_reports = sorted(eval_dir.glob("ict-report-*.json"))
        # If not enough cycles have passed, skip
        # (We run on every Nth cycle, counting from 0)
        cycle_count = len(existing_reports)
        if cycle_count > 0 and cycle_count % config.evaluation.ict_frequency != 0:
            return StepResult(
                step="evaluate",
                status="skipped",
                started_at=started,
                finished_at=_now_iso(),
                message=(
                    f"Skipping ICT (cycle {cycle_count}, "
                    f"runs every {config.evaluation.ict_frequency} cycles)"
                ),
            )

        return StepResult(
            step="evaluate",
            status="success",
            started_at=started,
            finished_at=_now_iso(),
            message=f"Evaluation cycle {cycle_count}: ICT scheduled",
            metrics={"cycle": cycle_count},
        )
    except Exception as e:
        logger.error("Evaluation step failed: %s", e)
        return StepResult(
            step="evaluate",
            status="failed",
            started_at=started,
            finished_at=_now_iso(),
            message=str(e),
        )


# --- Helpers for loading data between steps ---


def _load_identity_context(project_root: Path) -> str:
    """Load identity context from narada identity files."""
    identity_dir = Path.home() / ".claude" / "narada"
    identity_file = identity_dir / "identity.md"
    if identity_file.exists():
        return identity_file.read_text(encoding="utf-8")
    return "Narada is a persistent AI identity with genuine curiosity and honesty."


def _load_recent_experiences(project_root: Path) -> list[str]:
    """Load recent conversation excerpts for dream generation."""
    raw_dir = project_root / "data" / "raw"
    if not raw_dir.exists():
        return ["Human: Who are you?\n\nAssistant: I am Narada."]

    experience_files = sorted(raw_dir.glob("*.jsonl"), reverse=True)[:3]
    experiences: list[str] = []
    for f in experience_files:
        try:
            text = f.read_text(encoding="utf-8")
            lines = text.strip().split("\n")[:5]
            experiences.append("\n".join(lines))
        except Exception:
            continue

    return experiences if experiences else ["Human: Who are you?\n\nAssistant: I am Narada."]


def _load_todays_dreams(project_root: Path) -> list:
    """Load dreams generated earlier today."""
    from svapna.dream.generate import Dream, DreamTurn
    from svapna.dream.templates import DreamType

    today = date.today().isoformat()
    dreams_path = project_root / "data" / "dreams" / f"dreams-{today}.json"
    if not dreams_path.exists():
        return []

    with open(dreams_path, encoding="utf-8") as f:
        data = json.load(f)

    dreams = []
    for d in data:
        turns = [DreamTurn(role=t["role"], text=t["text"]) for t in d["turns"]]
        dreams.append(Dream(
            dream_type=DreamType(d["dream_type"]),
            turns=turns,
            identity_context=d["identity_context"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
        ))
    return dreams


def _load_scored_dreams(project_root: Path) -> list:
    """Load scored dream pairs for training data preparation.

    Returns a list of (Dream, DreamScore) tuples. Returns empty list
    if no scored dreams are available.
    """
    # For now, return empty — the prepare step will still work with
    # conversation + memory data. Full dream scoring integration
    # will come when the pipeline runs end-to-end with real data.
    return []


# --- Pipeline runner ---

def _get_step_runner(step: Step):
    """Look up the runner function for a step at call time.

    This indirection (instead of a dict literal) ensures that
    unittest.mock.patch on the module-level functions takes effect.
    """
    import svapna.orchestrate.nightly as _self

    _runners = {
        Step.CONSOLIDATE: _self.run_consolidate,
        Step.DREAM: _self.run_dream,
        Step.SCORE: _self.run_score,
        Step.PREPARE: _self.run_prepare,
        Step.TRAIN: _self.run_train,
        Step.EVALUATE: _self.run_evaluate,
    }
    return _runners[step]


def run_pipeline(
    *,
    steps: list[Step] | None = None,
    skip_training: bool = False,
    resume: bool = False,
    config: PipelineConfig | None = None,
    project_root: Path | None = None,
) -> list[StepResult]:
    """Run the nightly pipeline.

    Executes pipeline steps in order, logging progress and saving state
    for resume capability.

    Args:
        steps: Specific steps to run. Defaults to all steps.
        skip_training: If True, skip the TRAIN step.
        resume: If True, resume from last completed step of today's run.
        config: Pipeline configuration. Loaded from pipeline.yml if None.
        project_root: Project root directory. Auto-detected if None.

    Returns:
        List of StepResult objects for each step executed.
    """
    if project_root is None:
        project_root = _project_root()
    if config is None:
        config = PipelineConfig.load(project_root)

    if steps is None:
        steps = list(ALL_STEPS)

    if skip_training:
        steps = [s for s in steps if s != Step.TRAIN]

    metrics_dir = project_root / "data" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    # Resume support: load previous state and skip completed steps
    start_after = 0
    previous_results: list[dict[str, Any]] = []
    if resume:
        existing_state = load_run_state(metrics_dir, today)
        if existing_state is not None:
            start_after = existing_state.last_completed_step
            previous_results = existing_state.step_results
            logger.info(
                "Resuming from step %d (completed %d steps previously)",
                start_after + 1, len(previous_results),
            )

    state = RunState(
        run_date=today,
        last_completed_step=start_after,
        step_results=list(previous_results),
        started_at=_now_iso(),
    )
    save_run_state(state, metrics_dir)

    results: list[StepResult] = []

    for step in steps:
        # Skip steps already completed in a previous run
        if step.value <= start_after:
            logger.info("Skipping already-completed step: %s", step.name)
            continue

        logger.info("Running step: %s", step.name)
        runner = _get_step_runner(step)
        result = runner(config, project_root)
        results.append(result)

        # Update state
        state.step_results.append(result.to_dict())
        if result.status in ("success", "skipped"):
            state.last_completed_step = step.value
        save_run_state(state, metrics_dir)

        logger.info(
            "Step %s: %s — %s",
            step.name, result.status, result.message,
        )

        # Stop on failure
        if result.status == "failed":
            logger.error("Pipeline halted at step %s", step.name)
            break

    state.finished_at = _now_iso()
    save_run_state(state, metrics_dir)

    # Save metrics summary
    _save_metrics_summary(results, metrics_dir, today)

    return results


def _save_metrics_summary(
    results: list[StepResult],
    metrics_dir: Path,
    run_date: str,
) -> Path:
    """Save a summary of pipeline metrics.

    Args:
        results: Step results from the pipeline run.
        metrics_dir: Output directory.
        run_date: ISO date string.

    Returns:
        Path to the written metrics file.
    """
    summary = {
        "run_date": run_date,
        "timestamp": _now_iso(),
        "steps": [r.to_dict() for r in results],
        "total_steps": len(results),
        "successful": sum(1 for r in results if r.status == "success"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
    }

    path = metrics_dir / f"nightly-{run_date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return path
