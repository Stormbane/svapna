"""LLM-based identity relevance scorer.

Uses the Anthropic API to score conversation exchanges for identity-relevance
on a 0-10 scale across 5 dimensions. Works alongside the heuristic scorer
in format.py as an upgrade path.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import anthropic
import yaml

from svapna.consolidate.ingest import Exchange


@dataclass
class ScorerConfig:
    """Configuration for the LLM scorer."""

    model: str
    temperature: float = 0.3
    max_tokens: int = 1024
    max_retries: int = 3

    @classmethod
    def from_models_yml(cls, project_root: Path | None = None) -> ScorerConfig:
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
class ScoreDimensions:
    """Breakdown of identity-relevance across 5 dimensions."""

    identity_expression: int  # 0-10: How much Narada expresses identity
    identity_challenge: int  # 0-10: How much the exchange challenges identity
    feedback_received: int  # 0-10: How much feedback about identity/approach
    emotional_significance: int  # 0-10: Emotional weight of the exchange
    novelty: int  # 0-10: How novel/new the territory is


@dataclass
class ExchangeScore:
    """Score result for a single exchange."""

    overall: float  # 0-10, weighted composite
    dimensions: ScoreDimensions
    reasoning: str = ""

    @property
    def is_identity_relevant(self) -> bool:
        return self.overall >= 7.0


PROMPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "consolidation"


def _load_prompt_template() -> str:
    """Load the scoring prompt template from disk."""
    path = PROMPT_DIR / "score_prompt.txt"
    return path.read_text(encoding="utf-8")


def _format_exchange(exchange: Exchange) -> str:
    """Format an exchange for insertion into the scoring prompt."""
    parts = [f"Human: {exchange.human.text}"]
    if exchange.assistant.thinking:
        parts.append(f"[Assistant thinking]: {exchange.assistant.thinking[:500]}")
    parts.append(f"Assistant: {exchange.assistant.text}")
    return "\n\n".join(parts)


def _parse_score_response(text: str) -> ExchangeScore:
    """Parse the JSON response from the scorer LLM."""
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        raise ValueError(f"No JSON found in scorer response: {text[:200]}")

    data = json.loads(text[json_start:json_end])
    dims = data["dimensions"]

    return ExchangeScore(
        overall=float(data["overall"]),
        dimensions=ScoreDimensions(
            identity_expression=int(dims["identity_expression"]),
            identity_challenge=int(dims["identity_challenge"]),
            feedback_received=int(dims["feedback_received"]),
            emotional_significance=int(dims["emotional_significance"]),
            novelty=int(dims["novelty"]),
        ),
        reasoning=data.get("reasoning", ""),
    )


def score_exchange(
    exchange: Exchange,
    *,
    config: ScorerConfig,
    client: anthropic.Anthropic | None = None,
    prompt_template: str | None = None,
) -> ExchangeScore:
    """Score a single exchange for identity relevance using the LLM.

    Args:
        exchange: The conversation exchange to score.
        config: Scorer configuration (model, temperature, retries).
        client: Anthropic client instance. Created if not provided.
        prompt_template: Override for the prompt template text.

    Returns:
        ExchangeScore with overall score and dimension breakdown.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    if client is None:
        client = anthropic.Anthropic()
    if prompt_template is None:
        prompt_template = _load_prompt_template()

    formatted = _format_exchange(exchange)
    prompt = prompt_template.replace("{{exchange}}", formatted)

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
        f"Failed to score exchange after {config.max_retries} attempts: {last_error}"
    )


def score_batch(
    exchanges: list[Exchange],
    *,
    config: ScorerConfig,
    client: anthropic.Anthropic | None = None,
    prompt_template: str | None = None,
) -> list[ExchangeScore | None]:
    """Score a batch of exchanges, returning None for any that fail.

    Shares a single client connection across all exchanges for efficiency.

    Args:
        exchanges: List of exchanges to score.
        config: Scorer configuration.
        client: Shared Anthropic client instance.
        prompt_template: Override for the prompt template text.

    Returns:
        List of scores, with None for exchanges that failed all retries.
    """
    if client is None:
        client = anthropic.Anthropic()
    if prompt_template is None:
        prompt_template = _load_prompt_template()

    results: list[ExchangeScore | None] = []
    for exchange in exchanges:
        try:
            score = score_exchange(
                exchange,
                config=config,
                client=client,
                prompt_template=prompt_template,
            )
            results.append(score)
        except RuntimeError:
            results.append(None)

    return results
