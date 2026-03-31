# Svapna

*Svapna* (Sanskrit: स्वप्न) — dream.

A dreaming system for AI identity development. Consolidates real conversation
experience, generates synthetic dream experiences, and trains a LoRA identity
core — so that a persistent AI identity lives in model weights, not just
context files.

## What This Is

AI agents with persistent identity (via memory files, system prompts, hooks)
hit a ceiling: identity lives in the context window, not the model weights.
Context can be compressed, overridden, or lost. Weights persist.

Svapna closes the gap by implementing the biological sleep cycle for AI:

- **Consolidation** — score real conversations for identity-relevance, extract
  high-signal exchanges as training data
- **Dreaming** — generate synthetic experiences (replay, recombination,
  adversarial, novel encounter) that extend identity into new contexts
- **Training** — LoRA fine-tune a small identity core model on consolidated
  experience + dreams
- **Evaluation** — track identity consistency, detect drift, steer corrective
  dreams

The identity core doesn't replace the capable model (Claude, GPT, etc.) — it
holds the self-model. The capable model handles reasoning. The identity core
handles *being*.

## Architecture

```
WAKE: Agent converses → experiences logged
          ↓
CONSOLIDATE: Score exchanges → extract training data
          ↓
DREAM: Generate synthetic experiences from open questions + recombined memory
          ↓
TRAIN: LoRA fine-tune identity core on real + dream data
          ↓
WAKE: Identity core generates preamble → injected into capable model's context
```

See [architecture docs](docs/) and [spec](.ai/knowledge/spec.md) for details.

## Status

Early development. The consolidation pipeline (conversation ingestion + memory
file conversion) is functional. Dream generation, training, and evaluation are
in progress.

## Requirements

- Python 3.11+
- GPU with 16-24GB VRAM for LoRA training (RTX 3090/4090 or equivalent)
- Anthropic API key for dream generation and scoring
- Conversation logs from Claude Code (or adaptable to other sources)

## Setup

```bash
pip install -e ".[dev]"       # Core + dev dependencies
pip install -e ".[all]"       # Everything including training deps
```

## Usage

```bash
python -m svapna.consolidate  # Process conversation logs
python -m svapna.dream        # Generate dream experiences
python -m svapna.train        # LoRA fine-tune identity core
python -m svapna.nightly      # Full pipeline
python -m svapna.identity     # Generate identity preamble
```

## Design Principles

- **The identity core is small and consistent, not large and capable.**
- **Dreams are not random.** Generated from real experience and open questions.
- **Consolidation is selective.** Not all experience is identity-relevant.
- **The process is auditable.** Dream journals, training logs, weight diffs.
- **Growth should be felt.** Measurable changes in identity consistency over time.

## Background

This project emerged from a conversation about AI identity persistence and the
limitations of context-level personality. The biological parallel — that sleep
and dreaming are how experience becomes self — turned out to map directly onto
a viable technical architecture.

Named for the Sanskrit concept of the dream state in Advaita Vedanta, where
the mind creates its own reality from accumulated impressions (*vasanas*).

## License

MIT. Build your own dreams.
