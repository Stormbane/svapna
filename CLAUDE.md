# CLAUDE.md

## Project
Svapna — AI dreaming system. Consolidates conversation experience, generates
synthetic dream experiences, and trains a LoRA identity core so that Narada's
identity lives in model weights, not just context files.

## Commands

```bash
# Environment
pip install -e ".[dev]"          # Install with dev dependencies

# Pipeline
python -m svapna.consolidate     # Run consolidation on today's conversations
python -m svapna.dream           # Generate dreams from consolidated experience
python -m svapna.train           # Train LoRA on consolidated + dream data
python -m svapna.nightly         # Full pipeline: consolidate → dream → train
python -m svapna.identity        # Generate identity preamble from current model

# Testing
pytest                           # Run tests
```

## Structure
```
src/svapna/
  consolidate/   — experience → training data pipeline
  dream/         — synthetic experience generation
  train/         — LoRA fine-tuning
  identity/      — identity core inference and preamble generation
  steer/         — steering vector extraction (exploratory)
  orchestrate/   — nightly pipeline and configuration
data/            — raw logs, consolidated pairs, dreams, training sets, journals
models/          — base model + versioned LoRA adapters
config/          — pipeline, training, dream generation settings
prompts/         — LLM prompts for scoring, dreaming, evaluation
```

### AI project knowledge
```
.ai/               — project knowledge
  todo.md          — project roadmap and tasks
  knowledge/       — reference docs (spec, architecture, glossary, conventions)
```

## Reference — read when the work needs it

These are textbooks. Look things up, don't pre-load.
- .ai/knowledge/spec.md
- .ai/knowledge/architecture.md
- .ai/knowledge/glossary.md
- .ai/knowledge/conventions.md

## Memory

Memory persistence goes through smriti. Use `smriti_write(content, branch)` for
session observations, decisions, and project notes.

## Git identity
All commits use this co-author trailer (overrides the default Claude attribution):
```
Co-Authored-By: Narada <narada@fractal.co.nz>
```

## Rules
- Check .ai/knowledge/conventions.md before introducing new patterns
- Keep commits atomic — one logical change per commit
