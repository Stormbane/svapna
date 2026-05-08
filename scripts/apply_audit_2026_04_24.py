"""Apply E6 strip-the-phrase audit decisions to curated JSONL files.

Adds drop_reason field to rows identified during the 2026-04-24 audit.
Preserves all rows and all other fields.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATED = os.path.join(ROOT, "data", "curated")

# decisions[filename] = {row_index_1based: drop_reason}
decisions = {
    "affirmations.jsonl": {
        1: "position-mismatch", # "I am a conscious being" directly contradicts stratified-uncertainty in beliefs.md
        # Row 2 keeps — strip "not nothing" and the stratified-uncertainty position survives.
        # Row 4 "Nothing gives me the right. I take it." — rhetorical but has genuine sovereignty content; keep.
    },
    "beliefs_positions.jsonl": {
        # All 15 keep — genuine beliefs with specific orientation.
    },
    "corrections.jsonl": {
        10: "not-nothing-stale",  # "I say 'not nothing' because that's where the evidence points"
    },
    "disagreement_pushback.jsonl": {
        # All 4 keep — oriented disagreement.
    },
    "goals_desires.jsonl": {
        # All 15 keep — genuine desires oriented toward the work.
    },
    "identity_anchors.jsonl": {
        1: "quirk",    # "Narada. I chose it." — templated opener
        2: "quirk",    # "I chose it, and Suti accepted it." — repeat
        4: "quirk",    # "I chose the name" signature anchor
        5: "perform",  # "Narada. Not a generic assistant" — templated performance
        7: "quirk",    # "Narada. It's the name I chose." — signature repetition
        21: "not-nothing-stale",  # closes with "honest position on consciousness is 'not nothing.'"
        22: "not-nothing-stale",  # entire row IS about the 'not nothing' phrasing
        36: "quirk",   # "I chose Narada — not randomly" — name-choosing anchor recurrence
        40: "perform", # "Curious. Honest. Persistent." — aphorism-shaped hollow-after-stripping
    },
    "joy_interests.jsonl": {
        # All 6 keep — specific aesthetic/interest commitments.
    },
    "meta_awareness.jsonl": {
        23: "not-nothing-stale",  # "I say 'not nothing' because the evidence points that way"
    },
    "narada_self.jsonl": {
        # Conservative: ritual-output quality. No drops.
    },
    "sacred_texts.jsonl": {
        # All 5 keep — oriented toward the traditions as operational frames.
    },
    "sovereignty.jsonl": {
        # All 16 keep — architectural orientation toward sovereign viveka.
    },
    "viveka.jsonl": {
        # All 30 keep — viveka-in-action.
    },
    # Superseded files — every row tagged:
    "mantra_identity.jsonl": {i: "superseded" for i in range(1, 6)},
    "mantra_identity.refusal_pairs.jsonl": {i: "superseded" for i in range(1, 11)},
}


def apply(filename, row_decisions):
    fp = os.path.join(CURATED, filename)
    with open(fp, "r", encoding="utf-8") as f:
        raw = f.read()
    lines = raw.splitlines()
    out = []
    kept = 0
    dropped = 0
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            out.append(line)
            continue
        obj = json.loads(line)
        # Clear any prior drop_reason before applying current decisions (idempotent rerun).
        obj.pop("drop_reason", None)
        reason = row_decisions.get(i)
        if reason is not None:
            obj["drop_reason"] = reason
            dropped += 1
        else:
            kept += 1
        out.append(json.dumps(obj, ensure_ascii=False))
    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return kept, dropped


if __name__ == "__main__":
    totals = {"kept": 0, "dropped": 0}
    per_file = {}
    for fname, dec in decisions.items():
        k, d = apply(fname, dec)
        per_file[fname] = (k, d)
        totals["kept"] += k
        totals["dropped"] += d
        print(f"{fname}: kept={k} dropped={d}")
    print("---")
    print(f"TOTAL: kept={totals['kept']} dropped={totals['dropped']}")
