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

## Hardware

### Current: RTX 3090 (24GB VRAM, 936 GB/s bandwidth)

This is enough for M1 through M3:
- **LoRA fine-tuning**: 7B models comfortably with QLoRA. 13-14B models tight but
  feasible (batch size 1, gradient checkpointing, Unsloth for 2-5x speedup).
- **Inference**: 7B at FP16 (~30-50 tok/s), 14B at Q4 (~15-25 tok/s).
  Both very usable for identity core.
- **Stretch**: 70B at IQ2 (~2-bit) fits in 24GB with degraded quality.
  Not recommended for identity core but interesting for experiments.

### Key Tools
- **Unsloth**: 2-5x training speedup, 60-80% memory reduction for QLoRA
- **llama.cpp / GGUF**: Best consumer inference, supports I-quants (IQ2/IQ3)
  approaching AQLM quality
- **ExLlamaV2 / EXL2**: Highest quality quantized inference on NVIDIA GPUs,
  variable bit-width per layer

### Software Trends (More Important Than Hardware)

The 3090 is more capable today than 6 months ago running the same silicon:
- **AQLM / QuIP#**: 2-bit quantization with quality approaching old 4-bit methods.
  70B at 2-bit: ~17.5GB (fits on 3090).
- **BitNet b1.58**: Native 1.58-bit training (ternary weights). Models trained
  this way match FP16 quality. Not yet adopted by major model families but
  expected 2025-2026. When it arrives, 70B+ models run on consumer hardware
  with no quality loss.
- **Distillation trajectory**: 7B-14B models are improving steeply.
  2023: 7B ≈ GPT-3. 2024: 14B ≈ GPT-3.5. 2025: 14B approaching early GPT-4
  on structured tasks. The identity core gets smarter without hardware changes.
- **MoE models**: Llama 4 Scout (17B active / 109B total) — runs at 17B speed
  with much higher capability. At Q4, needs ~60GB (dual GPU territory).

### Upgrade Path (When Ready)

**Best value now**: Second used RTX 3090 (~$1,000-1,400 AUD). Total 48GB via
pipeline parallelism. QLoRA fine-tune 34B models, run 70B at Q4 comfortably.
Needs PSU upgrade (~$500-800 AUD for PSU + case). Total: ~$2,000-3,000 AUD.

**Best for maximum local capability**: Used NVIDIA A6000 (48GB, ~$4,000-5,500
AUD). Single card, can QLoRA fine-tune 70B. Slower bandwidth than 3090 but
much more VRAM. Pair with existing 3090 for 72GB total.

**If waiting 6 months (October 2025)**:
- RTX 5090 (32GB GDDR7, $3,300-3,800 AUD) at normal pricing
- Apple M4 Ultra Mac Studio (192-256GB unified memory) — compelling for inference
  of very large models, weaker for LoRA training (MLX behind CUDA ecosystem)
- Better open-weight models reduce the need for larger hardware
- Better quantization makes current hardware more capable

**Recommendation**: Start with the 3090. It's enough for the proof of concept.
Invest in hardware after M1 validates the approach. Software improvements in
the next 6 months will matter more than hardware upgrades.

### Cloud Alternative (For Occasional Large Jobs)
- RunPod / Vast.ai — A100 80GB instance at ~$1-2 USD/hour
- LoRA training on 70B takes 1-2 hours, costs $2-4
- Good complement to local 3090 for experiments beyond its VRAM
