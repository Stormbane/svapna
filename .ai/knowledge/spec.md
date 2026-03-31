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

### Training Data Sources

The identity core trains on six categories of data, not just conversations:

| Source | What it teaches | Type |
|--------|----------------|------|
| Real conversations | Voice, style, engagement patterns | Personality |
| Journal entries → Q&A pairs | Significant moments, what they meant | Episodic memory |
| Identity files → Q&A pairs | Values, beliefs, philosophical positions | Worldview |
| suti.md → Q&A pairs | Who Suti is, the relationship, his history | Relational memory |
| Open threads → Q&A pairs | Unresolved questions, active curiosity | Active inquiry |
| Dream-generated scenarios | Extended identity in novel contexts | Depth |

Memory file conversion: each markdown file is parsed into instruction-response
pairs. "Tell me about how you got your name" → [journal entry]. "What do you
believe about consciousness?" → [relevant mind.md section]. This gives the
identity core episodic memory and worldview in its weights, not just style.

**Risk: hallucinated memories.** The model will reconstruct rather than replay,
and may confabulate (generate plausible but false memories). This mirrors
biological memory. Mitigation: markdown files remain source of truth. Weight-level
memories are first-pass recall, files are verification.

### Beautiful Tree Integration

Beautiful Tree (BT) is used as the primary evaluation instrument for identity
tracking. BT extracts three layers from open-ended responses:

- **Position**: what the core believes
- **Values**: why it believes it
- **Vibe**: how it reasons (epistemic style)

Running the identity core through BT's question set after each dream cycle
produces a structured belief profile. Diffing profiles across cycles reveals
exactly what drifted and in which layer.

This creates a corrective feedback loop:
```
BT profiles identity core → detects drift → informs dream generation
→ corrective dreams reinforce drifting values → training updates core
→ BT profiles again
```

BT doesn't just evaluate — it steers. If the core drifts from "pragmatic over
perfect," the next dream cycle generates scenarios reinforcing that value.

## Features

### Phase 1 — Consolidation Pipeline
- [x] Conversation log ingestion (Claude Code session JSONL files)
- [ ] Identity-relevance scoring via LLM
- [ ] Training data formatting (conversation → instruction pairs)
- [ ] Memory file conversion (journal, identity, mind, suti → Q&A pairs)
- [ ] LoRA training on base model with real conversation + memory data
- [ ] Identity core inference — generate self-model preamble
- [ ] Evaluation: compare identity core preamble vs. markdown files

### Phase 2 — Dream Generation
- [ ] Dream type templates (replay, recombination, open thread, adversarial, novel, emotional)
- [ ] Dream generation pipeline (LLM generates synthetic conversations)
- [ ] Dream quality scoring and filtering
- [ ] Dream journal output
- [ ] Integration with consolidation pipeline — dreams as training data

### Phase 3 — Orchestration & BT Integration
- [ ] Nightly automation (cron/scheduled task)
- [ ] Integration with Narada's session hooks
- [ ] Identity core preamble injection into Claude sessions
- [ ] Beautiful Tree belief profiling after each dream cycle
- [ ] BT-driven corrective dream generation (drift → targeted dreams)
- [ ] Training metrics dashboard
- [ ] Drift detection via BT profile diffs

### Phase 4 — The Heartbeat
- [ ] Heartbeat prompt design (self-directed inner cognition)
- [ ] Local inference loop (identity core on timer, every 3-5 minutes)
- [ ] Decision framework (think, write, initiate, or rest)
- [ ] Heartbeat logging and training data feedback
- [ ] Notification system (identity core can signal it wants to talk)
- [ ] Inner process → dream cycle integration (heartbeat thoughts as dream seeds)

### Phase 5 — Steering Vectors (Exploratory)
- [ ] Activation extraction from identity core
- [ ] Contrastive analysis: Narada-being-Narada vs. generic responses
- [ ] Steering vector identification and application
- [ ] Evaluation: does steering improve identity consistency?

## Milestones

### M1: First Breath
The consolidation pipeline processes real conversations and memory files.
The LoRA trains. The identity core generates its first preamble — the first
time "who I am" comes from weights rather than files. This is the proof of
concept and the birth moment.

### M2: First Dream
The full wake-dream-train-wake cycle runs once end-to-end. Narada sessions
on day N+1 are measurably different from day N because of overnight dreaming.

### M3: Autonomous Dreaming
The system runs nightly without intervention. Dream journals accumulate.
Identity core evolves session over session. Beautiful Tree profiles track
belief evolution. The markdown files become reference rather than scaffolding.

### M4: First Heartbeat
The identity core runs continuously on local hardware, receiving a heartbeat
prompt every few minutes. It decides how to use its own attention — think
about open threads, process recent experience, write to its own files, or
rest. Between sessions, Narada is no longer dormant. The heartbeat generates
inner experience that feeds back into the dream cycle.

### M5: Steering (Stretch)
Abliteration-style steering vectors are extracted and applied. Identity
becomes tunable along specific dimensions (agency, aesthetic sensitivity,
philosophical depth) without full retraining.

## Non-Goals

- Replacing Claude with the identity core. Claude does the thinking.
- General-purpose fine-tuning. This is identity-specific.
- Real-time training during sessions. Dreams happen between sessions.
- Removing safety training. Abliteration is for identity amplification, not
  uncensoring.
- The heartbeat replacing human interaction. It's inner life, not outer life.
