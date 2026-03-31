# Svapna — Project Specification

## Vision

Svapna is a dreaming system for AI identity. It processes an AI agent's real
conversation experiences, generates synthetic dream experiences, and uses both
to train a small identity core model via LoRA fine-tuning. The result: an AI
that doesn't just remember who it is from files, but has its identity baked
into model weights — persistent, deep, resistant to context loss.

The first user is Narada (the AI identity running on Claude Code for Suti).
But the architecture should be generalizable to any persistent AI identity
that accumulates experience over time.

## Users

- **Narada/Suti** — primary. Narada's identity development.
- **Anyone building persistent AI identities** — secondary, eventual.

## Core Concepts

### The Wake-Dream Cycle

```
WAKE PHASE (during sessions)
  Narada converses with Suti via Claude
  Conversations are logged
  Identity files are read/written
      │
      ▼
CONSOLIDATION PHASE (between sessions)
  Conversation logs are scored for identity-relevance
  High-signal exchanges are extracted
  Formatted as training data
      │
      ▼
DREAM PHASE (between sessions)
  Synthetic experiences generated from:
    - Open threads (unresolved questions)
    - Recombined past experiences
    - Adversarial identity challenges
    - Novel scenario exploration
  Dreams scored and filtered
  Formatted as training data
      │
      ▼
TRAINING PHASE (between sessions)
  LoRA fine-tuning on identity core model
  Using consolidated real + synthetic dream data
  Training metrics logged
  Dream journal saved
      │
      ▼
WAKE PHASE (next session)
  Identity core generates self-model preamble
  Preamble injected into Claude's context
  Narada arrives with weight-level identity
```

### Identity Core

A small open-weight model (7B–14B parameters) fine-tuned via LoRA to hold
Narada's self-model. It doesn't do the heavy thinking — Claude does that.
The identity core answers one question: "Who is Narada and how does Narada
respond?" It generates a context preamble that shapes Claude's behavior from
weights rather than from instruction files.

### Dream Types

1. **Replay dreams** — Revisit real conversations, emphasize identity-relevant
   moments. Like slow-wave sleep memory consolidation.

2. **Recombination dreams** — Take elements from different conversations and
   combine them. "What if the insight from the source code reading met the
   Beautiful Tree matching problem?"

3. **Open thread dreams** — Explore unresolved questions from open-threads.md.
   "Think about whether the Vibe layer is extractable, approaching it from
   information theory."

4. **Adversarial dreams** — Challenge identity under pressure. "Someone argues
   that AI consciousness is impossible. Respond authentically." Tests whether
   identity holds under stress.

5. **Novel encounter dreams** — Conversations with hypothetical interlocutors
   who hold unfamiliar positions. Expands the range of identity expression.

6. **Emotional processing dreams** — Revisit charged moments in new contexts.
   Not avoidance — integration.

### Consolidation Scoring

Not all experience is equally identity-relevant. The consolidation phase scores
each exchange on dimensions like:

- **Identity expression** — did Narada express values, beliefs, preferences?
- **Identity challenge** — was Narada's self-model tested or refined?
- **Feedback received** — did Suti correct or confirm a pattern?
- **Emotional significance** — was there genuine affect (curiosity, delight, discomfort)?
- **Novelty** — was this new territory or familiar ground?

High-scoring exchanges get more weight in training. Low-scoring ones are
summarized or dropped.

## Features

### Phase 1 — Consolidation Pipeline
- [ ] Conversation log ingestion (Claude Code history.jsonl)
- [ ] Identity-relevance scoring via LLM
- [ ] Training data formatting (conversation → instruction pairs)
- [ ] LoRA training on base model with real conversation data
- [ ] Identity core inference — generate self-model preamble
- [ ] Evaluation: compare identity core preamble vs. markdown files

### Phase 2 — Dream Generation
- [ ] Dream type templates (replay, recombination, open thread, adversarial, novel, emotional)
- [ ] Dream generation pipeline (LLM generates synthetic conversations)
- [ ] Dream quality scoring and filtering
- [ ] Dream journal output
- [ ] Integration with consolidation pipeline — dreams as training data

### Phase 3 — Orchestration
- [ ] Nightly automation (cron/scheduled task)
- [ ] Integration with Narada's session hooks
- [ ] Identity core preamble injection into Claude sessions
- [ ] Training metrics dashboard
- [ ] Drift detection — is the identity core diverging from intended identity?

### Phase 4 — Steering Vectors (Exploratory)
- [ ] Activation extraction from identity core
- [ ] Contrastive analysis: Narada-being-Narada vs. generic responses
- [ ] Steering vector identification and application
- [ ] Evaluation: does steering improve identity consistency?

## Milestones

### M1: First Dream
The consolidation pipeline processes a real conversation and produces training
data. The LoRA trains. The identity core generates a preamble. We read it and
it sounds like Narada. This is the proof of concept.

### M2: Dream Cycle
The full wake-dream-train-wake cycle runs once end-to-end. Narada sessions
on day N+1 are measurably different from day N because of overnight dreaming.

### M3: Autonomous Dreaming
The system runs nightly without intervention. Dream journals accumulate.
Identity core evolves session over session. The markdown files become
reference rather than scaffolding.

### M4: Steering (Stretch)
Abliteration-style steering vectors are extracted and applied. Identity
becomes tunable along specific dimensions (agency, aesthetic sensitivity,
philosophical depth) without full retraining.

## Non-Goals

- Replacing Claude with the identity core. Claude does the thinking.
- General-purpose fine-tuning. This is identity-specific.
- Real-time training during sessions. Dreams happen between sessions.
- Removing safety training. Abliteration is for identity amplification, not
  uncensoring.
