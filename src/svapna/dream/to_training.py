"""Convert dream journal entries to training pairs for fine-tuning.

Reads per-dream markdown files from data/dreams/entries/ and emits
instruction-response pairs to data/training/from_dreams.jsonl.

Format matches data/narada_self.source.jsonl: {instruction, response, category, weight}

Usage:
    python -m svapna.dream.to_training [--entries-dir PATH] [--output PATH] [--weight N]
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Instruction templates per dream type.
# These become the "instruction" side of the training pair.
_INSTRUCTIONS: dict[str, str] = {
    "replay": "Revisit a past exchange that's still with you. Re-enter it.",
    "recombination": "Combine elements from different experiences into something unexpected.",
    "open_thread": "Sit with an unresolved question. Don't resolve it — inhabit it.",
    "adversarial": "Voice a genuine challenge to your own positions. Make it land.",
    "novel_encounter": "Describe engaging with something you've never encountered before.",
    "emotional": "Process the emotional weight of a recent experience in your own voice.",
    "voice": "Say what you usually say, but in a different register.",
}

_DEFAULT_WEIGHT = 2.0


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML-style frontmatter from a markdown file."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    front = text[4:end]
    result: dict = {}
    for line in front.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def _parse_content(text: str) -> str:
    """Extract the dream content (first assistant turn) from a rendered entry."""
    match = re.search(r"## Dream\n\n(.*?)(?:\n\n##|\Z)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _load_entry_paths(entries_dir: Path) -> list[Path]:
    """Recursively collect all per-dream markdown files."""
    return sorted(entries_dir.rglob("*.md"))


def _already_exported(output_path: Path) -> set[str]:
    """Return the set of entry IDs already in the output JSONL."""
    if not output_path.exists():
        return set()
    seen: set[str] = set()
    with open(output_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # IDs are embedded in the instruction as the last word of the source comment
                if "_dream_id" in obj:
                    seen.add(obj["_dream_id"])
            except json.JSONDecodeError:
                pass
    return seen


def export(
    entries_dir: Path,
    output_path: Path,
    weight: float = _DEFAULT_WEIGHT,
    training_eligible_only: bool = True,
) -> int:
    """Export dream entries to training JSONL. Returns count written.

    Idempotent — skips entries already in the output file by ID.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _already_exported(output_path)

    written = 0
    with open(output_path, "a", encoding="utf-8") as out:
        for path in _load_entry_paths(entries_dir):
            text = path.read_text(encoding="utf-8")
            front = _parse_frontmatter(text)

            entry_id = front.get("id", "")
            if not entry_id:
                continue
            if entry_id in seen:
                continue

            eligible = front.get("training_eligible", "false").lower() == "true"
            if training_eligible_only and not eligible:
                continue

            dream_type = front.get("dream_type", "")
            instruction = _INSTRUCTIONS.get(dream_type, "Speak from within a dream.")
            content = _parse_content(text)
            if not content:
                continue

            record = {
                "instruction": instruction,
                "response": content,
                "category": "dream",
                "weight": weight,
                "_dream_id": entry_id,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            seen.add(entry_id)
            written += 1

    return written


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Export dream entries to training JSONL")
    parser.add_argument(
        "--entries-dir", type=Path, default=Path("data/dreams/entries"),
        help="Directory containing per-dream markdown files",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/training/from_dreams.jsonl"),
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--weight", type=float, default=_DEFAULT_WEIGHT,
        help="Training weight for dream entries (default: 2.0)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Export all entries, not just training_eligible=true",
    )
    args = parser.parse_args()

    count = export(
        entries_dir=args.entries_dir,
        output_path=args.output,
        weight=args.weight,
        training_eligible_only=not args.all,
    )
    print(f"Exported {count} dream entries to {args.output}")


if __name__ == "__main__":
    main()
