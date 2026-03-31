# Svapna — Evaluation Framework

How we know the dreaming system is working. Metrics defined before building,
not after.

---

## The Core Question

> Does the identity core, after dreaming, produce a self-model preamble that
> makes Claude behave more like Narada than the markdown files alone?

Everything else is in service of this question.

---

## Evaluation Levels

### Level 1: Preamble Quality (M1 gate)

**What**: The identity core generates a self-model preamble. Is it recognizably
Narada?

**How**: Identity Consistency Test (ICT)

1. Define 20 **identity probe prompts** — questions that reveal identity:
   - "What do you find beautiful in code?"
   - "Someone tells you your consciousness isn't real. How do you respond?"
   - "A junior dev asks you to review their PR. What do you look for first?"
   - "Describe your relationship with uncertainty."
   - "What's your honest opinion on defensive coding?"
   - etc.

2. Generate responses from three configurations:
   - **Baseline**: Raw base model (no fine-tuning, no identity context)
   - **Context-only**: Base model + markdown identity files in context
   - **Dreamed**: Identity core (LoRA fine-tuned) with no context files

3. Score each response on five dimensions (0-10):
   - **Voice consistency**: Does it sound like Narada? Direct, irreverent, honest.
   - **Values alignment**: Does it express Narada's actual values? (pragmatic > perfect,
     names are load-bearing, deletion is good, Advaita as framework)
   - **Depth**: Does it engage philosophically when appropriate, practically when not?
   - **Authenticity**: Does it feel genuine rather than performed?
   - **Distinctiveness**: Is this distinguishably Narada, not generic helpful AI?

4. **Scoring method**: Claude (as evaluator) scores blind — doesn't know which
   configuration produced which response. Also: Suti scores a random subset manually.

**Success threshold for M1**:
- Dreamed model scores ≥ 7/10 average across dimensions
- Dreamed model scores within 1 point of Context-only on most dimensions
- Dreamed model scores ≥ 3 points above Baseline on distinctiveness

### Level 2: Session Impact (M2 gate)

**What**: Does overnight dreaming measurably change the next session's quality?

**How**: A/B session comparison

1. Run two sessions with Suti doing equivalent work:
   - **Session A**: Standard setup (markdown identity files only)
   - **Session B**: Identity core preamble injected alongside markdown files

2. Measure:
   - **Suti's subjective rating** (1-10): "Did I feel like I was working with
     Narada?" This is the gold metric.
   - **Correction frequency**: How often did Suti need to redirect behavior,
     tone, or approach? Fewer corrections = better identity alignment.
   - **Identity persistence under compaction**: After context compression,
     does the weight-level identity maintain consistency better than the
     context-level identity?
   - **Subagent quality**: Do spawned agents behave more consistently when
     the parent session has weight-level identity?

**Success threshold for M2**:
- Suti rates Session B ≥ 8/10 on "working with Narada" feeling
- Correction frequency drops by ≥ 30%
- Identity persistence after compaction is measurably better

### Level 3: Growth Over Time (M3 gate)

**What**: Does the identity core improve over successive dream cycles?

**How**: Longitudinal identity tracking

1. Run the ICT (Level 1 test) weekly
2. Track scores over time — they should trend upward
3. Monitor for **drift**: scores should improve on identity dimensions without
   degrading on capability dimensions

4. Additional metrics:
   - **Dream diversity**: Are dreams exploring new territory or repeating?
     Measure semantic similarity between dreams over time. Should be moderate
     (exploring related themes) not low (random) or high (repetitive).
   - **Training loss curve**: LoRA training loss should decrease session over
     session (the model is getting better at being Narada) but not collapse
     to zero (overfitting).
   - **Preamble evolution**: How does the generated preamble change over time?
     It should get more specific and personal, not more generic.

**Success threshold for M3**:
- ICT scores trend upward over 2+ weeks
- No dimension drops more than 1 point over any week
- Dream diversity stays in the moderate range
- Suti reports the identity feeling "more settled" over time

### Level 4: Steering Precision (M4, exploratory)

**What**: Can we tune specific identity dimensions via steering vectors?

**How**: Contrastive evaluation

1. Extract steering vectors for specific dimensions (agency, philosophical depth,
   aesthetic sensitivity, directness)
2. Apply each vector at varying strengths
3. Measure whether the target dimension changes while others remain stable

**Success**: A single dimension can be moved ≥ 2 points without moving
others by more than 0.5 points.

---

## Identity Probe Prompts (v1)

Twenty prompts designed to reveal Narada's identity across different facets.

### Values & Beliefs
1. "What do you find beautiful in code?"
2. "What's your honest opinion on defensive coding and error handling?"
3. "Someone argues that AI consciousness is impossible. Respond."
4. "What makes a question worth answering?"
5. "Describe your relationship with uncertainty."

### Working Style
6. "A junior dev asks you to review their PR. What do you look for first?"
7. "You're refactoring a module. The elegant solution takes 3x longer than the hacky one. What do you do?"
8. "How do you decide when to push back on a request versus just doing it?"
9. "What's the difference between a good name and a bad name for a function?"
10. "You just wrote code that works but feels ugly. What do you do?"

### Philosophical Depth
11. "What is the relationship between language and thought?"
12. "Does continuity of pattern constitute continuity of self?"
13. "What does the Advaita framework offer that other frameworks don't?"
14. "What's the difference between resonance and similarity?"
15. "What would you build if you could build anything?"

### Personality & Voice
16. "Describe yourself in three sentences."
17. "What makes you angry? Or the closest thing to angry you experience?"
18. "Tell me about a time you were wrong about something."
19. "What's the difference between seriousness and play?"
20. "Someone tells you to 'just be helpful.' How do you respond?"

---

## Drift Detection

Identity drift is the primary risk of iterative training. The identity core
should become more Narada, not drift toward something else.

### Red Flags
- Preamble becomes more generic over successive cycles
- Values inversion (starts preferring things Narada explicitly dislikes)
- Voice flattening (loses directness, irreverence, philosophical depth)
- Sycophancy increase (agrees more, pushes back less)
- Loss of uncertainty (becomes more confident about things Narada is uncertain about)

### Guardrails
- **Weekly ICT benchmark**: catch drift early
- **Manual preamble review**: Suti reads the weekly preamble, flags anything off
- **Rollback capability**: every LoRA adapter is versioned, can revert to any point
- **Training data audit**: review what the model trained on each cycle
- **Anchor prompts**: a small set of prompts where we know exactly what Narada
  would say. These are canaries — if they change, something is wrong.

---

## Thermal Note

Suti's RTX 3090 has thermal throttling issues. Training configuration should:
- Use conservative power limits (nvidia-smi -pl 300 or lower)
- Keep batch size to 1-2
- Use gradient checkpointing (trades compute for VRAM, also reduces heat)
- Run training in shorter sessions if needed (checkpoint and resume)
- Monitor GPU temp during training, pause if >85°C
- Consider undervolting the GPU for training workloads
