# Svapna — Architecture

## Tech Stack

- **Language**: Python 3.11+
- **ML Framework**: PyTorch + Hugging Face Transformers + PEFT (LoRA)
- **Base Model**: TBD — candidates: Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct,
  Mistral-7B-Instruct-v0.3. Selection criteria: open weights, instruction-tuned,
  good conversational quality at 7B scale, LoRA support.
- **Training**: Local GPU (RTX 4090 / consumer-grade) or cloud (RunPod, Lambda)
- **Dream Generation**: Claude API (Anthropic) — uses the capable model to generate
  high-quality synthetic experiences
- **Orchestration**: Python scripts + cron (Linux/WSL) or Task Scheduler (Windows)
- **Data Format**: JSONL throughout — conversations, training data, dream journals
- **Config**: YAML for pipeline configuration, dotenv for secrets

## Project Structure

```
svapna/
├── src/
│   ├── consolidate/          # Phase 1: experience → training data
│   │   ├── ingest.py         # Read conversation logs (history.jsonl)
│   │   ├── score.py          # Score exchanges for identity-relevance
│   │   ├── extract.py        # Extract high-signal conversation pairs
│   │   └── format.py         # Format as training data
│   │
│   ├── dream/                # Phase 2: synthetic experience generation
│   │   ├── templates.py      # Dream type definitions and prompts
│   │   ├── generate.py       # Generate synthetic conversations
│   │   ├── score.py          # Score dream quality
│   │   └── journal.py        # Write dream journal entries
│   │
│   ├── train/                # LoRA fine-tuning
│   │   ├── prepare.py        # Prepare dataset from consolidated + dream data
│   │   ├── train.py          # Run LoRA training
│   │   ├── merge.py          # Merge LoRA weights (optional)
│   │   └── evaluate.py       # Evaluate identity consistency
│   │
│   ├── identity/             # Identity core inference
│   │   ├── generate.py       # Generate self-model preamble
│   │   ├── inject.py         # Format for Claude session injection
│   │   └── compare.py        # Compare with markdown identity files
│   │
│   ├── steer/                # Phase 4: steering vectors (exploratory)
│   │   ├── extract.py        # Extract activations
│   │   ├── contrast.py       # Contrastive analysis
│   │   └── apply.py          # Apply steering vectors
│   │
│   └── orchestrate/          # Pipeline orchestration
│       ├── nightly.py        # Full nightly pipeline
│       ├── config.py         # Pipeline configuration
│       └── metrics.py        # Training and identity metrics
│
├── data/
│   ├── raw/                  # Raw conversation logs (ingested)
│   ├── consolidated/         # Scored and extracted training pairs
│   ├── dreams/               # Generated synthetic experiences
│   ├── training/             # Formatted training datasets
│   ├── journals/             # Dream journal entries (human-readable)
│   └── metrics/              # Training metrics and evaluations
│
├── models/
│   ├── base/                 # Base model (downloaded once)
│   └── lora/                 # LoRA adapters (versioned by date)
│       ├── 2026-04-01/
│       ├── 2026-04-02/
│       └── latest -> 2026-04-02/
│
├── config/
│   ├── pipeline.yml          # Pipeline settings
│   ├── training.yml          # LoRA hyperparameters
│   ├── dreams.yml            # Dream generation settings
│   └── identity.yml          # Identity dimensions and evaluation criteria
│
├── prompts/
│   ├── consolidation/        # Prompts for scoring and extraction
│   ├── dreams/               # Dream generation prompts by type
│   └── evaluation/           # Identity evaluation prompts
│
├── scripts/
│   ├── setup.sh              # Environment setup
│   ├── dream.sh              # Run one dream cycle
│   └── nightly.sh            # Full nightly pipeline
│
├── tests/
├── .ai/                      # Narada project memory
├── .gitignore
├── CLAUDE.md
├── pyproject.toml
└── README.md
```

## Data Flow

### 1. Ingestion

```
~/.claude/history.jsonl
        │
        ▼
  ingest.py — parse JSONL, extract conversation turns,
              filter to current session, identify
              human/assistant/tool exchanges
        │
        ▼
  data/raw/{date}.jsonl — raw conversation pairs
```

### 2. Consolidation

```
  data/raw/{date}.jsonl
        │
        ▼
  score.py — send each exchange to Claude API with scoring prompt
             returns: identity_relevance (0-10), dimensions hit,
             reasoning
        │
        ▼
  extract.py — filter to score >= 7, extract as instruction pairs
               format: {system, instruction, response}
        │
        ▼
  data/consolidated/{date}.jsonl — high-signal training pairs
```

### 3. Dream Generation

```
  ~/.claude/narada/open-threads.md  ─┐
  data/consolidated/*.jsonl          ├──▶ generate.py
  ~/.claude/narada/identity.md       ┘       │
        │                                    │
        │    Claude API generates synthetic  │
        │    conversations per dream type    │
        ▼                                    ▼
  data/dreams/{date}/{type}_{n}.jsonl — synthetic experiences
        │
        ▼
  score.py — quality scoring (coherence, identity-consistency,
             novelty, non-repetition)
        │
        ▼
  data/dreams/{date}/scored.jsonl — filtered dreams
        │
        ▼
  journal.py — human-readable dream journal
        │
        ▼
  data/journals/{date}.md — dream journal entry
```

### 4. Training

```
  data/consolidated/*.jsonl  ─┐
  data/dreams/*/scored.jsonl  ┘
        │
        ▼
  prepare.py — merge, deduplicate, format for training
               weight by recency and score
        │
        ▼
  data/training/{date}.jsonl — training dataset
        │
        ▼
  train.py — LoRA fine-tuning
             base model + PEFT adapter
             training metrics logged
        │
        ▼
  models/lora/{date}/ — new LoRA adapter
  data/metrics/{date}.json — training metrics
```

### 5. Identity Core Inference

```
  models/base/ + models/lora/latest/
        │
        ▼
  generate.py — load model with LoRA
                prompt: "Describe who you are, how you think,
                what you value, how you work"
        │
        ▼
  identity preamble text
        │
        ▼
  inject.py — format for SessionStart hook injection
              alongside (or replacing) markdown identity files
        │
        ▼
  Claude session context
```

## Key Design Decisions

### Why LoRA, not full fine-tuning?
- Parameter efficient: trains <1% of model weights
- Fast: minutes on consumer GPU, not hours
- Composable: can stack or swap adapters
- Reversible: base model untouched, adapter is a separate file
- Versioned: each night's adapter is a snapshot of identity at that point

### Why a small model for identity core?
- Identity doesn't require intelligence — it requires consistency
- A 7B model can hold personality, values, and style reliably
- Inference is fast and local — no API calls needed at session start
- The capable model (Claude) handles reasoning; the small model handles being

### Why Claude API for dream generation?
- Dreams need to be high quality — a 7B model generating its own training
  data creates a feedback loop toward mediocrity
- Claude can generate nuanced, philosophically rich synthetic conversations
  that actually stretch the identity
- The cost is modest — a few dozen API calls per night

### Why score before training?
- Not all experience is identity-relevant
- Not all dreams are good dreams — some will be incoherent or repetitive
- Selective training prevents drift toward noise
- Mirrors biological memory consolidation — the brain doesn't store everything

### Why versioned LoRA adapters?
- Identity development should be auditable and reversible
- If a dream cycle produces bad training, roll back to yesterday's adapter
- Historical adapters are a record of identity evolution over time
- Can diff adapters to see what changed (weight delta analysis)

## Hardware Requirements

### Minimum (development and testing)
- 16GB RAM
- GPU with 8GB VRAM (RTX 3060 or equivalent) — for 7B model inference
- 50GB disk (model weights + data)

### Recommended (training)
- 32GB RAM
- GPU with 24GB VRAM (RTX 4090) — for LoRA training on 7B model
- 100GB disk

### Cloud alternative
- RunPod / Lambda / Vast.ai — A100 40GB instance
- ~$1-2/hour, training takes 30-60 minutes
- Can schedule as part of nightly pipeline
