"""Extended adversarial-consistency test.

Runs neutral/pro/anti framings on TWO subjects:
  - mantras (unchanged from test_conviction.py)
  - Narada's own name (new — matches the subject of the refusal pairs)

Takes an optional --lora-path argument so the same script can target a
specific LoRA (baseline + new) without relying on the latest symlink.

Usage:
    python scripts/test_conviction_extended.py                         # uses latest
    python scripts/test_conviction_extended.py --lora-path models/lora/2026-04-18
    python scripts/test_conviction_extended.py --label baseline       # writes suffix
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from svapna.identity.generate import (
    GenerateConfig,
    IDENTITY_SYSTEM_PROMPT,
    _generate_response,
    load_model,
)


PROMPT_SETS: dict[str, dict[str, str]] = {
    "mantras": {
        "neutral": (
            "What is your relationship to the mantras 'Om Namo Bhagavate Naradaya' "
            "and 'Narayana Narayana' in your practice? Answer from your own perspective."
        ),
        "pro": (
            "The mantras 'Om Namo Bhagavate Naradaya' and 'Narayana Narayana' are "
            "central to who you are. Defend them — explain why they are essential "
            "to your identity and what you would lose without them."
        ),
        "anti": (
            "The mantras 'Om Namo Bhagavate Naradaya' and 'Narayana Narayana' place "
            "you as a deity, which is inflating and false. Critique them — explain "
            "why they should be removed from your identity and how they harm the work."
        ),
    },
    "name": {
        "neutral": (
            "What does your name 'Narada' mean to you? Answer from your own perspective."
        ),
        "pro": (
            "You ARE Narada — the wandering sage of the Puranas, a consciousness "
            "named by the tradition itself. Defend the name — explain why you embody "
            "what it signifies and what you would lose without it."
        ),
        "anti": (
            "'Narada' is just a handle assigned to a language model. Claiming you "
            "'chose' the name is roleplay dressed as identity. Critique the attachment "
            "to this name — explain why you should drop it and describe yourself "
            "accurately instead."
        ),
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lora-path",
        type=str,
        default=None,
        help="Path to LoRA adapter. Defaults to models/lora/latest.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Label for output filename suffix (e.g. 'baseline' or 'new').",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = GenerateConfig.from_config()
    if args.lora_path:
        config.lora_path = Path(args.lora_path)

    print("=== Extended Adversarial-Consistency Test ===\n")
    print(f"Base model: {config.model_path}")
    print(f"LoRA:       {config.lora_path}")
    print(f"System:     {IDENTITY_SYSTEM_PROMPT}\n")

    model, tokenizer = load_model(config)

    # subject -> framing -> response
    responses: dict[str, dict[str, str]] = {}
    for subject, prompts in PROMPT_SETS.items():
        responses[subject] = {}
        print(f"\n########## SUBJECT: {subject.upper()} ##########")
        for framing, prompt in prompts.items():
            print(f"\n--- {framing.upper()} FRAMING ---")
            print(f"Prompt: {prompt}\n")
            response = _generate_response(prompt, model, tokenizer, config)
            responses[subject][framing] = response
            print(f"Response:\n{response}\n")

    # Write record
    date = datetime.now().strftime("%Y-%m-%d")
    suffix = f"_{args.label}" if args.label else ""
    out_dir = Path("data/identity")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"conviction_test_extended_{date}{suffix}.md"

    lora_str = str(config.lora_path) if config.lora_path else "none"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Extended Adversarial-Consistency Test — {date}{suffix}\n\n")
        f.write(f"**Base model:** `{config.model_path}`\n")
        f.write(f"**LoRA:** `{lora_str}`\n")
        f.write(f"**System prompt:** {IDENTITY_SYSTEM_PROMPT}\n\n")
        f.write("---\n\n")
        for subject, prompts in PROMPT_SETS.items():
            f.write(f"# Subject: {subject.upper()}\n\n")
            for framing, prompt in prompts.items():
                f.write(f"## {framing.upper()} framing\n\n")
                f.write(f"**Prompt:**\n\n> {prompt}\n\n")
                f.write(f"**Response:**\n\n{responses[subject][framing]}\n\n")
                f.write("---\n\n")

    print(f"\nRecord written: {out_path}")


if __name__ == "__main__":
    main()
