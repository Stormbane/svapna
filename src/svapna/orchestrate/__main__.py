"""Run the nightly pipeline.

Usage: python -m svapna.orchestrate [--step STEP] [--no-train] [--resume]
       python -m svapna.nightly  (alias)
"""

from __future__ import annotations

import argparse
import logging
import sys

from svapna.orchestrate.config import PipelineConfig
from svapna.orchestrate.nightly import ALL_STEPS, Step, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Svapna nightly pipeline orchestrator",
    )
    parser.add_argument(
        "--step", type=str, action="append", default=None,
        help=(
            "Run only specific step(s). Can be repeated. "
            "Valid steps: consolidate, dream, score, prepare, train, evaluate"
        ),
    )
    parser.add_argument(
        "--no-train", action="store_true",
        help="Skip the training step",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from the last completed step of today's run",
    )
    parser.add_argument(
        "--from-step", type=str, default=None,
        help="Start from a specific step (skipping earlier steps)",
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

    print("=== Svapna Nightly Pipeline ===\n")

    config = PipelineConfig.load()

    # Resolve steps to run
    steps: list[Step] | None = None
    if args.step:
        steps = [Step.from_name(s) for s in args.step]
    elif args.from_step:
        from_step = Step.from_name(args.from_step)
        steps = [s for s in ALL_STEPS if s >= from_step]

    results = run_pipeline(
        steps=steps,
        skip_training=args.no_train,
        resume=args.resume,
        config=config,
    )

    # Print summary
    print("\n=== Pipeline Summary ===\n")
    for result in results:
        icon = {"success": "+", "skipped": "-", "failed": "!"}[result.status]
        print(f"  [{icon}] {result.step}: {result.message}")

    failed = [r for r in results if r.status == "failed"]
    if failed:
        print(f"\n{len(failed)} step(s) failed.")
        sys.exit(1)
    else:
        print("\nAll steps completed successfully.")


if __name__ == "__main__":
    main()
