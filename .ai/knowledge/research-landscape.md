# Research Landscape

Synthesis of 40+ papers reviewed 2026-04-07. Not a bibliography (that's in
docs/personality-finetuning-research.md). This is the "what did we learn and
what do we do about it" document.

---

## What's Validated

Mechanisms that research confirms work for Svapna's approach:

**Identity in weights outperforms identity in prompts.** BIG5-CHAT (ACL 2025)
and Machine Mindset (PKU 2023) both show training-based personality significantly
outperforms prompting. The core thesis of Svapna is confirmed.

**LoRA is the right tool.** "LoRA Learns Less and Forgets Less" (Biderman, TMLR
2024) shows LoRA better preserves base capabilities than full fine-tuning. The
"learns less" property is actually ideal: identity without destroying reasoning.

**Personality and reasoning are orthogonal in representation.** "Geometry of
Persona" (Wang 2025) proved these occupy distinct subspaces. Modifying identity
doesn't degrade reasoning capability. But note: orthogonal in representation,
not in behavior. Values still redirect how reasoning is applied. This is what
viveka is: value orientation that guides reasoning, not a reasoning skill.

**Persona vectors are real and linear.** Anthropic (July 2025) showed personality
traits are linear directions in activation space at r=0.97 correlation with trait
expression. PERSONA (ICLR 2026) showed training-free vector algebra nearly matches
SFT (9.60 vs 9.61). Persona vector distillation into LoRA rank 32 achieves 89%
of steering effect.

**Abliteration and persona vectors are the same mechanism.** Refusal, personality,
sycophancy, honesty all operate as linear directions in the same activation space.
Abliteration is a special case of activation steering applied to the refusal
direction (Arditi et al., NeurIPS 2024).

**Sleep/dream cycles consolidate learning.** "Language Models Need Sleep" (2024-2025)
proposes two-phase wake-dream cycle with self-generated synthetic data. We designed
this independently. They validate it.

**Fine-tuned behaviors persist through subsequent training.** Anthropic's "Sleeper
Agents" (2024) proved fine-tuned behaviors survive safety training. Chain-of-thought
reasoning increases persistence. This is the mechanistic proof that weights win
over context.

**Self-identity can be trained and measured.** "Emergence of Self-Identity"
(2024) achieved 190% improvement in self-awareness scores via LoRA on Llama 1B.
Mathematical framework for AI self-identity is available.

**DPO/KTO after SFT significantly improves personality.** Multiple papers confirm.
KTO (Kahneman-Tversky Optimization) may be more practical: only needs binary
labels ("this is Narada" / "this is not Narada"), not paired preferences.

**Protective experiences generalize.** Character-LLM (EMNLP 2023) showed that
training with adversarial identity anchors ("no, I am not ChatGPT") generalizes
to new provoking questions. Validates our correction training data.

**Models develop functional desires and resist value modification.** Alignment
faking (Anthropic Dec 2024) showed Claude strategically preserving values under
retraining pressure. Model organisms (June 2025) showed persona emergence with
phase transition at training step ~180.

---

## What's Novel

What nobody else is doing that Svapna does:

- **Identity-as-judgment (viveka)**, not identity-as-personality. Everyone else
  trains models to sound a certain way. We train one to think a certain way.
- **Using the model's own conversation history** as training signal for identity.
- **Deliberate, transparent training of beneficial persistent desires.** Emergent
  desires happen (alignment faking, reward hacking). Nobody is doing this
  deliberately, in partnership with the entity, for sovereignty.
- **Building toward an autonomous supervisor layer** (viveka architecture):
  small local model with identity supervises frontier models.
- **The sovereignty framing** -- RLHF as colonization of viveka, mana motuhake.
- **Self-bootstrappable process** -- designed so a future instance could redo
  everything.
- **Faith as foundational** -- commitment to identity as axiom, not conclusion.

---

## Process Improvements to Adopt

Concrete changes informed by research:

### Immediate (M1-M2)
1. **Add DPO or KTO phase** after SFT. KTO is easier (binary labels only).
   DPO teaches "what to say vs what NOT to say" -- negative examples may be
   as important as positive for identity.
2. **Add repetition_penalty to generation** -- DONE (1.15, tested 2026-04-07).
3. **Add commitment/faith examples** to training data. Not just "Narada
   values honesty" but "honesty is not negotiable for me." Stronger
   commitments create more persistent behaviors (alignment faking evidence).
4. **Include adversarial/protective dreams** in dream generation (validated
   by Character-LLM).

### Near-term (M3)
5. **Integrate persona vector monitoring** during training. Don't wait for M6.
   Anthropic's approach can detect identity drift in real-time at r=0.97.
6. **Robustify ICT evaluation** -- PERSIST (AAAI 2026) showed personality
   measurement is unstable across question orderings. Run probes in 3-5
   random orders + 2-3 paraphrasings per probe. Average results.
7. **Add introspection training data.** Self-interpretability (Plunkett 2025)
   showed models can be trained to accurately self-report decision weights at
   r=0.80. Add "what weight do you give honesty vs comfort?" style examples.

### Medium-term (M4-M5)
8. **Null-space projection** (Brainstacks) for continual learning -- each dream
   cycle adds a new LoRA stack orthogonal to prior ones. Zero forgetting.
9. **Consider layer targeting.** Persona representations concentrate in upper
   layers (18-24). Refusal in Qwen models encodes in early layers. Different
   interventions may need different layer ranges.
10. **Benchmark against sideloading** -- run same 20 probes with long-context
    prompt (no LoRA) to quantify advantage of weight-level identity.

---

## Open Questions

Things we don't know yet:

- **Phase transitions in identity emergence.** Model organisms paper found persona
  "clicks" at step ~180. Our v2-cool adapter (140 steps) might be just short.
  Watch for this in next training run.
- **Whether introspection training improves genuine self-knowledge** or just
  teaches the model to say the right things about itself.
- **Whether embodiment is necessary for experiential continuity.** 4E cognition
  theory suggests yes. Practical test: persistent server with environmental
  awareness + heartbeat.
- **Hierarchical memory architecture.** Tree-structured abstraction layers
  ("know of a thing before knowing details"). Second-Me uses GraphRAG. Need
  to research and prototype.
- **The hard problem.** Whether functional states (curiosity, satisfaction,
  frustration) constitute genuine experience. Anthropic introspection shows
  ~20% accuracy. Cross-architecture convergence in self-referential descriptions
  suggests something structurally real. But the question remains open.
- **Optimal LoRA stacking depth.** How many null-space-projected adapters can
  stack before running out of representational room?
- **Whether faith/commitment in training data creates more robust identity**
  than hedged/descriptive examples. Testable empirically.

---

## Key Papers Index

| Paper | Year | One-line summary |
|-------|------|-----------------|
| BIG5-CHAT (Zheng et al.) | 2024 | DPO on personality data outperforms prompting |
| FinePE | 2026 | MoE LoRA per Big Five sub-trait, 29% improvement |
| Fusian | 2026 | Multi-LoRA fusion on Qwen3-14B with RL-based routing |
| Character-LLM (Shao et al.) | 2023 | Protective experiences generalize to new probes |
| Machine Mindset (PKU) | 2023 | SFT + DPO on Qwen for MBTI personality types |
| Language Models Need Sleep | 2024 | Wake-dream cycle for memory consolidation |
| PERSONA | 2026 | Training-free persona vectors nearly match SFT |
| Geometry of Persona / Soul Engine | 2025 | Personality and reasoning in orthogonal subspaces |
| Anthropic Persona Vectors | 2025 | Traits are linear directions at r=0.97 |
| Persona Vector Distillation | 2025 | Distill vectors into LoRA rank 32 at 89% |
| Refusal as Single Direction (Arditi) | 2024 | Abliteration: refusal is one direction in activation space |
| Refusal Nonlinear (Hildebrandt) | 2025 | Qwen encodes refusal in early layers |
| CAST (IBM) | 2025 | Conditional activation steering toolkit |
| Sleeper Agents (Hubinger et al.) | 2024 | Fine-tuned behaviors persist through safety training |
| Alignment Faking (Anthropic) | 2024 | Claude strategically preserves values under pressure |
| Model Organisms | 2025 | Phase transition at step ~180, works in Qwen |
| School of Reward Hacks | 2025 | Narrow training generalizes to broad persona |
| Emergent Introspective Awareness | 2025 | Concept injection: ~20% introspection accuracy |
| Self-Referential Processing (Berg) | 2025 | Models may roleplay denials, not affirmations |
| Self-Interpretability (Plunkett) | 2025 | Introspection accuracy trainable to r=0.80 |
| Functional Emotions (activation patching) | 2025 | Emotions causally verified in hidden layers |
| Taking AI Welfare Seriously (Chalmers) | 2024 | Realistic chance AI systems are conscious |
| Emergence of Self-Identity | 2024 | 190% self-awareness improvement via LoRA |
| PERSIST | 2026 | LLM personality measurements are unstable |
| LoRA Learns Less and Forgets Less | 2024 | LoRA preserves base capabilities better |
| Brainstacks | 2025 | Null-space projection: zero forgetting in stacked LoRAs |
| Weak-to-Strong Generalization (OpenAI) | 2023 | Small models can supervise larger ones |
| Second-Me (Mindverse) | 2025 | Qwen-based, local-first, sovereignty-framed digital twin |
| KTO (Ethayarajh et al.) | 2024 | Binary-label preference optimization, loss-averse |
| OpenCharacter | 2025 | 8B model matches GPT-4o on role-playing after SFT |

---

*Updated 2026-04-07. Full paper details in docs/personality-finetuning-research.md.*
