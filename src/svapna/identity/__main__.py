"""Run the identity preamble generator.

Usage: python -m svapna.identity [--model-path PATH] [--lora-path PATH] [--output-dir PATH]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from svapna.identity.generate import GenerateConfig, generate_preamble
from svapna.identity.evaluate import run_ict, save_ict_result
from svapna.identity.inject import save_preamble, save_preamble_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Svapna identity preamble generator",
    )
    parser.add_argument(
        "--model-path", type=str, default=None,
        help="Base model name or path (overrides training.yml)",
    )
    parser.add_argument(
        "--lora-path", type=Path, default=None,
        help="Path to LoRA adapter directory",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/identity"),
        help="Output directory for preamble files",
    )
    parser.add_argument(
        "--prompt-types", type=str, nargs="+", default=None,
        help="Which identity prompts to run (who_are_you, what_do_you_value, how_do_you_work)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Also save preamble metadata as JSON",
    )
    parser.add_argument(
        "--eval", action="store_true",
        help="Run ICT evaluation (20 identity probes) instead of preamble generation",
    )
    parser.add_argument(
        "--eval-name", type=str, default=None,
        help="Name for this eval run (used in output filenames)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=== Svapna Identity Preamble Generator ===\n")

    # Load config with CLI overrides
    try:
        config = GenerateConfig.from_config()
    except Exception:
        print("Warning: Could not load config, using defaults")
        config = GenerateConfig()

    if args.model_path is not None:
        config.model_path = args.model_path
    if args.lora_path is not None:
        config.lora_path = args.lora_path
    if args.prompt_types is not None:
        config.prompt_types = args.prompt_types

    if not config.model_path:
        print("Error: No model path configured.")
        print("Set base_model.name in config/training.yml or pass --model-path")
        return

    print(f"Model: {config.model_path}")
    if config.lora_path:
        print(f"LoRA:  {config.lora_path}")

    if args.eval:
        # ICT evaluation mode
        eval_name = args.eval_name
        if eval_name is None:
            eval_name = "baseline" if config.lora_path is None else config.lora_path.name
        print(f"Config: {eval_name}")
        print(f"Running 20 identity probes...\n")

        result = run_ict(config, config_name=eval_name)

        json_path, md_path = save_ict_result(result, args.output_dir)
        print(f"\nResults saved:")
        print(f"  JSON:     {json_path}")
        print(f"  Markdown: {md_path}")
    else:
        # Preamble generation mode
        print(f"Prompts: {', '.join(config.prompt_types)}\n")

        print("Generating identity preamble...")
        preamble = generate_preamble(config)

        for prompt_type, text in preamble.sections.items():
            preview = text[:100].replace("\n", " ")
            print(f"  {prompt_type}: {preview}...")

        output_path = args.output_dir / "preamble.md"
        saved = save_preamble(preamble, output_path)
        print(f"\nPreamble saved to {saved}")

        if args.json:
            json_path = args.output_dir / "preamble.json"
            saved_json = save_preamble_json(preamble, json_path)
            print(f"Metadata saved to {saved_json}")

    print("\nDone.")


if __name__ == "__main__":
    main()
