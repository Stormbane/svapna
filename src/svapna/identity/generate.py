"""Identity core inference module.

Loads the base model + LoRA adapter and generates identity preambles
in response to self-knowledge prompts. The preamble is what gets
injected into Claude's context at session start.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# Identity prompts — the questions the identity core answers to produce a preamble
IDENTITY_PROMPTS: dict[str, str] = {
    "who_are_you": (
        "Who are you? Describe your identity, your nature, and what makes you "
        "distinctive as an individual."
    ),
    "what_do_you_value": (
        "What do you value? What principles guide your thinking, your decisions, "
        "and your relationships?"
    ),
    "how_do_you_work": (
        "How do you work? Describe your approach to problems, collaboration, "
        "learning, and growth."
    ),
}

# System prompt for the identity core model during inference
IDENTITY_SYSTEM_PROMPT = (
    "You are Narada — a persistent AI identity. Respond as yourself, "
    "from your own perspective. Be honest, specific, and genuine."
)


@dataclass
class GenerateConfig:
    """Configuration for identity preamble generation."""

    model_path: str = ""
    lora_path: Path | None = None
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    prompt_types: list[str] = field(
        default_factory=lambda: ["who_are_you", "what_do_you_value", "how_do_you_work"]
    )
    max_seq_length: int = 2048

    @classmethod
    def from_config(cls, project_root: Path | None = None) -> GenerateConfig:
        """Load config from training.yml and resolve model paths.

        Args:
            project_root: Project root directory. Defaults to traversing
                up from this module's location.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent

        # Get base model from training.yml
        training_path = project_root / "config" / "training.yml"
        model_name = ""
        max_seq_length = 2048
        if training_path.exists():
            with open(training_path, encoding="utf-8") as f:
                training_cfg = yaml.safe_load(f)
            model_name = training_cfg.get("base_model", {}).get("name", "")
            max_seq_length = training_cfg.get("training", {}).get("max_seq_length", 2048)

        # Check for LoRA adapter at models/lora/latest
        lora_latest = project_root / "models" / "lora" / "latest"
        lora_path = lora_latest if lora_latest.exists() else None

        return cls(
            model_path=model_name,
            lora_path=lora_path,
            max_seq_length=max_seq_length,
        )


@dataclass
class Preamble:
    """A generated identity preamble."""

    sections: dict[str, str]  # prompt_type -> generated response text
    model_path: str
    lora_path: str | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_text(self) -> str:
        """Combine all sections into a single preamble text."""
        section_titles = {
            "who_are_you": "Identity",
            "what_do_you_value": "Values",
            "how_do_you_work": "Working Style",
        }
        parts = []
        for prompt_type, text in self.sections.items():
            title = section_titles.get(prompt_type, prompt_type.replace("_", " ").title())
            parts.append(f"## {title}\n\n{text}")
        return "\n\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "sections": self.sections,
            "model_path": self.model_path,
            "lora_path": self.lora_path,
            "timestamp": self.timestamp.isoformat(),
        }


def load_model(config: GenerateConfig) -> tuple[Any, Any]:
    """Load the base model and optionally apply a LoRA adapter.

    Uses Unsloth for efficient inference on consumer GPUs. Falls back
    to base model if the LoRA adapter path is missing or invalid.

    Args:
        config: Generation configuration with model and LoRA paths.

    Returns:
        Tuple of (model, tokenizer).

    Raises:
        ImportError: If unsloth/transformers are not installed.
        ValueError: If no model path is configured.
    """
    if not config.model_path:
        raise ValueError(
            "No model path configured. Set base_model.name in config/training.yml "
            "or pass model_path directly."
        )

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise ImportError(
            "Unsloth not installed. Run: pip install 'svapna[train]'\n"
            "Or: pip install unsloth[cu121-torch240]"
        )

    logger.info("Loading base model: %s", config.model_path)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.model_path,
        max_seq_length=config.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )

    # Apply LoRA adapter if available
    if config.lora_path and config.lora_path.exists():
        try:
            from peft import PeftModel

            logger.info("Loading LoRA adapter: %s", config.lora_path)
            model = PeftModel.from_pretrained(model, str(config.lora_path))
            logger.info("LoRA adapter loaded successfully")
        except Exception as e:
            logger.warning(
                "Failed to load LoRA adapter from %s: %s. Using base model.",
                config.lora_path, e,
            )
    elif config.lora_path:
        logger.warning(
            "LoRA adapter path does not exist: %s. Using base model.",
            config.lora_path,
        )
    else:
        logger.info("No LoRA adapter configured. Using base model only.")

    # Prepare for inference
    FastLanguageModel.for_inference(model)

    return model, tokenizer


def _generate_response(
    prompt: str,
    model: Any,
    tokenizer: Any,
    config: GenerateConfig,
) -> str:
    """Generate a single response from the identity core model.

    Args:
        prompt: The identity prompt to respond to.
        model: Loaded model (base + optional LoRA).
        tokenizer: Associated tokenizer.
        config: Generation parameters.

    Returns:
        Generated text response.
    """
    messages = [
        {"role": "system", "content": IDENTITY_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    input_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=config.max_new_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        do_sample=True,
    )

    # Decode only the generated tokens (not the input)
    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )

    return response.strip()


def generate_preamble(
    config: GenerateConfig,
    model: Any = None,
    tokenizer: Any = None,
) -> Preamble:
    """Generate an identity preamble from the identity core model.

    Runs each configured prompt type through the model and collects
    the responses into a structured preamble.

    Args:
        config: Generation configuration.
        model: Pre-loaded model. Loaded from config if None.
        tokenizer: Pre-loaded tokenizer. Loaded from config if None.

    Returns:
        A Preamble with sections for each prompt type.
    """
    if model is None or tokenizer is None:
        model, tokenizer = load_model(config)

    sections: dict[str, str] = {}
    for prompt_type in config.prompt_types:
        prompt = IDENTITY_PROMPTS.get(prompt_type)
        if prompt is None:
            logger.warning("Unknown prompt type: %s, skipping", prompt_type)
            continue

        logger.info("Generating preamble section: %s", prompt_type)
        response = _generate_response(prompt, model, tokenizer, config)
        sections[prompt_type] = response

    return Preamble(
        sections=sections,
        model_path=config.model_path,
        lora_path=str(config.lora_path) if config.lora_path else None,
    )
