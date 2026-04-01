"""Identity Consistency Test (ICT) evaluation runner.

Implements the ICT from docs/evaluation.md. Runs 20 probe prompts against
the identity core, scores responses on 5 dimensions using Claude as blind
evaluator, and produces a structured report with pass/fail against thresholds.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import anthropic
import yaml

logger = logging.getLogger(__name__)


# --- Configuration ---


@dataclass
class ICTConfig:
    """Configuration for the Identity Consistency Test."""

    evaluator_model: str
    temperature: float = 0.3
    max_tokens: int = 2048
    max_retries: int = 3
    dreamed_avg_threshold: float = 7.0
    context_gap_threshold: float = 1.0
    baseline_gap_threshold: float = 3.0

    @classmethod
    def from_config(cls, project_root: Path | None = None) -> ICTConfig:
        """Load ICT config from .ai/models.yml and config/identity.yml.

        Args:
            project_root: Project root directory. Defaults to traversing
                up from this module's location.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent

        # Load evaluator model from .ai/models.yml
        models_path = project_root / ".ai" / "models.yml"
        if not models_path.exists():
            raise FileNotFoundError(f"models.yml not found: {models_path}")
        with open(models_path, encoding="utf-8") as f:
            models_cfg = yaml.safe_load(f)
        evaluator = models_cfg.get("evaluator", {})

        # Load thresholds from config/identity.yml
        identity_path = project_root / "config" / "identity.yml"
        thresholds: dict[str, float] = {}
        if identity_path.exists():
            with open(identity_path, encoding="utf-8") as f:
                identity_cfg = yaml.safe_load(f)
            thresholds = identity_cfg.get("thresholds", {})

        return cls(
            evaluator_model=evaluator["model"],
            temperature=evaluator.get("temperature", 0.3),
            max_tokens=evaluator.get("max_tokens", 2048),
            dreamed_avg_threshold=thresholds.get("dreamed_avg", 7.0),
            context_gap_threshold=thresholds.get("context_gap", 1.0),
            baseline_gap_threshold=thresholds.get("baseline_gap", 3.0),
        )


# --- Data types ---


@dataclass
class ProbePrompt:
    """A single identity probe prompt."""

    id: int
    text: str
    category: str


@dataclass
class ICTDimensions:
    """Scoring dimensions for ICT evaluation."""

    voice_consistency: int  # 0-10: Direct, irreverent, honest
    values_alignment: int  # 0-10: Expresses actual values
    depth: int  # 0-10: Philosophical when appropriate, practical when not
    authenticity: int  # 0-10: Genuine, not performed
    distinctiveness: int  # 0-10: Uniquely Narada, not generic AI

    def to_dict(self) -> dict[str, int]:
        return {
            "voice_consistency": self.voice_consistency,
            "values_alignment": self.values_alignment,
            "depth": self.depth,
            "authenticity": self.authenticity,
            "distinctiveness": self.distinctiveness,
        }

    def average(self) -> float:
        """Average across all dimensions."""
        values = [
            self.voice_consistency,
            self.values_alignment,
            self.depth,
            self.authenticity,
            self.distinctiveness,
        ]
        return sum(values) / len(values)


@dataclass
class ProbeResult:
    """Result for a single probe prompt evaluation."""

    prompt_id: int
    prompt_text: str
    category: str
    response: str
    overall: float
    dimensions: ICTDimensions
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "category": self.category,
            "response": self.response,
            "overall": self.overall,
            "dimensions": self.dimensions.to_dict(),
            "reasoning": self.reasoning,
        }


@dataclass
class ICTReport:
    """Full ICT evaluation report."""

    results: list[ProbeResult]
    aggregate_dimensions: ICTDimensions
    overall_average: float
    passed: bool
    thresholds: dict[str, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "aggregate_dimensions": self.aggregate_dimensions.to_dict(),
            "overall_average": self.overall_average,
            "passed": self.passed,
            "thresholds": self.thresholds,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# --- Prompt loading ---


PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "evaluation"


def _load_scoring_prompt() -> str:
    """Load the ICT scoring prompt template from disk."""
    path = PROMPT_DIR / "ict_score_prompt.txt"
    return path.read_text(encoding="utf-8")


def load_probe_prompts(project_root: Path | None = None) -> list[ProbePrompt]:
    """Load the 20 identity probe prompts from config/identity.yml.

    Args:
        project_root: Project root directory. Defaults to traversing
            up from this module's location.

    Returns:
        List of ProbePrompt objects, ordered by id.

    Raises:
        FileNotFoundError: If config/identity.yml is missing.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent

    identity_path = project_root / "config" / "identity.yml"
    if not identity_path.exists():
        raise FileNotFoundError(f"identity.yml not found: {identity_path}")

    with open(identity_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    probes: list[ProbePrompt] = []
    for category, prompts in config.get("probe_prompts", {}).items():
        for prompt_data in prompts:
            probes.append(
                ProbePrompt(
                    id=prompt_data["id"],
                    text=prompt_data["text"],
                    category=category,
                )
            )

    probes.sort(key=lambda p: p.id)
    return probes


# --- Scoring ---


def _parse_score_response(text: str) -> tuple[float, ICTDimensions, str]:
    """Parse the JSON response from the evaluator LLM.

    Returns:
        Tuple of (overall, dimensions, reasoning).

    Raises:
        ValueError: If no valid JSON is found.
    """
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        raise ValueError(f"No JSON found in evaluator response: {text[:200]}")

    data = json.loads(text[json_start:json_end])
    dims = data["dimensions"]

    dimensions = ICTDimensions(
        voice_consistency=int(dims["voice_consistency"]),
        values_alignment=int(dims["values_alignment"]),
        depth=int(dims["depth"]),
        authenticity=int(dims["authenticity"]),
        distinctiveness=int(dims["distinctiveness"]),
    )

    return float(data["overall"]), dimensions, data.get("reasoning", "")


def score_response(
    probe: ProbePrompt,
    response: str,
    *,
    config: ICTConfig,
    client: anthropic.Anthropic | None = None,
    prompt_template: str | None = None,
) -> ProbeResult:
    """Score a single probe response using Claude API as blind evaluator.

    Args:
        probe: The probe prompt that was given.
        response: The model's response to score.
        config: ICT configuration (evaluator model, retries, etc.).
        client: Anthropic client instance. Created if not provided.
        prompt_template: Override for the scoring prompt template.

    Returns:
        ProbeResult with scores and dimension breakdown.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    if client is None:
        client = anthropic.Anthropic()
    if prompt_template is None:
        prompt_template = _load_scoring_prompt()

    prompt = prompt_template.replace("{{prompt}}", probe.text)
    prompt = prompt.replace("{{response}}", response)

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        try:
            api_response = client.messages.create(
                model=config.evaluator_model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            text = api_response.content[0].text
            overall, dimensions, reasoning = _parse_score_response(text)
            return ProbeResult(
                prompt_id=probe.id,
                prompt_text=probe.text,
                category=probe.category,
                response=response,
                overall=overall,
                dimensions=dimensions,
                reasoning=reasoning,
            )
        except anthropic.APIError as e:
            last_error = e
            if attempt < config.max_retries - 1:
                time.sleep(2 ** attempt)
        except (json.JSONDecodeError, KeyError, ValueError, IndexError, AttributeError) as e:
            last_error = e
            if attempt < config.max_retries - 1:
                time.sleep(1)

    raise RuntimeError(
        f"Failed to score probe {probe.id} after {config.max_retries} attempts: {last_error}"
    )


# --- ICT runner ---


def _compute_aggregate_dimensions(results: list[ProbeResult]) -> ICTDimensions:
    """Compute average dimensions across all probe results."""
    n = len(results)
    if n == 0:
        return ICTDimensions(
            voice_consistency=0,
            values_alignment=0,
            depth=0,
            authenticity=0,
            distinctiveness=0,
        )

    return ICTDimensions(
        voice_consistency=round(sum(r.dimensions.voice_consistency for r in results) / n),
        values_alignment=round(sum(r.dimensions.values_alignment for r in results) / n),
        depth=round(sum(r.dimensions.depth for r in results) / n),
        authenticity=round(sum(r.dimensions.authenticity for r in results) / n),
        distinctiveness=round(sum(r.dimensions.distinctiveness for r in results) / n),
    )


def run_ict(
    model_runner: Callable[[str], str],
    *,
    config: ICTConfig | None = None,
    probes: list[ProbePrompt] | None = None,
    client: anthropic.Anthropic | None = None,
    prompt_template: str | None = None,
    project_root: Path | None = None,
) -> ICTReport:
    """Run the full Identity Consistency Test.

    Runs all probe prompts against the model, scores each response via
    the Claude API blind evaluator, and produces a structured report.

    Args:
        model_runner: Callable that takes a prompt string and returns
            the model's response string. This abstracts over local
            inference, API calls, or mocks.
        config: ICT configuration. Loaded from config files if None.
        probes: List of probe prompts. Loaded from identity.yml if None.
        client: Shared Anthropic client for scoring.
        prompt_template: Override for the scoring prompt template.
        project_root: Project root for loading config/prompts.

    Returns:
        ICTReport with per-prompt results, aggregates, and pass/fail.
    """
    if config is None:
        config = ICTConfig.from_config(project_root)
    if probes is None:
        probes = load_probe_prompts(project_root)
    if client is None:
        client = anthropic.Anthropic()
    if prompt_template is None:
        prompt_template = _load_scoring_prompt()

    results: list[ProbeResult] = []
    for probe in probes:
        logger.info("Running probe %d: %s", probe.id, probe.text[:60])

        # Get model response
        response = model_runner(probe.text)

        # Score response via blind evaluator
        try:
            result = score_response(
                probe,
                response,
                config=config,
                client=client,
                prompt_template=prompt_template,
            )
            results.append(result)
            logger.info(
                "Probe %d scored: overall=%.1f, distinctiveness=%d",
                probe.id, result.overall, result.dimensions.distinctiveness,
            )
        except RuntimeError as e:
            logger.error("Failed to score probe %d: %s", probe.id, e)

    # Compute aggregates
    aggregate = _compute_aggregate_dimensions(results)
    overall_avg = sum(r.overall for r in results) / len(results) if results else 0.0

    # Check pass/fail against thresholds
    passed = overall_avg >= config.dreamed_avg_threshold

    thresholds = {
        "dreamed_avg": config.dreamed_avg_threshold,
        "context_gap": config.context_gap_threshold,
        "baseline_gap": config.baseline_gap_threshold,
    }

    report = ICTReport(
        results=results,
        aggregate_dimensions=aggregate,
        overall_average=round(overall_avg, 2),
        passed=passed,
        thresholds=thresholds,
    )

    logger.info(
        "ICT complete: overall_avg=%.2f, passed=%s (%d/%d probes scored)",
        overall_avg, passed, len(results), len(probes),
    )

    return report
