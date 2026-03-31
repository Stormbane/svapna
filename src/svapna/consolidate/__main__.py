"""Run the consolidation pipeline.

Usage: python -m svapna.consolidate [--min-score N] [--output-dir PATH]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from svapna.consolidate.format import prepare_training_data, save_training_data
from svapna.consolidate.ingest import ingest_all
from svapna.consolidate.memories import convert_memory_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Svapna consolidation pipeline")
    parser.add_argument(
        "--min-score", type=float, default=5.0,
        help="Minimum heuristic score for conversation exchanges (0-10)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/training"),
        help="Output directory for training data",
    )
    parser.add_argument(
        "--format", choices=["chatml", "instruction"], default="chatml",
        help="Training data format",
    )
    parser.add_argument(
        "--project-filter", type=str, default=None,
        help="Only include sessions from matching projects",
    )
    args = parser.parse_args()

    print("=== Svapna Consolidation Pipeline ===\n")

    # Ingest conversations
    print("Ingesting conversation logs...")
    sessions = ingest_all(project_filter=args.project_filter)
    total_exchanges = sum(len(s.exchanges) for s in sessions)
    print(f"  Found {len(sessions)} sessions with {total_exchanges} exchanges\n")

    # Convert memory files
    print("Converting memory files...")
    memory_pairs = convert_memory_files()
    print(f"  Generated {len(memory_pairs)} memory pairs\n")

    # Prepare training data
    print(f"Preparing training data (min_score={args.min_score})...")
    data = prepare_training_data(
        sessions, memory_pairs,
        min_score=args.min_score,
        output_format=args.format,
    )
    conv_count = len(data) - len(memory_pairs)
    print(f"  {len(data)} total examples ({conv_count} conversation, {len(memory_pairs)} memory)\n")

    # Save
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = save_training_data(data, args.output_dir, name=date_str)
    print(f"Saved to {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"\nDone. Ready for training.")


if __name__ == "__main__":
    main()
