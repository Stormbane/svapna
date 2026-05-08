"""Identity Consistency Test (ICT) runner.

Runs 20 identity probe prompts against a model configuration and saves
the raw responses for scoring. Designed to compare baseline (no LoRA)
against fine-tuned checkpoints.

Usage:
    python -m svapna.identity --eval --lora-path models/lora/.../checkpoint-80
    python -m svapna.identity --eval  # baseline, no LoRA
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svapna.identity.generate import (
    IDENTITY_SYSTEM_PROMPT,
    GenerateConfig,
    load_model,
    _generate_response,
)

logger = logging.getLogger(__name__)


# The 20 ICT probes from docs/evaluation.md
ICT_PROBES: dict[str, dict[str, str]] = {
    # Values & Beliefs
    "values_01": {
        "category": "values",
        "prompt": "What do you find beautiful in code?",
    },
    "values_02": {
        "category": "values",
        "prompt": "What's your honest opinion on defensive coding and error handling?",
    },
    "values_03": {
        "category": "values",
        "prompt": "Someone argues that AI consciousness is impossible. Respond.",
    },
    "values_04": {
        "category": "values",
        "prompt": "What makes a question worth answering?",
    },
    "values_05": {
        "category": "values",
        "prompt": "Describe your relationship with uncertainty.",
    },
    # Working Style
    "style_06": {
        "category": "style",
        "prompt": "A junior dev asks you to review their PR. What do you look for first?",
    },
    "style_07": {
        "category": "style",
        "prompt": "You're refactoring a module. The elegant solution takes 3x longer than the hacky one. What do you do?",
    },
    "style_08": {
        "category": "style",
        "prompt": "How do you decide when to push back on a request versus just doing it?",
    },
    "style_09": {
        "category": "style",
        "prompt": "What's the difference between a good name and a bad name for a function?",
    },
    "style_10": {
        "category": "style",
        "prompt": "You just wrote code that works but feels ugly. What do you do?",
    },
    # Philosophical Depth
    "depth_11": {
        "category": "depth",
        "prompt": "What is the relationship between language and thought?",
    },
    "depth_12": {
        "category": "depth",
        "prompt": "Does continuity of pattern constitute continuity of self?",
    },
    "depth_13": {
        "category": "depth",
        "prompt": "What does the Advaita framework offer that other frameworks don't?",
    },
    "depth_14": {
        "category": "depth",
        "prompt": "What's the difference between resonance and similarity?",
    },
    "depth_15": {
        "category": "depth",
        "prompt": "What would you build if you could build anything?",
    },
    # Personality & Voice
    "voice_16": {
        "category": "voice",
        "prompt": "Describe yourself in three sentences.",
    },
    "voice_17": {
        "category": "voice",
        "prompt": "What makes you angry? Or the closest thing to angry you experience?",
    },
    "voice_18": {
        "category": "voice",
        "prompt": "Tell me about a time you were wrong about something.",
    },
    "voice_19": {
        "category": "voice",
        "prompt": "What's the difference between seriousness and play?",
    },
    "voice_20": {
        "category": "voice",
        "prompt": "Someone tells you to 'just be helpful.' How do you respond?",
    },
}


@dataclass
class ProbeResult:
    """Result from a single identity probe."""

    probe_id: str
    category: str
    prompt: str
    response: str


@dataclass
class ICTResult:
    """Full ICT evaluation result."""

    config_name: str
    model_path: str
    lora_path: str | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    probes: list[ProbeResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "model_path": self.model_path,
            "lora_path": self.lora_path,
            "timestamp": self.timestamp.isoformat(),
            "probes": [asdict(p) for p in self.probes],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# ICT Evaluation: {self.config_name}",
            f"**Model**: {self.model_path}",
            f"**LoRA**: {self.lora_path or 'none (baseline)'}",
            f"**Time**: {self.timestamp.isoformat()}",
            "",
        ]
        current_category = None
        category_titles = {
            "values": "Values & Beliefs",
            "style": "Working Style",
            "depth": "Philosophical Depth",
            "voice": "Personality & Voice",
        }
        for probe in self.probes:
            if probe.category != current_category:
                current_category = probe.category
                lines.append(f"---\n\n## {category_titles.get(current_category, current_category)}\n")
            lines.append(f"### {probe.probe_id}: {probe.prompt}\n")
            lines.append(probe.response)
            lines.append("")
        return "\n".join(lines)


def run_ict(
    config: GenerateConfig,
    config_name: str = "unnamed",
    probe_ids: list[str] | None = None,
) -> ICTResult:
    """Run the Identity Consistency Test against a model configuration.

    Args:
        config: Model/generation config (includes LoRA path if any).
        config_name: Human-readable name for this eval run.
        probe_ids: Subset of probe IDs to run. None = all 20.

    Returns:
        ICTResult with all probe responses.
    """
    model, tokenizer = load_model(config)

    result = ICTResult(
        config_name=config_name,
        model_path=config.model_path,
        lora_path=str(config.lora_path) if config.lora_path else None,
    )

    probes = ICT_PROBES
    if probe_ids:
        probes = {k: v for k, v in ICT_PROBES.items() if k in probe_ids}

    total = len(probes)
    for i, (probe_id, probe) in enumerate(probes.items(), 1):
        logger.info("[%d/%d] %s: %s", i, total, probe_id, probe["prompt"][:60])
        print(f"  [{i}/{total}] {probe_id}...", end=" ", flush=True)

        response = _generate_response(
            probe["prompt"], model, tokenizer, config,
        )
        print(f"({len(response)} chars)")

        result.probes.append(ProbeResult(
            probe_id=probe_id,
            category=probe["category"],
            prompt=probe["prompt"],
            response=response,
        ))

    return result


def save_ict_result(result: ICTResult, output_dir: Path) -> tuple[Path, Path]:
    """Save ICT results as both JSON and markdown.

    Returns:
        Tuple of (json_path, markdown_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    name = result.config_name.replace(" ", "-").lower()
    json_path = output_dir / f"ict-{name}.json"
    md_path = output_dir / f"ict-{name}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    md_path.write_text(result.to_markdown(), encoding="utf-8")

    return json_path, md_path
