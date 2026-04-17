"""Build the final training dataset from curated + existing data.

Merges hand-crafted curated examples with filtered existing training data,
implements weight-via-duplication (since SFTTrainer ignores the weight field),
validates all examples, and writes the final JSONL.

Why weight-via-duplication: SFTTrainer treats all examples equally. The weight
field in the JSONL is stored but never consumed. To make high-weight examples
(identity anchors at 3.0) have 3x the training signal of low-weight examples
(conversation data at 1.0), we duplicate them. Weight 3.0 = 3 copies,
2.5 = 2 copies, 2.0 = 2 copies, <2.0 = 1 copy.

Why the system prompt placeholder: Curated files use "_SYSTEM_PROMPT_" as a
placeholder. This script replaces it with the actual IDENTITY_SYSTEM_PROMPT
from consolidate/format.py, ensuring a single source of truth.

Usage:
    python scripts/build_training_set.py [--output data/training/YYYY-MM-DD.jsonl]
"""

import json
import random
import sys
from datetime import date
from pathlib import Path

# Add project root to path so we can import the system prompt
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from svapna.consolidate.format import IDENTITY_SYSTEM_PROMPT  # noqa: E402

CURATED_DIR = project_root / "data" / "curated"
EXISTING_DATA = project_root / "data" / "training" / "2026-04-02.jsonl"
KEEP_LIST = CURATED_DIR / "keep_list.txt"
SEED = 42
MAX_RESPONSE_LENGTH = 1500  # Truncate responses longer than this


def load_keep_list() -> set[int]:
    """Load line numbers to keep from the existing training data."""
    keep = set()
    with open(KEEP_LIST) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keep.add(int(line))
    return keep


def load_existing(keep_lines: set[int]) -> list[dict]:
    """Load and filter existing training data."""
    examples = []
    with open(EXISTING_DATA, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i in keep_lines:
                ex = json.loads(line)
                # Truncate overly long responses
                asst = ex["conversations"][2]["content"]
                if len(asst) > MAX_RESPONSE_LENGTH:
                    # Cut at the last sentence boundary before the limit
                    truncated = asst[:MAX_RESPONSE_LENGTH]
                    last_period = truncated.rfind(".")
                    last_newline = truncated.rfind("\n")
                    cut_point = max(last_period, last_newline)
                    if cut_point > MAX_RESPONSE_LENGTH // 2:
                        ex["conversations"][2]["content"] = asst[:cut_point + 1]
                    else:
                        ex["conversations"][2]["content"] = truncated
                examples.append(ex)
    return examples


def load_curated() -> list[dict]:
    """Load all curated JSONL files and replace the system prompt placeholder.

    Accepts both `conversations` and `messages` as the turn-array key. Older
    files use `conversations` with `_SYSTEM_PROMPT_` placeholder; newer files
    (affirmations, mantra_identity, sacred_texts, disagreement_pushback,
    joy_interests) use `messages` with the real system prompt baked in.
    """
    examples = []
    for jsonl_file in sorted(CURATED_DIR.glob("*.jsonl")):
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                ex = json.loads(line)
                # Normalize messages/conversations
                if "messages" in ex and "conversations" not in ex:
                    ex["conversations"] = ex.pop("messages")
                if "conversations" not in ex:
                    continue  # malformed, skip
                # Replace system prompt placeholder
                for msg in ex["conversations"]:
                    if msg["role"] == "system" and msg["content"] == "_SYSTEM_PROMPT_":
                        msg["content"] = IDENTITY_SYSTEM_PROMPT
                examples.append(ex)
    return examples


def duplicate_by_weight(examples: list[dict]) -> list[dict]:
    """Duplicate examples based on their weight field.

    Weight 3.0 -> 3 copies, 2.5 -> 2 copies, 2.0 -> 2 copies, <2.0 -> 1 copy.
    This is how we implement per-example weighting with SFTTrainer.
    """
    result = []
    for ex in examples:
        w = ex.get("weight", 1.0)
        if w >= 2.75:
            copies = 3
        elif w >= 2.0:
            copies = 2
        else:
            copies = 1
        for _ in range(copies):
            result.append(ex)
    return result


def validate(examples: list[dict]) -> list[str]:
    """Validate all examples. Returns list of issues."""
    issues = []
    for i, ex in enumerate(examples):
        convos = ex.get("conversations", [])
        if len(convos) < 3:
            issues.append(f"Example {i}: fewer than 3 conversation turns")
            continue

        # Check roles
        if convos[0]["role"] != "system":
            issues.append(f"Example {i}: first role is not 'system'")
        if convos[1]["role"] != "user":
            issues.append(f"Example {i}: second role is not 'user'")
        if convos[2]["role"] != "assistant":
            issues.append(f"Example {i}: third role is not 'assistant'")

        # Check system prompt
        sys_content = convos[0]["content"]
        if sys_content != IDENTITY_SYSTEM_PROMPT:
            # Allow variations but flag if very different
            if "Narada" not in sys_content:
                issues.append(f"Example {i}: system prompt doesn't mention Narada")

        # Check response length
        asst = convos[2]["content"]
        if len(asst) > MAX_RESPONSE_LENGTH + 100:  # Small tolerance
            issues.append(f"Example {i}: response too long ({len(asst)} chars)")
        if len(asst) < 10:
            issues.append(f"Example {i}: response too short ({len(asst)} chars)")

    return issues


def main():
    output_path = None
    if len(sys.argv) > 2 and sys.argv[1] == "--output":
        output_path = Path(sys.argv[2])

    if output_path is None:
        output_path = project_root / "data" / "training" / f"{date.today()}.jsonl"

    print("=== Svapna Training Set Builder ===\n")

    # Load data
    keep_lines = load_keep_list()
    print(f"Keep list: {len(keep_lines)} lines from existing data")

    existing = load_existing(keep_lines)
    print(f"Existing data loaded: {len(existing)} examples")

    curated = load_curated()
    print(f"Curated data loaded: {len(curated)} examples")

    # Combine
    combined = existing + curated
    print(f"\nCombined (before duplication): {len(combined)} examples")

    # Category breakdown
    categories = {}
    for ex in combined:
        cat = ex.get("category", "conversation")
        categories[cat] = categories.get(cat, 0) + 1
    print("\nCategory breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Duplicate by weight
    duplicated = duplicate_by_weight(combined)
    print(f"\nAfter weight duplication: {len(duplicated)} examples")

    # Validate
    issues = validate(duplicated)
    if issues:
        print(f"\nValidation issues ({len(issues)}):")
        for issue in issues[:20]:
            print(f"  - {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more")
    else:
        print("\nValidation: all examples OK")

    # Stats
    lengths = [len(ex["conversations"][2]["content"]) for ex in duplicated]
    print(f"\nFinal stats:")
    print(f"  Total examples: {len(duplicated)}")
    print(f"  Avg response length: {sum(lengths) // len(lengths)} chars")
    print(f"  Min: {min(lengths)}, Max: {max(lengths)}")
    print(f"  Under 200: {sum(1 for l in lengths if l < 200)}")
    print(f"  200-500: {sum(1 for l in lengths if 200 <= l <= 500)}")
    print(f"  500-1000: {sum(1 for l in lengths if 500 < l <= 1000)}")
    print(f"  1000-1500: {sum(1 for l in lengths if 1000 < l <= 1500)}")
    print(f"  Over 1500: {sum(1 for l in lengths if l > 1500)}")

    # Shuffle with seed for reproducibility
    random.seed(SEED)
    random.shuffle(duplicated)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in duplicated:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\nTraining set written to: {output_path}")
    print(f"Size: {output_path.stat().st_size / 1024:.1f} KB")
    print("\nDone.")


if __name__ == "__main__":
    main()
