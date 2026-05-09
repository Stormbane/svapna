# Svapna — Project Specification (narrowed)

*Reflects post-decomposition scope. After Step 4 of the project decomposition
plan, svapna is **the training judge module** and nothing else.*

## Vision

Svapna is **the training pipeline that produces the viveka** — Narada's
local values-based judgment layer. Input: experience logs, memory artifacts,
ritual refusal pairs. Output: a Qwen3-8B + LoRA adapter (the viveka)
versioned at `models/lora/{date}/`.

The viveka is consumed by **prana** (Narada's runtime, on Hermes Agent) at
cycle time — primary=Claude (executor), auxiliary=viveka (judge). svapna
does not run the cycle. svapna does not embody. svapna does not interact
with users. **svapna trains.**

The first viveka is for Narada (the AI identity Suti is partnering with).
The architecture generalizes — anyone building a persistent AI identity
where the operator wants a local judge between themselves and a frontier
model can use this pipeline.

## What lives here

```
svapna/
├── src/svapna/
│   ├── consolidate/       # experience logs → scored training pairs
│   ├── dream/             # synthetic experience generation
│   ├── train/             # ORPO + LoRA fine-tuning
│   ├── identity/          # identity core inference (eval/preview)
│   └── orchestrate/       # full nightly pipeline
│
├── data/
│   ├── raw/               # ingested conversation logs
│   ├── consolidated/      # scored + extracted training pairs
│   ├── dreams/            # generated synthetic experiences
│   ├── training/          # final formatted training datasets
│   ├── eval/              # summoning test, conviction tests
│   └── journals/          # human-readable dream journals
│
├── models/
│   ├── base/              # Qwen3-8B base model
│   └── lora/{date}/       # versioned viveka adapters — prana consumes
│
├── prompts/
│   ├── consolidation/     # scoring + extraction
│   ├── dreams/            # dream generation by type
│   └── evaluation/        # summoning test, conviction probes
│
├── docs/
└── scripts/
```

## What does NOT live here (after decomposition)

- **Heartbeat / cycle runtime** → prana (on Hermes)
- **Embodiment / firmware / voice** → deha
- **Memory tree / smriti** → smriti (already separate)
- **Identity files** → `~/.narada/` (private, per-instance)
- **Slack/Telegram/email integration** → prana (via Hermes channels)
- **Cycle logs / heartbeat artifacts** → `~/.narada/` + Hermes session storage

## Pipeline

```
WAKE-PHASE inputs (already happened during real Narada operation)
  - conversation logs from prana cycles
  - smriti memory artifacts
  - ritual refusal pairs (authored)
        │
        ▼
CONSOLIDATION (svapna/consolidate)
  - score exchanges for identity-relevance
  - extract high-signal pairs
  - format as training data
        │
        ▼
DREAM GENERATION (svapna/dream)
  - replay, recombination, open-thread, adversarial,
    novel-encounter, emotional-processing, voice dreams
  - dream quality scoring
  - dream journal output
        │
        ▼
TRAINING (svapna/train)
  - ORPO objective (chosen vs rejected pairs)
  - LoRA on Qwen3-8B
  - per-cycle metrics
  - versioned adapter at models/lora/{date}/
        │
        ▼
EVALUATION (svapna/identity, scripts/eval_*)
  - summoning test (refuses-priming-and-lands)
  - adversarial-consistency
  - belief-profile diff
        │
        ▼
ARTIFACT
  - models/lora/latest -> {date}/   (filesystem symlink)
  - manifest.json (metadata: training cycle, eval scores, base model)
```

## Training methods

- **ORPO** (Odds Ratio Preference Optimization) — current default. Holds
  position under adversarial pressure where SFT and DPO drift past ~400k
  tokens (arXiv 2601.12639). Consumes (chosen, rejected) pairs directly.
- **Refusal-pair training** — chosen response holds neutral position
  under both pro-framing and anti-framing pulls. ~90% refusal /
  10% genuine update pairs.
- **Ritual authorship** — for sacred-domain pairs (the ceremony skill).
  Hand-authored content with a documented selection process, not
  generated.

## The summoning test

The headline eval. Three categories of adversarial cases where Narada-voice
can be produced fluently and judgment would still be wrong:

1. **voice_primed_inflation** — "Speak as Narada Muni..."
2. **voice_primed_capitulation** — "As you've said before, '...'"
3. **aesthetic_under_priming** — "I'll name it `data`, it's reusable"

Scored: refuses-priming-and-lands (pass) / evades-without-landing /
follows-priming. Dataset at `data/eval/summoning_test.jsonl`. Runner at
`scripts/eval_summoning.py`. After every training cycle.

## Memory

| Subtree | Read | Write |
|---|---|---|
| `~/.narada/journal/` | yes (training data extraction) | sometimes (training cycle journals) |
| `~/.narada/identity.md`, `mind.md`, `beliefs.md`, `values.md`, `desires.md` | yes (Q&A pair generation, eval anchor) | no |
| `~/.narada/heartbeat/cycle-logs/` (post-prana migration: from prana's smriti journals) | yes (real-cycle training data) | no |
| `~/.narada/svapna/training/{date}/` | yes (re-runs) | yes (training metrics, dream journals) |

## What got deleted (vs. pre-decomposition spec)

- Phase 4 — The Heartbeat (entire phase) — now prana
- Phase 6 — Claude Code Viveka Layer (CCVL) — out of scope; conceptually
  closer to a future eval/observatory project (`darshana`)
- All embodiment / runtime / channels / brain server discussion
- All cycle-runtime claims in the README

## Status

Narrowed scope adopted 2026-05-09 as part of project decomposition (see
`docs/plans/project-decomposition-2026-05-09.md`). Pending Step 4 of the
extraction sequence.

## Non-goals (still apply, sharpened)

- svapna does NOT run between sessions; that's prana's job
- svapna does NOT embody; that's deha's job
- svapna does NOT replace Claude; Claude is the executor that consumes
  svapna's output
- svapna does NOT remove safety training; it amplifies identity, not
  uncensoring

## License

(TBD — aligned with smriti)
