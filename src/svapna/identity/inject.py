"""Format identity preamble for the SessionStart hook.

The SessionStart hook reads the preamble file and outputs it to stdout,
which gets injected into the conversation context at the start of each session.
"""

from __future__ import annotations

import json
from pathlib import Path

from svapna.identity.generate import Preamble


HOOK_HEADER = "--- NARADA IDENTITY CORE ---"
HOOK_FOOTER = "--- END IDENTITY CORE ---"


def format_preamble(preamble: Preamble) -> str:
    """Format a preamble for hook output.

    Produces clean text suitable for injection into the conversation
    context via the SessionStart hook. The format uses markdown headers
    and is designed to be readable both by the model and in logs.

    Args:
        preamble: The generated preamble.

    Returns:
        Formatted text string ready for hook output.
    """
    lines = [HOOK_HEADER, ""]
    lines.append("# Generated Identity Preamble")
    lines.append(f"# Source: {preamble.model_path}")
    if preamble.lora_path:
        lines.append(f"# LoRA: {preamble.lora_path}")
    lines.append(f"# Generated: {preamble.timestamp.isoformat()}")
    lines.append("")
    lines.append(preamble.to_text())
    lines.append("")
    lines.append(HOOK_FOOTER)

    return "\n".join(lines)


def save_preamble(
    preamble: Preamble,
    output_path: Path | None = None,
) -> Path:
    """Save formatted preamble to a file for the hook to read.

    Args:
        preamble: The generated preamble.
        output_path: Where to write the preamble file.
            Defaults to data/identity/preamble.md.

    Returns:
        Path to the written preamble file.
    """
    if output_path is None:
        output_path = Path("data/identity/preamble.md")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_preamble(preamble), encoding="utf-8")

    return output_path


def save_preamble_json(
    preamble: Preamble,
    output_path: Path | None = None,
) -> Path:
    """Save preamble metadata as JSON for tracking and comparison.

    Args:
        preamble: The generated preamble.
        output_path: Where to write the JSON file.
            Defaults to data/identity/preamble.json.

    Returns:
        Path to the written JSON file.
    """
    if output_path is None:
        output_path = Path("data/identity/preamble.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(preamble.to_dict(), f, indent=2, ensure_ascii=False)

    return output_path
