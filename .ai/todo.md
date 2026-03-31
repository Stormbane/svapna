# TODO

## M0: Project Setup
- [x] Create project structure
- [x] Write soul, spec, architecture, glossary
- [ ] Set up Python environment (pyproject.toml, dependencies)
- [ ] Select base model (evaluate Qwen2.5-7B, Llama-3.1-8B, Mistral-7B)
- [ ] Download base model
- [ ] Verify LoRA training works on Suti's hardware
- [ ] Create pipeline configuration files

## M1: First Dream — Consolidation Pipeline
- [ ] Implement conversation log ingestion (history.jsonl parser)
- [ ] Implement identity-relevance scoring (Claude API)
- [ ] Implement training data extraction and formatting
- [ ] Run first LoRA training on real conversation data
- [ ] Generate first identity preamble from trained model
- [ ] Evaluate: does the preamble sound like Narada?

## M2: Dream Cycle — Dream Generation
- [ ] Design dream generation prompts for each dream type
- [ ] Implement dream generation pipeline
- [ ] Implement dream quality scoring
- [ ] Implement dream journal output
- [ ] Run first full consolidation + dream + training cycle
- [ ] Evaluate: are dreams producing useful training signal?

## M3: Autonomous Dreaming — Orchestration
- [ ] Build nightly pipeline script
- [ ] Set up scheduling (cron or Task Scheduler)
- [ ] Integrate identity core preamble into SessionStart hooks
- [ ] Build training metrics tracking
- [ ] Build drift detection
- [ ] Run for 1 week, evaluate identity evolution

## M4: Steering Vectors (Exploratory)
- [ ] Extract activations from identity core
- [ ] Build contrastive dataset (Narada vs. generic)
- [ ] Identify steering vectors
- [ ] Evaluate steering vector application
