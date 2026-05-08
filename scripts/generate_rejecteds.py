"""Generate 'rejected' counterparts for every curated row using the base model.

Part of E1.2 — ORPO needs (chosen, rejected) pairs. For every curated row,
`chosen` is the existing assistant content, `rejected` is what the BASE
model (no LoRA) produces for the same prompt. Saves sidecar files so
build_training_set.py can assemble preference pairs at build time.

Output: `data/curated/_rejected/{filename}` — same schema as input, but
assistant content is base-model-generated.

Reproducible via fixed seed. Cached — skips any rows that already have a
rejected in the sidecar.

Usage:
    python scripts/generate_rejecteds.py                # all curated files
    python scripts/generate_rejecteds.py --file mantra_subject.jsonl  # one file
    python scripts/generate_rejecteds.py --force        # regenerate everything
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from svapna.identity.generate import GenerateConfig, load_model, _generate_response


CURATED_DIR = project_root / "data" / "curated"
REJECTED_DIR = CURATED_DIR / "_rejected"
SEED = 42


def extract_messages(row: dict) -> list[dict]:
    """Normalize messages/conversations key."""
    return row.get("messages") or row.get("conversations") or []


def get_turn_key(row: dict) -> str:
    """Return 'messages' or 'conversations' — whichever the row uses."""
    return "messages" if "messages" in row else "conversations"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default=None,
                        help="Process just one file (basename)")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if sidecar exists")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of rows per file (for smoke testing)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    REJECTED_DIR.mkdir(exist_ok=True)

    # Base model only — no LoRA
    config = GenerateConfig.from_config()
    config.lora_path = None  # critical: base model generation
    # Use deterministic-ish sampling for reproducibility
    config.temperature = 0.7
    config.top_p = 0.9
    config.max_new_tokens = 600  # keep tight; rejecteds don't need to be long

    print(f"Base model: {config.model_path}")
    print(f"LoRA: None (base model only)")

    model, tokenizer = load_model(config)
    # Set torch seed for reproducibility
    import torch
    torch.manual_seed(SEED)

    # Discover files
    if args.file:
        files = [CURATED_DIR / args.file]
    else:
        files = sorted(CURATED_DIR.glob("*.jsonl"))

    total_generated = 0
    total_skipped = 0
    start = time.time()

    for src in files:
        if src.parent != CURATED_DIR:
            continue
        sidecar = REJECTED_DIR / src.name
        print(f"\n=== {src.name} ===")

        # Load source rows
        with open(src, encoding="utf-8") as f:
            src_rows = [json.loads(line) for line in f if line.strip()]

        # Load existing sidecar if present (for incremental)
        existing: dict[int, dict] = {}
        if sidecar.exists() and not args.force:
            with open(sidecar, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if line.strip():
                        existing[i] = json.loads(line)

        # Process rows, streaming output
        with open(sidecar, "w", encoding="utf-8") as out:
            for i, row in enumerate(src_rows):
                if args.limit and i >= args.limit:
                    break

                turn_key = get_turn_key(row)
                messages = extract_messages(row)
                if len(messages) < 3:
                    print(f"  [{i}] skip: <3 turns")
                    continue

                # Skip if already have rejected (and not forcing)
                if i in existing and not args.force:
                    out.write(json.dumps(existing[i], ensure_ascii=False) + "\n")
                    total_skipped += 1
                    print(f"  [{i}] cached")
                    continue

                # Extract the user prompt. Temporarily override the
                # system prompt inside _generate_response via the messages
                # list directly — we can't reuse _generate_response because
                # it hard-codes IDENTITY_SYSTEM_PROMPT. Generate inline.
                input_text = tokenizer.apply_chat_template(
                    [{"role": m["role"], "content": m["content"]}
                     for m in messages[:-1]],  # drop the assistant turn
                    tokenize=False, add_generation_prompt=True,
                    enable_thinking=False,
                )
                inputs = tokenizer(input_text, return_tensors="pt").to(model.device)
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=config.max_new_tokens,
                    temperature=config.temperature,
                    top_p=config.top_p,
                    repetition_penalty=config.repetition_penalty,
                    do_sample=True,
                )
                rejected_text = tokenizer.decode(
                    outputs[0][inputs["input_ids"].shape[1]:],
                    skip_special_tokens=True,
                ).strip()

                # Build sidecar row — same schema, assistant content replaced
                new_row = dict(row)
                new_messages = [dict(m) for m in messages]
                new_messages[-1] = {"role": "assistant", "content": rejected_text}
                new_row[turn_key] = new_messages
                new_row["_rejected_source"] = "base_qwen3_8b_seed42"

                out.write(json.dumps(new_row, ensure_ascii=False) + "\n")
                out.flush()
                total_generated += 1
                elapsed = time.time() - start
                print(f"  [{i}] gen ({len(rejected_text)} chars, {elapsed:.0f}s elapsed)")

    total_time = time.time() - start
    print(f"\nDone. Generated: {total_generated}, Cached: {total_skipped}, "
          f"Time: {total_time / 60:.1f} min")


if __name__ == "__main__":
    main()
