"""Dream generation pipeline.

Uses the Claude API to generate synthetic conversations from dream templates.
Takes the pipeline config (dream count, distribution across types) and produces
dream conversations in a structured format. Handles API rate limiting and errors.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import yaml

from svapna.dream.templates import DreamType, render_dream_prompt

logger = logging.getLogger(__name__)


@dataclass
class GeneratorConfig:
    """Configuration for the dream generator.

    Model settings come from .ai/models.yml (dream_generator section).
    Dream count and distribution come from config/pipeline.yml.
    """

    model: str = ""
    temperature: float = 0.8
    max_tokens: int = 4096
    count: int = 20
    distribution: dict[DreamType, int] = field(default_factory=dict)
    min_quality: float = 7.0
    max_retries: int = 3
    retry_base_delay: float = 2.0

    @classmethod
    def from_config(cls, project_root: Path | None = None) -> GeneratorConfig:
        """Load config from .ai/models.yml and config/pipeline.yml.

        Args:
            project_root: Project root directory. Defaults to traversing
                up from this module's location.

        Raises:
            FileNotFoundError: If models.yml is missing.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent

        # Model settings from .ai/models.yml
        models_path = project_root / ".ai" / "models.yml"
        if not models_path.exists():
            raise FileNotFoundError(f"models.yml not found: {models_path}")
        with open(models_path, encoding="utf-8") as f:
            models_cfg = yaml.safe_load(f)
        gen_cfg = models_cfg.get("dream_generator", {})

        # Dream distribution from config/pipeline.yml
        pipeline_path = project_root / "config" / "pipeline.yml"
        dreams_cfg: dict[str, Any] = {}
        if pipeline_path.exists():
            with open(pipeline_path, encoding="utf-8") as f:
                pipeline_cfg = yaml.safe_load(f)
            dreams_cfg = pipeline_cfg.get("dreams", {})

        distribution: dict[DreamType, int] = {}
        for type_name, count in dreams_cfg.get("distribution", {}).items():
            distribution[DreamType(type_name)] = count

        return cls(
            model=gen_cfg["model"],
            temperature=gen_cfg.get("temperature", 0.8),
            max_tokens=gen_cfg.get("max_tokens", 4096),
            count=dreams_cfg.get("count", 20),
            distribution=distribution,
            min_quality=dreams_cfg.get("min_quality", 7.0),
        )


@dataclass
class DreamTurn:
    """A single turn in a dream conversation."""

    role: str  # "human" or "assistant"
    text: str


@dataclass
class Dream:
    """A generated dream conversation."""

    dream_type: DreamType
    turns: list[DreamTurn]
    identity_context: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_response: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if dream has at least one human and one assistant turn."""
        if len(self.turns) < 2:
            return False
        roles = [t.role for t in self.turns]
        return "human" in roles and "assistant" in roles

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "dream_type": self.dream_type.value,
            "turns": [{"role": t.role, "text": t.text} for t in self.turns],
            "identity_context": self.identity_context,
            "timestamp": self.timestamp.isoformat(),
        }


def parse_dream_response(text: str) -> list[DreamTurn]:
    """Parse a generated conversation into turns.

    Expects format with ``Human:`` and ``Assistant:`` markers at the start
    of lines. Content between markers is captured as the turn text.

    Args:
        text: Raw text from the LLM containing a conversation.

    Returns:
        List of DreamTurn objects parsed from the text.
    """
    # Split on Human: or Assistant: markers at line start
    pattern = r"^(Human|Assistant):\s*"
    parts = re.split(pattern, text, flags=re.MULTILINE)

    turns: list[DreamTurn] = []
    # parts[0] is text before the first marker (skip it)
    # Then pairs of (marker_label, content) follow
    i = 1
    while i < len(parts) - 1:
        role_label = parts[i].strip().lower()
        content = parts[i + 1].strip()
        if content and role_label in ("human", "assistant"):
            turns.append(DreamTurn(role=role_label, text=content))
        i += 2

    return turns


def generate_dream(
    dream_type: DreamType,
    identity_context: str,
    recent_experiences: list[str],
    *,
    config: GeneratorConfig,
    client: anthropic.Anthropic | None = None,
) -> Dream:
    """Generate a single dream conversation via the Claude API.

    Args:
        dream_type: Type of dream to generate.
        identity_context: Identity text for the dreamer.
        recent_experiences: Recent conversation excerpts.
        config: Dream generation configuration.
        client: Anthropic API client. Created if not provided.

    Returns:
        A Dream with parsed conversation turns.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    if client is None:
        client = anthropic.Anthropic()

    system_prompt, user_prompt = render_dream_prompt(
        dream_type, identity_context, recent_experiences,
    )

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = response.content[0].text
            turns = parse_dream_response(raw_text)

            return Dream(
                dream_type=dream_type,
                turns=turns,
                identity_context=identity_context,
                raw_response=raw_text,
            )
        except anthropic.APIError as e:
            last_error = e
            if attempt < config.max_retries - 1:
                delay = config.retry_base_delay * (2 ** attempt)
                logger.warning(
                    "API error generating %s dream (attempt %d/%d): %s. "
                    "Retrying in %.1fs",
                    dream_type.value, attempt + 1, config.max_retries, e, delay,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Failed to generate {dream_type.value} dream after "
        f"{config.max_retries} attempts: {last_error}"
    )


def _resolve_distribution(config: GeneratorConfig) -> dict[DreamType, int]:
    """Resolve the distribution of dreams to generate.

    Uses the configured distribution if present, otherwise distributes
    the count evenly across all dream types.
    """
    if config.distribution:
        return dict(config.distribution)

    types = list(DreamType)
    per_type = config.count // len(types)
    remainder = config.count % len(types)

    dist: dict[DreamType, int] = {}
    for i, dt in enumerate(types):
        dist[dt] = per_type + (1 if i < remainder else 0)

    return dist


def generate_batch(
    identity_context: str,
    recent_experiences: list[str],
    *,
    config: GeneratorConfig | None = None,
    client: anthropic.Anthropic | None = None,
) -> list[Dream]:
    """Generate a batch of dreams according to the config distribution.

    Shares a single API client across all generations. Individual failures
    are logged but do not stop the batch; the returned list may be shorter
    than the configured count if some dreams fail.

    Args:
        identity_context: Identity text for the dreamer.
        recent_experiences: Recent conversation excerpts.
        config: Dream generation config. Loaded from config files if None.
        client: Anthropic API client. Created if None.

    Returns:
        List of successfully generated Dream objects.
    """
    if config is None:
        config = GeneratorConfig.from_config()
    if client is None:
        client = anthropic.Anthropic()

    distribution = _resolve_distribution(config)

    dreams: list[Dream] = []
    for dream_type, count in distribution.items():
        for i in range(count):
            try:
                dream = generate_dream(
                    dream_type=dream_type,
                    identity_context=identity_context,
                    recent_experiences=recent_experiences,
                    config=config,
                    client=client,
                )
                dreams.append(dream)
                logger.info(
                    "Generated %s dream %d/%d (%d turns)",
                    dream_type.value, i + 1, count, len(dream.turns),
                )
            except RuntimeError as e:
                logger.error(
                    "Failed to generate %s dream %d/%d: %s",
                    dream_type.value, i + 1, count, e,
                )

    return dreams
