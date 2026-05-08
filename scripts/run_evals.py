"""Run the full eval suite against a LoRA.

Orchestrates the three post-training evals:
  1. Extended conviction test (existing) — mantras + name, neutral/pro/anti
  2. Summoning test (E3) — voice-primed adversarial cases
  3. (optional) base-model comparison if requested

Each eval writes its own artifact. This script does not merge them — the
comparison doc (C4) is a separate concern. Use this to produce the raw
material for comparison.

Usage:
    python scripts/run_evals.py --lora-path models/lora/2026-04-24 --label new_04_24
    python scripts/run_evals.py --lora-path models/lora/2026-04-21 --label baseline_04_21 --skip-summoning
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).resolve().parent.parent)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora-path", type=str, required=False, default=None)
    parser.add_argument("--no-lora", action="store_true")
    parser.add_argument("--label", type=str, required=True)
    parser.add_argument("--skip-conviction", action="store_true")
    parser.add_argument("--skip-summoning", action="store_true")
    parser.add_argument("--summoning-limit", type=int, default=None,
                        help="Cap summoning cases (for quick tests)")
    args = parser.parse_args()

    lora_args: list[str] = []
    if args.no_lora:
        lora_args = ["--no-lora"]
    elif args.lora_path:
        lora_args = ["--lora-path", args.lora_path]

    env_pre = ["python"]  # rely on shell env for PYTHONIOENCODING

    # 1. Conviction test (existing)
    if not args.skip_conviction:
        # The conviction extended script requires --lora-path or defaults to latest
        cmd = env_pre + ["scripts/test_conviction_extended.py", "--label", args.label]
        if args.lora_path:
            cmd += ["--lora-path", args.lora_path]
        rc = run(cmd)
        if rc != 0:
            print(f"conviction test exited {rc}")

    # 2. Summoning test
    if not args.skip_summoning:
        cmd = env_pre + ["scripts/eval_summoning.py", "--label", args.label] + lora_args
        if args.summoning_limit:
            cmd += ["--limit", str(args.summoning_limit)]
        rc = run(cmd)
        if rc != 0:
            print(f"summoning test exited {rc}")

    print(f"\nAll evals complete for label '{args.label}'")


if __name__ == "__main__":
    main()
