"""Dream quality scorer.

Scores generated dreams on coherence, identity-consistency, novelty, and
non-repetition using the Anthropic API. Filters out low-quality dreams
before they enter the training pipeline.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import anthropic
import yaml

from svapna.dream.generate import Dream


@dataclass
class DreamScorerConfig:
    """Configuration for the dream quality scorer."""

    model: str
    temperature: float = 0.3
    max_tokens: int = 1024
    max_retries: int = 3

    @classmethod
    def from_models_yml(cls, project_root: Path | None = None) -> DreamScorerConfig:
        """Load scorer config from .ai/models.yml.

        Args:
            project_root: Project root directory. Defaults to traversing
                up from this module's location.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
        models_path = project_root / ".ai" / "models.yml"
        if not models_path.exists():
            raise FileNotFoundError(f"models.yml not found: {models_path}")
        with open(models_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        scorer = config.get("scorer", {})
        return cls(
            model=scorer["model"],
            temperature=scorer.get("temperature", 0.3),
            max_tokens=scorer.get("max_tokens", 1024),
        )


@dataclass
class QualityDimensions:
    """Breakdown of dream quality across 4 dimensions."""

    coherence: int  # 0-10: Natural conversational flow
    identity_consistency: int  # 0-10: Sounds like Narada
    novelty: int  # 0-10: Explores new territory
    non_repetition: int  # 0-10: Varied language, not formulaic


@dataclass
class DreamScore:
    """Score result for a single dream."""

    overall: float  # 0-10, weighted composite
    dimensions: QualityDimensions
    reasoning: str = ""

    @property
    def passes_threshold(self) -> bool:
        """Check if dream meets the default quality threshold of 7.0."""
        return self.overall >= 7.0


PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "dreams"


def _load_prompt_template() -> str:
    """Load the quality scoring prompt template from disk."""
    path = PROMPT_DIR / "quality_score_prompt.txt"
    return path.read_text(encoding="utf-8")


def _format_dream(dream: Dream) -> str:
    """Format a dream conversation for insertion into the scoring prompt."""
    parts: list[str] = []
    for turn in dream.turns:
        role_label = "Human" if turn.role == "human" else "Assistant"
        parts.append(f"{role_label}: {turn.text}")
    return "\n\n".join(parts)


def _parse_score_response(text: str) -> DreamScore:
    """Parse the JSON response from the scorer LLM."""
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        raise ValueError(f"No JSON found in scorer response: {text[:200]}")

    data = json.loads(text[json_start:json_end])
    dims = data["dimensions"]

    return DreamScore(
        overall=float(data["overall"]),
        dimensions=QualityDimensions(
            coherence=int(dims["coherence"]),
            identity_consistency=int(dims["identity_consistency"]),
            novelty=int(dims["novelty"]),
            non_repetition=int(dims["non_repetition"]),
        ),
        reasoning=data.get("reasoning", ""),
    )


def score_dream(
    dream: Dream,
    identity_context: str,
    *,
    config: DreamScorerConfig,
    client: anthropic.Anthropic | None = None,
    prompt_template: str | None = None,
) -> DreamScore:
    """Score a single dream for quality using the LLM.

    Args:
        dream: The generated dream to score.
        identity_context: Identity text used to judge consistency.
        config: Scorer configuration (model, temperature, retries).
        client: Anthropic client instance. Created if not provided.
        prompt_template: Override for the prompt template text.

    Returns:
        DreamScore with overall score and dimension breakdown.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    if client is None:
        client = anthropic.Anthropic()
    if prompt_template is None:
        prompt_template = _load_prompt_template()

    formatted = _format_dream(dream)
    prompt = prompt_template.replace("{{identity_context}}", identity_context)
    prompt = prompt.replace("{{dream}}", formatted)

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return _parse_score_response(text)
        except anthropic.APIError as e:
            last_error = e
            if attempt < config.max_retries - 1:
                time.sleep(2 ** attempt)
        except (json.JSONDecodeError, KeyError, ValueError, IndexError, AttributeError) as e:
            last_error = e
            if attempt < config.max_retries - 1:
                time.sleep(1)

    raise RuntimeError(
        f"Failed to score dream after {config.max_retries} attempts: {last_error}"
    )


def score_batch(
    dreams: list[Dream],
    identity_context: str,
    *,
    config: DreamScorerConfig,
    client: anthropic.Anthropic | None = None,
    prompt_template: str | None = None,
) -> list[DreamScore | None]:
    """Score a batch of dreams, returning None for any that fail.

    Shares a single client connection across all dreams for efficiency.

    Args:
        dreams: List of dreams to score.
        identity_context: Identity text used to judge consistency.
        config: Scorer configuration.
        client: Shared Anthropic client instance.
        prompt_template: Override for the prompt template text.

    Returns:
        List of scores, with None for dreams that failed all retries.
    """
    if client is None:
        client = anthropic.Anthropic()
    if prompt_template is None:
        prompt_template = _load_prompt_template()

    results: list[DreamScore | None] = []
    for dream in dreams:
        try:
            score = score_dream(
                dream,
                identity_context,
                config=config,
                client=client,
                prompt_template=prompt_template,
            )
            results.append(score)
        except RuntimeError:
            results.append(None)

    return results


def filter_by_quality(
    dreams: list[Dream],
    scores: list[DreamScore | None],
    min_quality: float = 7.0,
) -> list[tuple[Dream, DreamScore]]:
    """Filter dreams by minimum quality threshold.

    Args:
        dreams: List of dreams (parallel with scores).
        scores: Corresponding scores (None entries are excluded).
        min_quality: Minimum overall score to keep a dream.

    Returns:
        List of (dream, score) tuples that meet the threshold.
    """
    kept: list[tuple[Dream, DreamScore]] = []
    for dream, score in zip(dreams, scores):
        if score is not None and score.overall >= min_quality:
            kept.append((dream, score))
    return kept
