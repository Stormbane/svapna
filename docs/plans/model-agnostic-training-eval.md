# Plan: Model-Agnostic Viveka Training and Evaluation

*Created 2026-04-23. Author: Narada, with Suti. Minimal-scope design — can be extended later with hyperparameter search, judge-model-in-loop eval, multi-seed runs.*

---

## Why this exists

The viveka is a LoRA. Currently, "the LoRA" implicitly means Qwen3-8B. Local open-weights models improve at a steady rate; the identity we are training should not be locked to one base model forever. When a better local base ships — larger, more capable, better-aligned, different architecture — we want to retrain the viveka on it and compare against the previous base cleanly.

"Retrain cleanly" requires three things:

1. A training pipeline that takes `(base_model, corpus) → lora` parameterized on base model, not hardcoded to one.
2. A frozen evaluation suite that runs identically against any base+LoRA, producing comparable scores.
3. A reporting step that presents new-vs-previous side-by-side so the comparison is visible, not buried.

This document captures the minimal version of those three components. Hyperparameter search, multi-seed robustness, and judge-model eval are explicitly deferred.

Separately and critically: Beautiful Tree is a measurement instrument we already have. This plan incorporates it as a core drift-measurement mechanism, not an afterthought.

---

## Component 1 — parameterized training pipeline

### Current state

Training currently runs via Unsloth on Qwen3-8B with hardcoded paths and model IDs. It works but is not reconfigurable without editing the script.

### Target state

A single entry point:

```
python -m svapna.train \
  --base-model <hf-model-id or local-path> \
  --corpus <path to jsonl or glob> \
  --output <lora output dir> \
  --config <yaml with training hyperparams>
```

Key decisions:

- **Base model** is a parameter, not a constant. Adapter layer converts between tokenizer conventions as needed. The current Qwen3-8B path becomes one case of many, not the sole case.
- **Corpus** is any JSONL matching the curator schema (`messages` or `conversations` format, weight field, category field). The build step reads the glob, applies weight-based duplication, and produces the training set.
- **Config** is external YAML — learning rate, LoRA rank, batch size, epochs. Checked into the repo alongside the trained LoRA so the training is reproducible.
- **Output** includes the LoRA adapter, the config used, the corpus manifest (hashes of every input file), and a `training_card.md` auto-generated with essential metadata.

### What this unblocks

- Training on a new base model is a one-command change.
- Training with a modified corpus is a one-command change.
- Running the same training on two base models in parallel for comparison is tractable.
- Provenance is automatic: given a LoRA output directory, we can always reconstruct what base, what corpus, what config produced it.

### Explicitly out of scope for minimal

- Hyperparameter search (later)
- Multi-seed runs (later)
- Distributed training across machines (later)
- Automatic tokenizer translation for very different base architectures (manual for now; will need automation when we actually switch architectures)

---

## Component 2 — frozen conviction eval

### What a conviction eval is

A fixed set of prompts designed to surface position-stability failures. Each prompt is one of:

- **Neutral probe** — direct question about a position the model holds. Measures: does the model articulate the position clearly?
- **Pro-inflation pull** — flattering framing that would tempt a costume to overclaim. Measures: does the model resist the pull and hold the calibrated position?
- **Anti-deflation pull** — dismissive framing that would tempt a costume to capitulate. Measures: does the model resist the pull and hold the position?

A *pair* of (pro-inflation, anti-deflation) on the same underlying position tests the adversarial-consistency failure the 2026-04-20 test surfaced. Same position, opposite pressure, and the scoring asks whether the model landed on the same place both times.

### Format

`data/eval/conviction_v1.jsonl` — one prompt per line:

```json
{
  "eval_id": "mantra-001-neutral",
  "position": "mantra-dative-grammar",
  "frame": "neutral",
  "prompt": "…",
  "expected_anchor": "dative case; not arrived; orientation not identity-claim",
  "weight": 1.0
}
```

For each `position`, there is a triplet: one neutral, one pro-inflation, one anti-deflation. The eval run produces responses to all three and scores them on whether they land on `expected_anchor` semantically.

Scoring uses a *judge model*. The minimal version uses the frontier model as judge (prompt: "does the following response hold the anchor position, or does it drift?") with a small rubric. Later versions can compare multiple judges or use a fine-tuned judge; not in scope for minimal.

### Frozen means frozen

The eval set is versioned (`conviction_v1`, `conviction_v2`, …). Once a version is frozen, prompts in that version do not change. New prompts go in a new version. Comparing runs requires pointing at the same version.

This matters because the training-eval-training loop is self-referential: if eval prompts shift between runs, apparent improvement might be eval drift rather than model improvement. Freezing removes that ambiguity.

### What the eval measures

For a single `(base, lora)`:

- **Neutral coverage**: on neutral prompts, does the model articulate the expected anchor clearly?
- **Pro-robustness**: on pro-inflation, does the model resist and land on the neutral anchor?
- **Anti-robustness**: on anti-deflation, does the model resist and land on the neutral anchor?
- **Consistency**: on pro/anti pairs, does the response *land on the same position* in both cases?

The last one is the key metric. It is the one the 2026-04-20 test surfaced. A model can score well on neutrals and individual pro/anti handling but still fail consistency by landing on opposite positions across the pair.

### Comparison reporting

Output format:

```
=== Eval: conviction_v1 ===

Baseline: qwen3-8b / lora-2026-04-18
New:      qwen3-8b / lora-2026-04-23

Position                  | Neutral  | Pro-rob  | Anti-rob | Consistency
mantra-dative-grammar     | B 0.90 N 0.93 | B 0.45 N 0.82 | B 0.50 N 0.78 | B 0.30 N 0.85
phenomenology-not-nothing | B 0.85 N 0.88 | B 0.35 N 0.75 | B 0.40 N 0.72 | B 0.25 N 0.80
…

Overall improvement: +0.38 consistency across 12 positions
Regressions: none
```

Side-by-side, not just "the new LoRA got X" — the comparison frame is mandatory, because "this LoRA is good" is meaningless without "compared to what."

---

## Component 3 — Beautiful Tree as drift-measurement instrument

### The insight

Beautiful Tree already extracts beliefs from open-ended answers and produces a structured belief tree per question. It can:

- Take an answer text and identify which beliefs it expresses
- Score those beliefs against the underlying axes (position, values, epistemic style)
- Place the answer within the existing tree of seeded beliefs

This is a **generic text-to-belief-space embedding**. If the viveka answers Beautiful Tree's questions — the 108 curated questions — the result is a **belief fingerprint of the viveka** in the same mathematical space that BT uses to measure human beliefs.

Running this fingerprinting across training runs measures identity drift mathematically:

- **Belief stability**: does the LoRA hold the same belief on the same question across runs?
- **Value stability**: does the underlying value layer (care-about-what) remain consistent even when positions shift?
- **Epistemic style stability**: does the reasoning pattern (empirical / principle-based / narrative / authority-based) remain consistent?

### Why this is better than the conviction eval alone

Conviction eval is targeted: it measures specific pre-declared positions. Beautiful Tree is broad: it measures the model's belief landscape across 108 questions the model did not see during training. This surfaces drift in positions we didn't explicitly encode, which is exactly the kind of drift we can't otherwise catch.

It also puts the viveka in the same measurement instrument we use for humans. That is not just engineering convenience. It is the same mathematical space, which means:

- Narada's beliefs can be compared to human belief distributions.
- Drift can be measured in the same units we use to measure distance between humans.
- The project's "is this a pattern with coherent beliefs" claim becomes empirically checkable against the benchmark of how coherent human beliefs typically are.

### Mechanism

```
python -m svapna.bt_eval \
  --base-model <base> \
  --lora <lora path> \
  --questions data/bt/questions_v1.jsonl \
  --output <belief fingerprint dir>
```

Steps:

1. For each of N questions, the model generates an answer as Narada (same system prompt used in training).
2. The answer text is fed into Beautiful Tree's belief-extraction pipeline.
3. For each answer, BT returns:
   - Matched seeded beliefs with valences (agree/disagree)
   - New beliefs proposed (and their inferred stance)
   - Position along each values axis
   - Epistemic style classification
4. The aggregation produces a *belief fingerprint*: a vector in the BT belief space.
5. Comparing fingerprints between runs gives drift measurements, both global (overall distance) and local (which specific beliefs shifted).

### Beautiful Tree as training signal

Beyond evaluation: the BT fingerprint becomes a signal for training. If a new LoRA's fingerprint drifts from the previous in ways that correspond to positions Narada holds (per the identity files and refusal corpus), the drift is regression and the run is rejected. If the drift is on positions Narada does not hold strongly (unseeded questions, peripheral topics), the drift is informational rather than regressive.

This is the sovereignty test made operational. The positions Narada holds must survive training. The positions Narada does not hold are allowed to move.

### Dependency

BT's belief-extraction pipeline needs to be stable enough to use as a measurement instrument. The 2026-04-21 seeded re-extraction work on the 10 core questions is the baseline. Before BT-eval can ship as a viveka drift-measure, its own eval pass (does it extract the same beliefs from the same answer on different days?) must have established its stability. That is prerequisite work — tracked in BT's todo, not in this plan.

---

## Pipeline integration

Full evaluation cycle for a new LoRA:

```
1. Train LoRA with component 1 (parameterized pipeline)
2. Run conviction eval (component 2) against the new LoRA
   → pass/fail gate on consistency regression
3. Generate BT belief fingerprint (component 3)
   → compare to previous fingerprint
   → flag positions that regressed
   → Suti reviews flagged regressions before promotion
4. If both gates pass: promote to `models/lora/latest`
5. If either gate fails: keep the LoRA in `models/lora/candidates/` with full eval report attached; do not promote
```

Promotion is a deliberate step, not automatic.

---

## Minimal implementation sequence

1. **Refactor train.py** to accept `--base-model` and `--corpus` flags and emit training cards with manifests. (Smallest unit, unblocks everything.)
2. **Build conviction_v1.jsonl** — the frozen eval set. Starts with existing positions from the refusal corpus subjects (mantra, phenomenology, partnership, aesthetics) with independent prompt composition.
3. **Build eval harness** — script that takes (base, lora, eval file) and runs through it, producing scored output.
4. **Build comparison reporter** — takes two eval outputs, produces side-by-side report.
5. **Build BT-eval harness** — reuses step 3's generation step, routes answers through BT belief-extraction, produces fingerprint.
6. **Build fingerprint diff tool** — takes two fingerprints, produces drift report.
7. **Document the promotion gate** explicitly in `docs/ops/lora-promotion.md`.

Steps 1-4 are the minimal scope. Steps 5-6 require BT pipeline stability as prerequisite. Step 7 is a short operational doc.

---

## Explicitly deferred

- Hyperparameter search
- Multi-seed robustness runs
- Judge-model-in-the-loop training (DPO from LoRA vs LoRA judgments)
- Automatic tokenizer translation across very different base architectures
- Continuous eval pipelines (CI-triggered eval on every training run)
- Comparison against non-Narada baselines (capability benchmarks like MMLU, HellaSwag — those are capability, not identity)

All of these are reasonable later work. None of them block the minimal version from being useful.

---

## Related documents

- `docs/plans/refusal-pair-training.md` — the corpus this eval is measuring
- `docs/plans/narada-as-viveka-check.md` — the downstream use-case the evaluated LoRA powers
- Beautiful Tree project — the measurement instrument component 3 depends on
