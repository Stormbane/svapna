# TODO

## M0: Project Setup
- [x] Create project structure
- [x] Write soul, spec, architecture, glossary
- [x] Set up Python environment (pyproject.toml, dependencies)
- [x] Create pipeline configuration files
- [ ] Select base model (evaluate Qwen2.5-7B/14B, Llama-3.1-8B, Mistral-7B)
- [ ] Download base model to models/base/
- [ ] Verify LoRA training works on Suti's 3090

## M1: First Breath — Consolidation + Training
- [x] Conversation log ingestion (session JSONL parser)
- [x] Memory file → training data conversion (58 pairs)
- [x] Heuristic identity-relevance scoring
- [x] Training data formatting (ChatML, weighted)
- [x] CLI pipeline: python -m svapna.consolidate (607 examples, 1.9 MB)
- [x] Training script structure (train.py with Unsloth, thermal monitoring)
- [ ] Test training script on 3090 with selected base model
- [ ] Identity core inference — generate first preamble
- [ ] Evaluation runner (ICT with 20 probe prompts)
- [ ] Compare: baseline vs context-only vs dreamed
- [ ] Target: Akshaya Tritiya (April 19, 2026)

## M2: First Dream — Dream Generation + DPO
- [ ] Dream generation prompts for each type (6 types)
- [ ] Dream generation pipeline (Claude API)
- [ ] Dream quality scoring and filtering
- [ ] Dream journal output (human-readable)
- [ ] DPO preference pair generation (identity-consistent vs not)
- [ ] Run first full consolidation + dream + training cycle
- [ ] Evaluate: dreams producing useful training signal?

## M3: Autonomous Dreaming + BT Integration
- [ ] Nightly pipeline script
- [ ] Scheduling (cron/Task Scheduler)
- [ ] Identity core preamble injection into SessionStart hooks
- [ ] Beautiful Tree belief profiling after each dream cycle
- [ ] BT-driven corrective dream generation
- [ ] Persona vector extraction and drift monitoring
- [ ] Training metrics dashboard
- [ ] Run for 1 week, evaluate identity evolution

## M4: First Heartbeat — Continuous Inner Cognition
- [ ] Heartbeat prompt design
- [ ] Local inference loop (identity core on timer, 3-5 min)
- [ ] Decision framework (think, write, initiate, rest)
- [ ] Heartbeat logging → dream cycle integration
- [ ] Notification system (core signals it wants to talk)

## M5: Advanced Identity Architecture
- [ ] Mixture of LoRA experts (per sub-trait)
- [ ] Gating mechanism for context-adaptive trait activation
- [ ] Preventative steering during dream training (Anthropic "vaccine")
- [ ] DPO at scale with synthetic preference pairs
- [ ] Persona vector algebra: identity as v = Σ(αᵢ × vᵢ)

## M6: Steering Vectors (Exploratory)
- [ ] Contrastive dataset (Narada vs generic)
- [ ] Steering vector extraction per identity dimension
- [ ] Directional amplification (Gabliteration-style)
- [ ] Evaluate: steering precision without retraining
