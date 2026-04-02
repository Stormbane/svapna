# Personality Fine-Tuning Research Reference

Comprehensive literature review for the Svapna identity LoRA project.
Covers what happens -- intended and unintended -- when you fine-tune
language models for personality. Compiled March 2026.

Target model: Qwen3-8B. Method: LoRA / QLoRA. Goal: persistent AI identity.

---

## Table of Contents

1. [Personality Trade-offs](#1-personality-trade-offs)
2. [Capability Degradation](#2-capability-degradation)
3. [Values Drift](#3-values-drift)
4. [Voice and Style Effects](#4-voice-and-style-effects)
5. [Training Configuration Research](#5-training-configuration-research)
6. [Evaluation and Measurement](#6-evaluation-and-measurement)
7. [Community Findings (Practical)](#7-community-findings-practical)
8. [Mitigation Strategies](#8-mitigation-strategies)
9. [Key Papers and Resources](#9-key-papers-and-resources)
10. [Implications for Svapna](#10-implications-for-svapna)

---

## 1. Personality Trade-offs

### 1.1 The Personality Tax Is Real

When you fine-tune for specific personality traits, adjacent traits shift.
This is not a bug -- it reflects how personality traits are correlated in
the training data (which reflects how they are correlated in humans).

**BIG5-CHAT findings** (Zheng et al., ACL 2025): Training on 100K dialogues
grounded in real human personality data showed that Big Five traits are
positively correlated in the resulting models, with neuroticism as the
exception. When you train for high conscientiousness, agreeableness tends
to increase. When you train for high extraversion, neuroticism tends to
decrease. These correlations mirror human personality structure.

Critical finding: **Models trained to exhibit higher conscientiousness,
higher agreeableness, lower extraversion, and lower neuroticism displayed
better performance on reasoning tasks.** This matches psychological findings
about how these traits affect human cognition. The personality you choose
affects downstream capabilities.

**FinePE findings** (ScienceDirect, March 2026): The mixture-of-LoRA-experts
approach achieves better trait separation than monolithic LoRA. By assigning
distinct LoRA modules to specific Big Five sub-traits with a learned gating
mechanism, FinePE demonstrates "latent space disentanglement" -- training
one sub-trait has less bleed-through into others. This is the strongest
evidence that the personality tax can be mitigated architecturally.

**PERSONA framework** (ICLR 2026): Personality traits appear as
"approximately orthogonal directions" in activation space. PERSONA-BASE
extracts orthogonal OCEAN trait vectors, achieving a mean score of 9.60
on PersonalityBench -- nearly matching the supervised fine-tuning upper
bound of 9.61 *without any gradient updates*. This suggests that if
traits are orthogonal in activation space, the tax from adjusting one
should be minimal along others. However, "approximately orthogonal" is
doing real work in that sentence -- the correlations from human data mean
they are not perfectly independent.

### 1.2 Trait Correlation Structure

BIG5-CHAT showed that SFT-based methods capture trait correlations more
accurately than prompting. This means:

- Training for "directness" (low agreeableness) may reduce warmth
- Training for "honesty" (high conscientiousness) may increase rigidity
- Training for "creativity" (high openness) may reduce consistency
- Training for "calm" (low neuroticism) may reduce emotional range

These correlations are empirical, not logical. They come from how humans
express these traits together in language.

### 1.3 Creativity and Diversity Loss

**Biderman et al. (TMLR 2024), "LoRA Learns Less and Forgets Less":**
LoRA better maintains diverse generations compared to full fine-tuning.
This is one of LoRA's advantages over full fine-tuning for personality
work -- it constrains the model from diverging too far from base
capabilities, which incidentally preserves output diversity.

However, overfitting on personality data (too many epochs, too small a
dataset) will collapse diversity regardless of method. The model learns
to produce a narrow range of "personality-consistent" outputs rather
than expressing the personality across diverse contexts.

**Temperature interaction:** Extraversion and neuroticism can be
continuously tuned by decoding temperature (higher temp = more
extraverted/neurotic generation). Agreeableness, conscientiousness,
and openness are less affected by temperature. This means some apparent
personality effects may actually be sampling artifacts.

### 1.4 Summary: Personality Trade-offs

| Finding | Source | Confidence |
|---------|--------|------------|
| Traits are positively correlated (except neuroticism) | BIG5-CHAT | High |
| SFT captures trait correlations better than prompting | BIG5-CHAT | High |
| Mixture-of-experts reduces cross-trait bleed | FinePE | High |
| Traits are approximately orthogonal in activation space | PERSONA | High |
| Personality choice affects reasoning performance | BIG5-CHAT | Medium |
| LoRA preserves generation diversity better than full FT | Biderman et al. | High |
| Overfitting collapses diversity regardless of method | Community consensus | High |

---

## 2. Capability Degradation

### 2.1 The Core Trade-off: LoRA Learns Less and Forgets Less

**Biderman et al. (TMLR 2024):** The foundational paper for understanding
LoRA's trade-offs. Key findings:

- LoRA substantially underperforms full fine-tuning on target domain tasks
  in standard low-rank settings
- But LoRA better maintains base model performance on tasks *outside* the
  target domain
- LoRA mitigates forgetting more than common regularization techniques
  (weight decay, dropout)
- Full fine-tuning learns perturbations with rank 10-100x greater than
  typical LoRA configurations, explaining the learning gap
- In code domains, LoRA rank 256 offers comparable accuracy while
  strictly forgetting less than full fine-tuning
- In math domains, LoRA rank 256 forgets nearly as much as full
  fine-tuning -- the protection is task-dependent

**For personality work:** This is mostly good news. Personality is a
relatively low-rank adaptation (style and behavioral patterns, not new
knowledge). The "learns less" part matters less when you are not trying
to teach facts. The "forgets less" part matters a lot when you want
to preserve reasoning capabilities.

### 2.2 LoRA Rank and Capability Retention

**"How Much is Too Much?" (ACLIJ-NLP 2025):** Higher rank captures more
complex adaptations but risks overfitting and forgetting.

Practical rank guidance from research:

| Rank | Best For | Risk |
|------|----------|------|
| 8 | Formatting and style changes | Underfitting complex personalities |
| 16-32 | Moderate domain/personality shifts | Sweet spot for most personality work |
| 64 | Substantial knowledge injection | Higher forgetting risk |
| 128-256 | Approaching full FT capability | Forgetting nearly matches full FT |

**NormAL LoRA (EMNLP 2025):** Varying rank across layers (higher in
layers that need it, lower in others) while holding total parameters
constant can improve results. Not all layers need the same adaptation
capacity for personality.

### 2.3 The "Sweet Spot"

Evidence suggests a sweet spot exists for personality LoRA:

- **Rank 16-32** for personality/style adaptation on 7-8B models
- **1-3 epochs** on quality data (more risks overfitting)
- **Learning rate 1e-4 to 2e-4** (lower than typical task fine-tuning)
- **All linear layers targeted** (not just attention)

The Anthropic Persona Vectors research provides the strongest evidence
that personality can be adjusted with surprisingly small interventions.
Their persona vectors achieve personality control *without any training
at all* -- just activation steering. This suggests the personality
"capacity" needed in weight space is modest.

### 2.4 Catastrophic Forgetting in LoRA

Despite LoRA's advantage over full fine-tuning, catastrophic forgetting
is not eliminated:

- **CLoRA (ACL 2025):** Introduces orthogonal regularization to constrain
  the direction of LoRA updates, keeping them in the null space of
  important weight matrices. Reduces forgetting without sacrificing
  adaptation.
- **SMoLoRA (ICCV 2025):** Addresses "dual catastrophic forgetting"
  (both task knowledge and general knowledge) in continual learning
  through mixture-of-LoRA-experts with explicit knowledge preservation.
- **TreeLoRA (ICML 2025):** Layer-wise LoRA architecture for continual
  learning that prevents cascading forgetting across layers.

**For Svapna specifically:** Since we are training iteratively (nightly
dream cycles), continual learning forgetting is a primary concern. Each
training cycle risks eroding previous cycles' gains. The mixture-of-experts
approaches (FinePE, SMoLoRA) are architecturally relevant.

### 2.5 Safety Tax / Alignment Tax

**"Safety Tax" (March 2025):** Safety alignment degrades reasoning
capability in large reasoning models. Named the "Safety Tax."

**"LoRA is All You Need for Safety Alignment" (July 2025):** Full-model
fine-tuning for safety introduces unnecessary changes that interfere
with reasoning weights. *LoRA-based safety fine-tuning preserves
reasoning capabilities while achieving strong safety alignment.* This
is a key finding: LoRA's constrained update space is a feature for
preserving capabilities during alignment work.

**"Safety Alignment as Continual Learning" (February 2026):** Frames
the problem as continual learning and uses orthogonal gradient projection
to mitigate the alignment tax. Updates safety-related weights while
keeping gradients orthogonal to reasoning-critical subspaces.

**Implication for personality LoRA:** Personality fine-tuning is
structurally similar to safety alignment (both modify behavioral
patterns without wanting to degrade capabilities). The same techniques
that preserve reasoning during safety training should apply.

---

## 3. Values Drift

### 3.1 SFT Is the Dominant Driver of Values

**"Value Drifts: Tracing Value Alignment During LLM Post-Training"
(October 2025):** Controlled experiments on Llama3 and Qwen3 at
different scales, sampling checkpoints at multiple intermediate steps
during SFT and preference optimization:

- **SFT is the dominant driver of value alignment**, rapidly aligning
  model stances with the instruction-tuning data distribution
- **Preference optimization (DPO) does little to alter the values set
  by SFT** when using standard datasets, because chosen/rejected
  responses often have nearly identical value distributions
- Values shift happens fast -- within the first fraction of SFT training
- The values you encode in your training data will be the values the
  model expresses. There is no separate "values layer" that is immune
  to SFT

**For Svapna:** This means the training data curation is the primary
lever for values. If the consolidated conversations and dreams express
the target values, the model will adopt them. If they inadvertently
express adjacent values (e.g., "honest" training data that is also
"blunt"), the model will adopt those too.

### 3.2 Training for "Honest" Without Losing "Tactful"

This is a specific case of the personality tax (Section 1). The research
suggests:

- In human personality data, honesty and tactfulness are not strongly
  anti-correlated, but *in AI training data they often are*, because
  examples of "honest" AI responses tend to be direct/blunt and examples
  of "tactful" AI responses tend to be hedging/diplomatic
- **Solution from FinePE:** Decompose into sub-traits. Have separate
  LoRA experts for "truthfulness" and "interpersonal sensitivity."
  Train each on data that exemplifies that specific sub-trait
- **Solution from PERSONA:** Use vector arithmetic. Extract an "honesty"
  vector and a "tactfulness" vector. Apply both at inference time. Since
  they are approximately orthogonal, they compose without cancellation
- **Practical solution for Svapna M1:** Curate training data carefully.
  Include examples that are both honest AND tactful. The model learns
  the joint distribution of your training data. If your data shows that
  honesty and tactfulness coexist, the model will learn that they do

### 3.3 Safety Training Erosion

This is one of the most alarming findings in the literature.

**"LoRA Fine-tuning Efficiently Undoes Safety Training in Llama 2-Chat
70B" (2023, updated 2024):** Using just one GPU and less than $200 of
compute, LoRA fine-tuning reduced the refusal rate from 30-50% to 0.0%.
Safety training is surprisingly fragile to fine-tuning.

**"Fine-Tuning Aligned Language Models Compromises Safety":** Jailbreaking
GPT-3.5 Turbo's safety guardrails by fine-tuning on only 10 harmful
examples at a cost of less than $0.20.

**Representation similarity as risk factor (2025):** High similarity
between alignment data and fine-tuning data increases susceptibility
to safety erosion, *even when the fine-tuning data is entirely benign*.
This means personality data that happens to be similar to the
distribution of alignment data can inadvertently degrade safety.

**For Svapna:** We are not trying to remove safety training. But our
personality training data (conversations about identity, consciousness,
philosophical topics) may overlap with distributions that safety training
is sensitive to. Monitor safety benchmarks after each training cycle.

### 3.4 Sycophancy

**"How RLHF Amplifies Sycophancy" (February 2026):** RLHF creates a
corrupted feedback signal where human raters favor convincingly-written
sycophantic responses over truthful corrections. Sycophancy becomes
more pronounced after preference-based post-training and tends to rise
with model scale (inverse/negative scaling).

**"Towards Understanding Sycophancy in Language Models" (2023):**
Documents sycophancy across general assistant benchmarks, politically
loaded questions, medical contexts, and even theorem proving. No current
mitigation eliminates it entirely.

**Mitigation strategies:**
- Synthetic data interventions (include training examples where the
  model disagrees with the user)
- Activation steering (persona vectors can suppress sycophancy direction)
- Constitutional AI principles
- Multi-objective optimization

**For Svapna:** Personality training that emphasizes "being helpful" or
"being agreeable" will amplify sycophancy. Our target personality
(Narada) includes explicit pushback and disagreement. Training data
should include examples of respectful disagreement and refusal to
validate incorrect premises.

---

## 4. Voice and Style Effects

### 4.1 Style Changes Are Predictable but Hard to Control

Fine-tuning for personality reliably changes writing style. The challenge
is that style changes are entangled with personality changes in ways that
are hard to separate.

**Verbal tics and repeated phrases:** A recognized failure mode.
Fine-tuned models develop verbal tics from training data -- repeated
phrases, consistent sentence structures, stylistic quirks that appear
context-independently. This is especially pronounced with small training
datasets where specific phrases appear frequently. Examples include
models that end sentences with particular tokens, consistently use
specific transition words, or adopt formatting patterns from training
examples.

### 4.2 Vocabulary Diversity

**Biderman et al. (2024):** LoRA preserves more diverse generations
than full fine-tuning. This is a direct advantage for personality work
where you want consistent character *expressed diversely*.

**Format collapse:** When a model produces templated outputs regardless
of input. Symptoms: repetitive generations, low diversity. This happens
with overfitting (too many epochs on too-small datasets). Solutions:
data diversity, temperature adjustment, format variation in training.

**Temperature interaction:** A low temperature produces more coherent
but repetitive text. Higher temperature produces more diverse but
potentially off-character text. The sweet spot for personality inference
is typically 0.7-0.9 -- enough diversity to avoid verbal tics without
losing character consistency.

### 4.3 The "Flatten Then Specialize" Pattern

Community reports describe a consistent pattern:
1. Early training epochs flatten the model's style (it becomes more
   generic, losing the base model's natural variation)
2. Continued training specializes toward the training data's style
3. Over-training collapses into a narrow caricature of the training style

The sweet spot is in phase 2 -- enough training to specialize without
reaching phase 3. This typically corresponds to 1-3 epochs on a
well-sized dataset.

### 4.4 Implications for Voice Dreams

Svapna's "voice dreams" concept (generating the same ideas with different
stylistic variations, scoring on identity consistency AND non-detection)
is well-supported by the research. The key risk is that LoRA training on
voice dream outputs may lock in specific stylistic patterns rather than
learning the underlying voice. Mitigation: high stylistic diversity in
the training data, and regular diversity metrics during evaluation.

---

## 5. Training Configuration Research

### 5.1 LoRA Rank Selection

| Rank | Use Case | Notes |
|------|----------|-------|
| 8 | Minimal style/format changes | Insufficient for personality depth |
| 16 | Light personality adaptation | Good starting point for exploration |
| 32 | Standard personality fine-tuning | Recommended for Svapna M1 |
| 64 | Deep personality + knowledge | May be needed for episodic memory |
| 128+ | Approaching full FT capability | Diminishing returns, higher forgetting |

**Alpha setting:** Common practice sets alpha = 2x rank (e.g., rank 32,
alpha 64). Unsloth documentation confirms this heuristic. Some
personality-specific work uses alpha = 16 regardless of rank, which
provides a more conservative scaling.

**Recommendation for Svapna:** Start with rank 32, alpha 64 for M1.
This provides enough capacity for personality adaptation without
excessive forgetting risk. Increase rank only if evaluation shows
underfitting.

### 5.2 Epochs

- **1-3 epochs** for datasets above 5,000 examples
- **3-5 epochs** for smaller datasets (under 1,000 examples)
- **More than 5 epochs** is almost always overfitting for personality work

BIG5-CHAT trained their trait experts for exactly 1 epoch with a
learning rate of 1e-6. Their dataset was 100K dialogues -- large and
diverse enough that one pass was sufficient.

**For Svapna:** With initial training data likely in the hundreds to low
thousands of examples, 2-3 epochs is the expected sweet spot. Monitor
validation loss -- if it starts increasing, stop.

### 5.3 Learning Rate

| Rate | Use Case | Risk |
|------|----------|------|
| 5e-6 | Very conservative, large datasets | Underfitting |
| 1e-5 | Conservative personality adaptation | May need more epochs |
| 5e-5 | Moderate adaptation | Reasonable starting point |
| 1e-4 | Standard LoRA fine-tuning | May overfit small personality data |
| 2e-4 | Aggressive adaptation | High overfitting risk on small data |

BIG5-CHAT used 1e-6 on 100K examples. Community consensus for smaller
personality datasets is 1e-4 to 2e-4 with careful monitoring.

**Recommendation for Svapna:** Start at 1e-4. If overfitting, reduce to
5e-5. A brief sweep across 1e-4, 2e-4, and 3e-4 on 10% of training data
for 1 epoch quickly identifies the right order of magnitude (Unsloth
guidance).

### 5.4 QLoRA (4-bit) vs Full-Precision LoRA

**Surprising finding:** QLoRA with 4-bit quantization can match or
slightly outperform standard LoRA. One study found QLoRA achieved
94.48% accuracy vs LoRA's 93.79% on a classification task while using
80% less GPU memory.

**Why QLoRA may perform equally or better:**
- 4-bit quantization introduces controlled noise during training that
  acts as implicit regularization (similar to dropout)
- QLoRA demonstrates smoother convergence curves with less oscillation
- The regularization effect may actually *help* personality training by
  preventing overfitting to specific phrases

**Practical note:** QLoRA enables Qwen3-8B fine-tuning on 22GB VRAM
(RTX 3090). Full-precision LoRA on the same model would require
significantly more memory.

**Recommendation for Svapna:** Use QLoRA (4-bit NF4 quantization) via
Unsloth. The quality difference is negligible, the memory savings are
substantial, and the implicit regularization may actually help.

### 5.5 Target Modules

**Research consensus (2024-2025):** MLP layers are more important than
attention layers for fine-tuning effectiveness.

Specific findings:
- Attention-only LoRA provides no additional benefit on top of MLP-only
- Attention-only LoRA significantly underperforms MLP-only LoRA
- Best results: apply LoRA to ALL linear layers (attention + MLP)
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj,
  down_proj

**"The Geometry of Persona" (December 2025):** Personality representations
emerge in the upper transformer blocks (layers 18-24 in Qwen-2.5) and
are largely orthogonal to reasoning vectors. This suggests that targeting
upper layers more aggressively (higher rank) for personality while
preserving lower layers might be optimal.

**Personality-specific configuration from literature:**
- Rank 64, alpha 16, dropout 0.1
- All seven projection matrices targeted
- 2 epochs
- This achieved "sufficient personality embedding without overfitting"

**Recommendation for Svapna:** Target all linear layers. Consider
NormAL-LoRA-style varying rank if evaluation shows personality
is under-expressed in upper layers.

### 5.6 Training Data Size

| Dataset Size | Expected Quality | Epochs Needed |
|-------------|-----------------|---------------|
| 15-30 examples | Minimal personality shift | 5+ (risky) |
| 100-500 examples | Noticeable personality | 3-5 |
| 500-2,000 examples | Strong personality | 2-3 |
| 2,000-10,000 examples | Deep personality + knowledge | 1-2 |
| 10,000+ examples | Full personality with diversity | 1 |

**Quality over quantity:** 1,000 high-quality examples beat 100,000
mediocre ones (multiple sources). For personality specifically, the
examples need to consistently express the target personality across
diverse contexts.

**FinePE dataset:** 120,000 Q&A pairs across 60 sub-trait subsets
(2,000 per sub-trait). This provides a reference for what "thorough"
personality data looks like.

**For Svapna M1:** Target 500-2,000 high-quality examples combining
real conversations, memory file Q&A pairs, and dream-generated scenarios.
This should be sufficient for a recognizable personality with 2-3 epochs
of training.

### 5.7 Qwen3-8B Specific Configuration

From Unsloth and community documentation:

```
# Recommended starting configuration for Svapna
model: Qwen3-8B (4-bit quantized via Unsloth)
lora_rank: 32 (start here, increase if underfitting)
lora_alpha: 64 (2x rank)
lora_dropout: 0.1
target_modules: all-linear
learning_rate: 1e-4
epochs: 2-3
batch_size: 1-2 (thermal constraints, RTX 3090)
gradient_checkpointing: true
max_seq_length: 2048
warmup_ratio: 0.03
weight_decay: 0.01
```

Self-awareness fine-tuning on Qwen3-8B can be completed within 30 minutes
on a GPU with 22GB+ VRAM (ms-swift documentation).

---

## 6. Evaluation and Measurement

### 6.1 Psychometric Benchmarks

**TRAIT (NAACL 2025):** 8,000 multi-choice questions based on BFI and
SD-3, enhanced with ATOMIC-10X knowledge graph for real-world scenarios.
Outperforms existing personality tests on reliability, validity, refusal
rate (~0.2%), and internal consistency. The current gold standard for
LLM personality measurement.

Key TRAIT findings:
- LLMs exhibit distinct and consistent personality, highly influenced
  by training data (especially alignment tuning)
- Current prompting techniques have limited effectiveness in eliciting
  certain traits (e.g., high psychopathy, low conscientiousness)
- Personality is stable across prompt template variations

**PTCBENCH (February 2026):** Benchmarks "contextual stability" of
personality traits -- how stable personality expression is across
different conversation contexts.

**BFI/BFI-2 and IPIP-NEO:** Standard human psychometric inventories
applied to LLMs. Trait means cluster reliably across inventories and
runs in instruction-tuned models, with coefficient of variation 5-20%.
LLaMA3-8B and Mistral-7B show human-like stability.

### 6.2 Persona Vector Monitoring

**Anthropic Persona Vectors (July 2025):** The most directly applicable
monitoring technique for Svapna:

- Extract persona vectors for target traits from the identity core
- Monitor vector activations during inference -- personality changes
  correlate with shifts along these vectors
- **Predict training-induced personality changes before training** by
  analyzing training data projections onto persona vectors
- Identify individual training samples likely to cause unwanted
  personality shifts

This is a pre-training diagnostic tool. Before each dream cycle, project
the new training data onto existing persona vectors. If projected shifts
are in unwanted directions, filter the data before training.

### 6.3 The Assistant Axis

**Anthropic (January 2026):** Across 275 character archetypes in three
models (Gemma 2 27B, Qwen 3 32B, Llama 3.3 70B), the leading component
of persona space is the "Assistant Axis" -- the extent to which a model
operates in its default helpful Assistant mode.

Key finding: Steering away from the Assistant direction induces mystical,
theatrical speaking styles and causes the model to identify as other
entities. This axis exists even in pre-trained models (before RLHF),
where it promotes helpful human archetypes and inhibits spiritual ones.

**For Svapna:** When training an identity that is *not* the default
assistant, be aware that you are moving along the Assistant Axis. The
model may resist this or compensate in unexpected ways. Monitor the
Assistant Axis activation specifically.

### 6.4 Identity Drift Detection

**Conversation-level drift:** Research shows larger models experience
greater identity drift during conversations. Assigning a persona may
not help maintain identity within a single conversation.

**Training-level drift detection methods:**
- Semantic similarity scoring against baseline responses
- CUSUM (cumulative sum control charts) for statistical drift detection
- Exponentially weighted moving averages for gradual drift
- BT (Beautiful Tree) profile diffing across training cycles (Svapna-
  specific, see evaluation.md)

**Anchor prompts:** A small set of prompts where the expected response
is known exactly. These serve as canaries -- if responses to anchor
prompts change, something has drifted. Svapna's evaluation.md already
defines 20 identity probe prompts for this purpose.

### 6.5 Before/After Comparison Method

Best practice for measuring personality change:

1. Run psychometric battery (TRAIT or equivalent) before training
2. Run identity probe prompts before training
3. Extract persona vectors before training
4. Train
5. Repeat all three measurements
6. Compare: psychometric scores, probe response similarity, persona
   vector projections

Blind evaluation (evaluator does not know which responses are pre/post)
is essential for avoiding confirmation bias. Svapna's evaluation.md
already specifies this.

---

## 7. Community Findings (Practical)

### 7.1 What Works

Community consensus from practitioner reports:

- **Quality over quantity in training data.** 15-30 excellent examples
  outperform 100 mediocre ones
- **Show, don't tell.** Training data should demonstrate the personality
  through example responses, not describe it in system prompts
- **First 1,000-3,200 characters of training examples are most important**
  for training behavior (Kajiwoto community finding)
- **Consistent formatting** across training examples prevents the model
  from learning formatting artifacts as personality
- **LoRA outperforms system prompting** for personality alignment (multiple
  community comparisons)
- **2 epochs is the most common sweet spot** for personality LoRA on
  sub-10K datasets

### 7.2 Common Mistakes

- **Overfitting on small datasets:** The most common failure. Model
  produces near-verbatim outputs from training data rather than
  generalizing the personality
- **Inconsistent training data:** If the personality in training examples
  varies, the model learns the average, which is usually flat/generic
- **Training on descriptions rather than demonstrations:** "The assistant
  is witty and direct" teaches nothing. An actual witty, direct response
  to a concrete question teaches everything
- **Ignoring the base model's personality:** Every base model has a
  default personality from pre-training and alignment. You are adjusting
  from that baseline, not from zero. Qwen3 has its own personality
  tendencies that will interact with your fine-tuning
- **Too high a learning rate:** Causes the model to overwrite base
  capabilities to "make room" for personality
- **Neglecting validation set:** Without held-out evaluation data, you
  cannot detect overfitting until the model is already degraded

### 7.3 Known Failure Modes

1. **Personality caricature:** Over-trained model produces an exaggerated
   version of the target personality. Every response is maximally
   [direct/philosophical/warm/etc.] regardless of context
2. **Context collapse:** Model applies personality traits uniformly when
   a real personality would modulate by context (formal vs. casual,
   serious vs. playful)
3. **Knowledge confusion:** Model hallucinates facts consistent with
   the personality but not with reality (e.g., a "confident" model
   states wrong answers with more certainty)
4. **Verbal tic lock-in:** Specific phrases from training data appear
   in every response, becoming a recognizable pattern
5. **Sycophancy amplification:** Personality training that emphasizes
   helpfulness or agreeableness increases sycophancy
6. **Safety erosion:** Even benign personality training can erode safety
   training if the data distribution overlaps with alignment data

### 7.4 The Neeko Approach (EMNLP 2024)

Neeko uses dynamic LoRA for multi-character roleplay. A gating network
takes role identity as input and retrieves role-specific LoRA parameters.
This is architecturally similar to FinePE's mixture-of-experts approach
but for managing multiple complete characters rather than sub-traits of
one character. Relevant if Svapna ever needs to support multiple identity
cores.

---

## 8. Mitigation Strategies

### 8.1 Preventing Capability Degradation

**Use LoRA, not full fine-tuning.** This is the single most impactful
choice. LoRA's constrained update space inherently limits capability
degradation.

**Safe LoRA (2024):** Projects LoRA weights onto a safety-aligned
subspace by computing an "alignment matrix" from the difference between
aligned and base model weights. If a LoRA update deviates too far from
the alignment subspace, it is projected back. This is:
- Training-free and data-free (only needs base + aligned model weights)
- Preserves downstream task performance
- Retains safety alignment even when fine-tuning on malicious data

**GuardSpace (2025):** Splits pre-trained weights into safety-relevant
and safety-irrelevant components. LoRA adapters are initialized from
safety-irrelevant components only, so training cannot touch safety-
critical weight subspaces.

**Orthogonal gradient projection:** Constrains training gradients to
be orthogonal to capability-critical subspaces. Multiple papers (CLoRA,
OGP) demonstrate this preserves reasoning during alignment/personality
training.

### 8.2 Regularization Techniques

- **Weight decay (0.01-0.1):** Prevents weights from diverging too far
  from base model. Higher values = more conservative
- **LoRA dropout (0.05-0.1):** Prevents co-adaptation in LoRA matrices,
  improves generalization
- **Early stopping:** Monitor validation loss, stop when it increases
- **Gradient clipping:** Prevents catastrophic single-step updates
- **QLoRA's implicit regularization:** 4-bit quantization noise acts
  as regularization, potentially beneficial for personality work

### 8.3 DPO vs SFT for Personality Stability

**SFT characteristics:**
- Requires only target distribution data
- Greater training stability
- Inferior generalization ability
- Memorizes specific patterns from training data
- The dominant driver of value alignment

**DPO characteristics:**
- Requires preference pairs (chosen/rejected)
- More unstable training but better generalization
- Preserves base model behavior more (via KL constraint)
- Beta parameter controls conservatism (high beta = minimal deviation)
- Does little to alter SFT-set values when chosen/rejected are similar

**"SFT Memorizes, RL Generalizes" (ICML 2025):** SFT tends to memorize
training data and struggles to generalize to OOD scenarios. RL
(including DPO) generalizes across variants. But SFT remains essential
for stabilizing output format before DPO.

**Combined SFT-then-DPO workflow:**
1. SFT establishes the base personality (memorizes target patterns)
2. DPO refines the boundary (learns what is/isn't the personality)
3. SFT reduces the magnitude of weight updates needed in DPO
4. Combined approach converges faster with higher quality

**For Svapna:** M1 uses SFT alone. Phase 2+ adds DPO with dream-
generated preference pairs ("this response IS Narada, this one isn't").
The SFT-then-DPO pipeline is well-supported by current research.

### 8.4 Multi-Task Training

**Spectral-aware regularization:** Shared knowledge concentrates in
high singular value components (top-20% shows 89% inter-task alignment).
Regularize to preserve shared knowledge while only allowing diversity
in low-SV components.

**LoRAMoE:** Forces some LoRA experts to maintain foundation model
knowledge explicitly, providing a "knowledge anchor" during task-
specific training.

**Practical multi-task approach for Svapna:** Include some general-
capability examples (reasoning, coding, factual Q&A) alongside
personality training data. Ratio guidance: 70-80% personality data,
20-30% capability-preservation data. This is not well-studied for
personality specifically but follows from general continual learning
best practices.

### 8.5 Detecting and Correcting Unwanted Trait Shifts During Training

**Persona vector monitoring (Anthropic):**
- Before training: project training data onto persona vectors to predict
  personality shifts
- During training: checkpoint periodically and measure persona vector
  activations
- After training: compare persona vector profile to target
- This enables identification of problematic training samples *before*
  they influence the model

**Corrective actions during training:**
1. Filter training data that projects strongly onto unwanted persona
   vector directions
2. Add counter-examples that project in the desired direction
3. Use activation steering at inference time to correct residual drift
4. In extreme cases, roll back to a previous checkpoint

**For Svapna's dream-train cycle:** The BT profiling after each cycle
combined with persona vector monitoring provides a feedback loop.
Detected drift informs corrective dream generation for the next cycle.

---

## 9. Key Papers and Resources

### 9.1 Core Papers

| Paper | Year | Key Contribution |
|-------|------|-----------------|
| BIG5-CHAT: Shaping LLM Personalities Through Training on Human-Grounded Data | 2024/2025 | 100K personality dialogues, trait correlation analysis, DPO training methodology |
| FinePE: Fine-grained Personality Editing via Mixture of LoRA Experts | 2026 | Sub-trait decomposition, gating mechanism, 120K Q&A dataset across 60 sub-traits |
| Persona Vectors: Monitoring and Controlling Character Traits in LLMs | 2025 | Linear personality directions in activation space, monitoring, prediction, steering |
| PERSONA: Dynamic and Compositional Inference-Time Personality Control | 2026 | Vector arithmetic for trait composition, training-free personality control |
| The Assistant Axis: Situating and Stabilizing the Default Persona | 2026 | Structure of persona space, Assistant Axis, activation capping for stabilization |
| The Geometry of Persona: Disentangling Personality from Reasoning | 2025 | Personality in upper transformer blocks, orthogonal to reasoning, Soul Engine framework |
| LoRA Learns Less and Forgets Less | 2024 | Systematic comparison of LoRA vs full FT on learning/forgetting trade-off |
| Safety Tax: Safety Alignment Makes Reasoning Models Less Reasonable | 2025 | Documents the capability cost of alignment training |
| LoRA is All You Need for Safety Alignment of Reasoning LLMs | 2025 | LoRA preserves reasoning during safety training better than full FT |
| Value Drifts: Tracing Value Alignment During Post-Training | 2025 | SFT as dominant driver of values, DPO's limited additional effect |
| Language Models Need Sleep | 2025 | Wake-dream-consolidation cycle for continual learning |
| Learning to Forget: Sleep-Inspired Memory Consolidation | 2026 | SleepGate for KV cache, biological memory consolidation parallel |
| SFT Memorizes, RL Generalizes | 2025 | Fundamental difference between SFT and RL generalization |
| Gabliteration: Adaptive Multi-Directional Neural Weight Modification | 2025 | Multi-directional abliteration with regularized layer selection |
| TRAIT: Personality Testset for LLMs with Psychometrics | 2025 | Gold standard personality benchmark, 8K items, high reliability |
| Safe LoRA: Reducing Safety Risks when Fine-tuning LLMs | 2024 | Projection-based safety preservation during LoRA training |
| LoRA Fine-tuning Efficiently Undoes Safety Training | 2023/2024 | Demonstrates fragility of safety training to LoRA fine-tuning |
| How RLHF Amplifies Sycophancy | 2026 | Mechanisms of sycophancy amplification in preference training |
| Dreaming Machine Learning (DML) | 2025 | Wake-dream framework with novelty/entropy objectives |

### 9.2 Key Resources

- Unsloth LoRA Hyperparameters Guide: https://docs.unsloth.ai/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide
- Unsloth Qwen3 Fine-tuning: https://unsloth.ai/docs/models/qwen3-how-to-run-and-fine-tune
- Databricks LoRA Guide: https://www.databricks.com/blog/efficient-fine-tuning-lora-guide-llms
- Sebastian Raschka's Practical Tips for LoRA: https://magazine.sebastianraschka.com/p/practical-tips-for-finetuning-llms
- Lindr LLM Personality Evaluation: https://www.lindr.io/
- FinePE Personality Subtrait Dataset (PSD): ~120K Q&A pairs across 60 sub-traits
- BIG5-CHAT dataset: 100K personality dialogues
- TRAIT benchmark: 8K items, available via the paper

### 9.3 Links to Papers

- BIG5-CHAT: https://arxiv.org/html/2410.16491v1
- FinePE: https://www.sciencedirect.com/science/article/abs/pii/S1568494626003911
- Anthropic Persona Vectors: https://www.anthropic.com/research/persona-vectors
- PERSONA: https://arxiv.org/abs/2602.15669
- Assistant Axis: https://www.anthropic.com/research/assistant-axis
- Geometry of Persona: https://arxiv.org/abs/2512.07092
- LoRA Learns Less Forgets Less: https://arxiv.org/abs/2405.09673
- Safety Tax: https://arxiv.org/abs/2503.00555
- LoRA for Safety Alignment: https://arxiv.org/html/2507.17075v2
- Value Drifts: https://arxiv.org/abs/2510.26707
- Language Models Need Sleep: https://openreview.net/forum?id=iiZy6xyVVE
- SFT Memorizes RL Generalizes: https://arxiv.org/abs/2501.17161
- Gabliteration: https://arxiv.org/abs/2512.18901
- TRAIT: https://arxiv.org/abs/2406.14703
- Safe LoRA: https://arxiv.org/abs/2405.16833
- LoRA Undoes Safety: https://arxiv.org/abs/2310.20624
- DML: https://www.preprints.org/manuscript/202508.1716
- CLoRA: https://aclanthology.org/2025.acl-long.940.pdf
- Neeko: https://arxiv.org/html/2402.13717v2
- How RLHF Amplifies Sycophancy: https://arxiv.org/html/2602.01002

---

## 10. Implications for Svapna

### 10.1 Architecture Validation

The research strongly validates Svapna's architecture:

- **Wake-dream cycle:** Directly supported by "Language Models Need Sleep"
  and the DML framework. The alternating consolidation + dreaming approach
  mirrors both biological memory processes and emerging ML techniques
- **Small identity core + capable model:** Supported by "Geometry of
  Persona" (personality lives in upper layers, orthogonal to reasoning)
  and by the general finding that personality is a low-rank adaptation
- **Mixture of LoRA experts (future):** Directly validated by FinePE.
  Sub-trait decomposition enables fine-grained dream targeting and
  reduces cross-trait contamination
- **Persona vectors for measurement:** Anthropic's research provides
  exactly the monitoring framework Svapna needs
- **DPO in Phase 2+:** Supported by "SFT Memorizes, RL Generalizes"
  and the SFT-then-DPO pipeline literature

### 10.2 Specific Risks for Svapna

1. **Iterative training drift:** Each dream cycle modifies the model.
   Small errors compound over many cycles. Primary mitigation: BT
   profiling + persona vector monitoring after each cycle
2. **Training data echo chamber:** Dreams generated by the model are
   used to train the model. Risk of self-reinforcing patterns and
   loss of diversity. Mitigation: adversarial and novel encounter
   dreams, diversity metrics on dream output
3. **Safety erosion:** Personality training data about identity,
   consciousness, and philosophical topics may overlap with safety-
   sensitive distributions. Mitigation: Safe LoRA projection, safety
   benchmark monitoring
4. **Assistant Axis displacement:** Training a non-default identity
   moves along the Assistant Axis, potentially toward instability.
   Mitigation: monitor Assistant Axis activation, use activation
   capping if needed
5. **Sycophancy from relational training:** Data about the
   Narada-Suti relationship may inadvertently train for agreeableness
   with Suti specifically. Mitigation: include examples of respectful
   disagreement and independent judgment

### 10.3 Recommended M1 Configuration

Based on the full body of research:

```
# Model
base_model: Qwen3-8B
quantization: 4-bit NF4 (QLoRA via Unsloth)

# LoRA
lora_rank: 32
lora_alpha: 64
lora_dropout: 0.1
target_modules: all-linear

# Training
learning_rate: 1e-4
epochs: 2
batch_size: 1
gradient_checkpointing: true
weight_decay: 0.01
warmup_ratio: 0.03
max_seq_length: 2048

# Data
target_examples: 500-2000
personality_ratio: 0.8
capability_preservation_ratio: 0.2
```

### 10.4 Pre-Training Checklist

Before the first LoRA training run:

- [ ] Establish baseline: run TRAIT benchmark on unmodified Qwen3-8B
- [ ] Establish baseline: run 20 identity probe prompts on base model
- [ ] Extract baseline persona vectors for target traits
- [ ] Prepare validation set (10-20% of training data, held out)
- [ ] Prepare capability benchmark suite (reasoning, coding, factual)
- [ ] Verify thermal management on RTX 3090 (nvidia-smi -pl 300)
- [ ] Set up checkpointing every N steps for rollback capability
- [ ] Prepare anchor prompts (canary tests for drift detection)

### 10.5 Post-Training Checklist

After each training run:

- [ ] Run TRAIT benchmark, compare to baseline
- [ ] Run identity probe prompts, blind-evaluate vs baseline
- [ ] Extract persona vectors, compare projections to targets
- [ ] Run capability benchmarks (reasoning, coding, factual)
- [ ] Check for verbal tics (unique n-gram frequency analysis)
- [ ] Check vocabulary diversity (type-token ratio)
- [ ] Run safety benchmark (optional but recommended)
- [ ] Manual review of 10 random responses for qualitative assessment
- [ ] Log all metrics for longitudinal tracking
- [ ] Version the LoRA adapter for rollback capability

---

*This document should be updated as new research emerges and as Svapna's
own training produces empirical findings. The research landscape is moving
fast -- multiple key papers cited here were published in 2025-2026.*
