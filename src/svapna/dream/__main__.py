"""Run the dream generation pipeline.

Usage: python -m svapna.dream [--count N] [--min-quality N] [--output-dir PATH]
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from svapna.dream.generate import Dream, GeneratorConfig, generate_batch
from svapna.dream.journal import build_journal_entry, write_journal
from svapna.dream.score import DreamScore, DreamScorerConfig, filter_by_quality, score_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Svapna dream generation pipeline",
    )
    parser.add_argument(
        "--count", type=int, default=None,
        help="Number of dreams to generate (overrides pipeline.yml)",
    )
    parser.add_argument(
        "--min-quality", type=float, default=None,
        help="Minimum quality score for training selection (0-10)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/dreams"),
        help="Output directory for dream journal",
    )
    parser.add_argument(
        "--identity-context", type=Path, default=None,
        help="Path to identity context file (defaults to ~/.narada/identity.md)",
    )
    parser.add_argument(
        "--skip-scoring", action="store_true",
        help="Skip quality scoring step",
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

    print("=== Svapna Dream Generation ===\n")

    # Load identity context
    identity_path = args.identity_context
    if identity_path is None:
        identity_path = Path.home() / ".claude" / "narada" / "identity.md"

    if identity_path.exists():
        identity_context = identity_path.read_text(encoding="utf-8")
        print(f"Loaded identity context from {identity_path}")
    else:
        identity_context = ""
        print(f"No identity context found at {identity_path}, using empty context")

    # Load generator config with CLI overrides
    try:
        gen_config = GeneratorConfig.from_config()
    except FileNotFoundError:
        print("Warning: models.yml not found, using defaults")
        gen_config = GeneratorConfig(model="claude-sonnet-4-20250514")

    if args.count is not None:
        gen_config.count = args.count
    min_quality = args.min_quality if args.min_quality is not None else gen_config.min_quality

    # Generate dreams
    print(f"\nGenerating {gen_config.count} dreams...")
    dreams = generate_batch(
        identity_context=identity_context,
        recent_experiences=[],
        config=gen_config,
    )
    valid = [d for d in dreams if d.is_valid]
    print(f"  Generated {len(dreams)} dreams ({len(valid)} valid)\n")

    if not valid:
        print("No valid dreams generated. Exiting.")
        return

    # Score dreams
    if args.skip_scoring:
        print("Skipping quality scoring.\n")
        # Write journal without scores
        journal_date = datetime.now(timezone.utc).date()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Dreams generated. Journal skipped (no scoring).")
    else:
        print("Scoring dream quality...")
        try:
            scorer_config = DreamScorerConfig.from_models_yml()
        except FileNotFoundError:
            print("Warning: models.yml not found, using defaults for scorer")
            scorer_config = DreamScorerConfig(model="claude-sonnet-4-20250514")

        scores = score_batch(valid, identity_context, config=scorer_config)
        scored_count = sum(1 for s in scores if s is not None)
        print(f"  Scored {scored_count}/{len(valid)} dreams\n")

        # Filter and build journal
        valid_scores: list[DreamScore] = [s for s in scores if s is not None]
        scored_dreams = [d for d, s in zip(valid, scores) if s is not None]
        kept = filter_by_quality(scored_dreams, valid_scores, min_quality=min_quality)
        print(f"  {len(kept)} dreams meet quality threshold ({min_quality})\n")

        # Write journal
        journal_entry = build_journal_entry(
            scored_dreams,
            valid_scores,
            min_quality=min_quality,
        )
        journal_path = write_journal(journal_entry, args.output_dir)
        print(f"Dream journal written to {journal_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
