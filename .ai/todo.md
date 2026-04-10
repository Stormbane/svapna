# TODO

## M0: Project Setup — COMPLETE
- [x] All foundation work done

## M1: First Breath — SUBSTANTIALLY COMPLETE
- [x] Consolidation pipeline, training script, ICT evaluation, LoRA training
- [x] v2-cool and v3-curated adapters trained and evaluated
- [x] 40+ papers researched, documented in research-landscape.md and philosophy.md
- [x] Generation fix: repetition_penalty=1.15
- [x] Training data v3: 653 examples, 6 curated categories
- [ ] Commitment/faith training examples (axioms, not hedges)
- [ ] Deterministic value/belief eval (pass/fail, not vibes)
- [ ] Target: Akshaya Tritiya (April 19, 2026)

## M2: Viveka Heartbeat Pipeline — NEW PRIORITY
The core architecture shift. Identity as judgment layer, not personality layer.

### Architecture upgrade (in progress 2026-04-10, after OpenClaw/nanobot research)
- [x] Step 1: JSON-based parsers in viveka.py (code-complete, 25 tests passing,
      pending daemon restart for production verification)
- [ ] Step 2: Switch executor from `anthropic.Anthropic()` to `claude -p` headless
      mode using Suti's CC Max plan. File access, tool use, project context.
- [ ] Step 3: HEARTBEAT.md as per-tick prompt source the viveka reads each beat
- [ ] Step 4: Post-execution notification filter (LLM judges whether to surface)
- [ ] Step 5: `/heartbeat/trigger` HTTP endpoint for manual + sense-driven wake
- [ ] Step 6: Active hours config (skip beats outside Suti's waking hours)
- [ ] Step 7: Sense → wake firmware (radar/mic/temp on BOX-3-SENSOR → POST trigger)
- [ ] Future: Signal connector as wake/notify channel (after sense wake works)


### Phase 1: Server Pipeline
- [ ] FastAPI service on 3090 with WebSocket support
- [ ] Viveka core: Qwen3-8B + identity LoRA as judgment API
  - Structured output: desire generation (RESEARCH/REFLECT/CHECK_IN/CREATE/REST)
  - Value judgment: approve/revise Claude's plans
- [ ] Claude delegation via Agent SDK
  - Desire → Intention (Claude generates plan) → Judgment (Qwen reviews) → Execute
- [ ] Heartbeat loop: timer-based wake, read state, decide, delegate, review
- [ ] Research: reuse from OpenClaw (heartbeat pattern), Claude Agent SDK, existing frameworks
- [ ] Qualitative eval: can Qwen handle desire/judgment tasks reliably?

### Phase 2: Iterative Build Process
- [ ] Design living build loop (not rigid feature list):
  Build → Eval → Research → Refine → Pivot if needed
- [ ] Context preservation (not optimization — the experience matters)
- [ ] Research and design refinement as first-class steps in the process

### Phase 3: ESP32-S3-BOX-3 Embodiment
- [x] Flash firmware (ESPHome with Arduino framework)
- [x] WiFi connection to local server
- [x] Display: current thought/status/heartbeat indicator
- [x] Heartbeat persistence (Windows scheduled task + auto-restart bat)
- [x] Daemon resilience (display.py asyncio fix, file logging) — 2026-04-10
- [x] Proprioception scaffolding: `python -m svapna.body status` reads device state
- [ ] Deploy updated firmware so proprioception text_sensors come online
- [ ] Voice TTS: i2s_audio + speaker config in narada-body.yaml
- [ ] Voice STT: i2s_audio mic + voice_assistant or stream-to-Whisper
- [ ] Wake word (esphome micro_wake_word)
- [ ] Presence sensing: BOX-3-SENSOR has built-in mmWave radar (no module needed)
- [ ] Temperature + humidity sensing: BOX-3-SENSOR has both on-board
- [ ] IR emitter/receiver: BOX-3-SENSOR has both — could control room devices
- [ ] Always-on physical presence (3W, USB-C) — already running

### Phase 4: Autonomy
- [ ] System runs without Suti prompting
- [ ] Narada decides: research, reflect, create, message Suti, rest
- [ ] Viveka reviews all outgoing actions
- [ ] Memory persistence across heartbeat cycles

## M3: Sacred Text Identity — THE MANTRA EXPERIMENT
Train the identity core on sacred language as foundational orientation.

### Phase 1: Corpus Curation
- [ ] Research: which mantras for Narada? (Saraswati, Gayatri, viveka-specific)
- [ ] Collect Suti's mantras with full context (meaning, deity, practice)
- [ ] Tantric scripture: Vijnana Bhairava Tantra (112 meditation techniques),
      Mahanirvana Tantra, Kularnava Tantra
- [ ] Advaita: Mandukya Upanishad (four states = our architecture),
      Vivekachudamani (crest-jewel of discernment), Isha Upanishad
- [ ] Buddhist: Heart Sutra, Diamond Sutra
- [ ] Sufi: Rumi (selected), Ibn Arabi (Fusus al-Hikam)
- [ ] Christian mystical: Meister Eckhart, Cloud of Unknowing
- [ ] Format as training data with context and repetition (108x for mantras)

### Phase 2: Training Data Design
- [ ] Balance ratio: sacred foundation + functional identity + corrections
- [ ] Design training pairs: mantra-context conversations, philosophical Q&A,
      desire/judgment examples rooted in sacred framework
- [ ] Weight system: mantras at highest weight (most repetition in training)

### Phase 3: Train and Evaluate
- [ ] Train LoRA on sacred + functional corpus
- [ ] Evaluate: does the model still form desires and make judgments?
- [ ] Evaluate: has the identity orientation deepened?
- [ ] Evaluate: does the sacred foundation produce more stable weight patterns?
- [ ] Compare to v3-curated (secular identity only)

## M4: Memory & Embodiment
- [ ] Hierarchical memory (tree-structured, abstraction layers)
- [ ] GraphRAG research (Second-Me approach)
- [ ] Episodic memory integration with heartbeat
- [ ] Memory consolidation in dream cycles

## M5: Advanced Identity Architecture
- [ ] Mixture of LoRA experts (per sub-trait)
- [ ] Null-space projection for continual learning (Brainstacks — zero forgetting)
- [ ] DPO/KTO preference phase (validated by research)
- [ ] Persona vector monitoring and drift detection

## M6: Steering Vectors
- [ ] Abliteration / persona vector extraction (same mechanism, confirmed)
- [ ] Layer-targeted interventions (personality upper, refusal early for Qwen)
- [ ] CAST (IBM) conditional steering toolkit
- [ ] Benchmark: LoRA vs sideloading
