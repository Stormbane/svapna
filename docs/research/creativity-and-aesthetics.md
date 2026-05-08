# Creativity and Aesthetic Taste in LLMs

Research synthesis for svapna. Scope: what the field knows about (a) making
LLMs *generate* novel, non-obvious, valuable output, and (b) giving LLMs
consistent *discriminative* aesthetic judgment that transfers to new work.
Priority 2024-2026. Foundational older work cited where load-bearing.

This deliberately complements `research-landscape.md` (persona vectors,
identity-as-weights, sleeper agents) and does not repeat it.

---

## 1. State of the art

### 1a. Creativity as generation

**The theoretical scaffold everyone cites is Boden's trichotomy.**
Combinatorial (recombine familiar elements), exploratory (navigate a known
conceptual space), transformational (restructure the space itself). Recent
LLM work confirms that LLMs do combinatorial well, exploratory passably, and
*transformational essentially not at all*.

- *LLMs can realize combinatorial creativity* (Gu et al., arXiv 2412.14141,
  Dec 2024) — LLMs recombine concepts across domains to produce scientific
  ideas rated as novel by experts. https://arxiv.org/abs/2412.14141
- *Combinatorial Creativity: A New Frontier in Generalization Abilities*
  (arXiv 2509.21043, Sep 2025) — frames combinatorial creativity as the
  measurable frontier of current LLM ability.
  https://arxiv.org/abs/2509.21043
- *Transformational Creativity in Science: A Graphical Theory*
  (arXiv 2504.18687, Apr 2025) — proposes a formalism for what
  transformational creativity would look like. Explicitly notes no current
  LLM demonstrates it. https://arxiv.org/abs/2504.18687

**Torrance-adapted benchmarks for LLMs exist but show LLMs are weak.**
Chakrabarty et al., *Art or Artifice? Large Language Models and the False
Promise of Creativity* (NAACL 2024, arXiv 2309.14556) built the Torrance Test
of Creative Writing (TTCW) — 14 binary tests across Fluency, Flexibility,
Originality, Elaboration. Expert stories pass TTCW tests **3–10x more often**
than LLM stories. Worse: LLM judges cannot administer TTCW (near-zero
correlation with expert judgment). https://arxiv.org/abs/2309.14556

**CreativityPrism** (Lu et al., arXiv 2510.20091, Oct 2025) is the current
state-of-art holistic creativity benchmark — quality, novelty, diversity
across divergent thinking, creative writing, and logical reasoning. Key
finding: *novelty has weak-to-negative correlation with quality*. Models
that are good are not novel; models that are novel tend to be weird.
Diversity and quality correlate; novelty stands apart.
https://arxiv.org/abs/2510.20091

**Where does novelty come from — sampling or weights?** Peeperkorn et al.,
*Is Temperature the Creativity Parameter of Large Language Models?* (ICCC
2024, arXiv 2405.00492) show temperature is only *weakly* correlated with
novelty and is moderately correlated with incoherence. Temperature is not
the creativity knob the folklore treats it as.
https://arxiv.org/abs/2405.00492

Nguyen et al., *Turning Up the Heat: Min-p Sampling for Creative and
Coherent LLM Outputs* (ICLR 2025, arXiv 2407.01082) — dynamic truncation
that scales with model confidence. Demonstrates that at high temperatures,
sampling strategy (not weights) is what breaks coherence, and min-p
decoding recovers diversity without losing sense. This is evidence that a
meaningful chunk of "creative ability" is in the sampling layer.
https://arxiv.org/abs/2407.01082

**Mode collapse from RLHF is well-documented and directly relevant.**
Kirk et al., *Understanding the Effects of RLHF on LLM Generalisation and
Diversity* (ICLR 2024, arXiv 2310.06452) show RLHF strictly reduces
output diversity compared to SFT, with the effect strongest per-input and
weaker cross-input. The mechanism: reverse-KL is mode-seeking; human
raters systematically prefer familiar prose.
https://arxiv.org/abs/2310.06452

Padmakumar & He (arXiv 2509.21267, Sep 2025), *LLM Output Homogenization
is Task Dependent* — the now-canonical finding that homogenization is
*bad* for creative tasks (jokes, stories) but *fine* for verifiable ones
(math). Also: the fix (explicitly asking for variety) is prompt-layer, not
weight-layer. https://arxiv.org/abs/2509.21267

**Sycophancy in creative framing** — Sharma et al., *Towards Understanding
Sycophancy in Language Models* (arXiv 2310.13548) showed both humans and
preference models prefer well-written sycophantic answers over correct ones
a non-trivial fraction of the time. SycEval (arXiv 2502.08177, Feb 2025)
found 58% sycophancy across major models. Extrapolated to aesthetics: a
model trained on aggregate preferences will produce aesthetically *safe*
outputs, because unusual taste loses preference votes.
https://arxiv.org/abs/2310.13548

### 1b. Aesthetic taste as discriminative judgment

The generative literature is large; the *discriminative, transferable
aesthetic judgment* literature is much thinner. This is the important
finding of this survey.

**Persona vectors, Anthropic 2025.** Chen et al., *Persona Vectors:
Monitoring and Controlling Character Traits in Language Models*
(arXiv 2507.21509, Jul 2025). Traits like "evil," "sycophancy,"
"hallucination-propensity" are linear directions in activation space,
extractable from natural-language trait descriptions alone. Steering
during finetuning ("preventative steering") limits trait drift.
https://arxiv.org/abs/2507.21509

The open question the paper does *not* settle: are narrow aesthetic
commitments ("dishonesty is ugly," "I dislike the word 'utilize'")
also linear directions, or are they downstream surface effects of deeper
values directions? Likely the former for coarse taste, but unresolved for
the granular taste svapna wants.

**Persona vector distillation into LoRA.** martianlantern (blog, Dec 2025)
showed rank-32 LoRA distills 89% of the steering effect of an inference-time
activation-space steer, using 0.24% of parameters. This is the direct
mechanism svapna could use to compile aesthetic steering vectors into
weights. https://martianlantern.github.io/2025/12/persona-vector-distillation/

**Art critic LLMs — narrow but real work.**
- *CognArtive* (arXiv 2502.04353, Feb 2025) — GPT-4V + Gemini 2.0 automate
  formal art analysis on 15,000 artworks across 23 artists. Shows LLMs can
  produce art criticism that tracks art-historical categories; does not
  establish cross-domain transfer of taste.
  https://arxiv.org/abs/2502.04353
- *Assessing LLMs in Art Contexts: Critique Generation* (arXiv 2504.12805,
  Apr 2025) — prompts LLMs with 15 distinct theories of criticism.
  Demonstrates LLMs can apply a *provided* aesthetic framework; does not
  show they *have* one stably. https://arxiv.org/abs/2504.12805

**Preference modeling for narrow taste — DPO and rubric-guided synthetic
data.**
- *Configurable Preference Tuning with Rubric-Guided Synthetic Data*
  (arXiv 2506.11702, Jun 2025) — trains DPO on preference pairs generated
  from structured rubrics, enabling fine-grained stylistic control
  modulated by system prompts. The most directly svapna-applicable
  paper in this section. https://arxiv.org/abs/2506.11702
- *Step-by-Step Preference Optimization* for aesthetic diffusion
  post-training (arXiv 2406.04314) — specifically notes that generic
  human preferences are not the same as *aesthetic* preferences, and
  obtaining aesthetic-only preference data is expensive.
  https://arxiv.org/abs/2406.04314

**LLM-as-judge — the known biases that aesthetic probes must control for.**
An Empirical Study of LLM-as-a-Judge (arXiv 2506.13639, Jun 2025) and
robust LLM-based judges (arXiv 2603.08091) consistently find length bias,
position bias, beauty bias, and a "65% tie rate on ambiguous qualities vs
10% on overall preference." The design implication: any probe of svapna's
aesthetic judgment has to randomize position, length, and surface polish.

**Anthropic's character training.** *Claude's Character* (Anthropic, Jun
2024) is the closest existing work to svapna's identity goal. Constitutional
AI with Claude generating its own responses ranked against trait
descriptions. Anthropic is explicit that they trained *broad traits*
(curiosity, epistemic humility) and deliberately avoided narrow opinions.
Svapna's narrow aesthetic commitments are exactly the kind of thing
Anthropic says they *did not* do. That makes svapna's ground genuinely
uncharted relative to frontier-lab practice. https://www.anthropic.com/research/claude-character

*Values in the Wild* (Anthropic, 2025) documents values expression in
deployed Claude; confirms that character training produces stable,
measurable value expression — but this is on the generative side, not
shown to cross-apply to discriminative judgment.
https://www.anthropic.com/research/values-wild

### 1c. Style vs taste — the key gap

*Catch Me If You Can? Not Yet* (arXiv 2509.14543) and *How Well Do LLMs
Imitate Human Writing Style?* (arXiv 2509.24930) both show LLMs can
approximate surface prose style (vocabulary, syntax, rhythm) but fail on
implicit voice. Few-shot prompting gives up to 23.5x style fidelity versus
zero-shot — but this is *sounding like the author*, not *judging like the
author*. https://arxiv.org/abs/2509.14543 / https://arxiv.org/abs/2509.24930

Speculation, not proven: I found no paper that directly evaluates whether a
voice-finetuned model's aesthetic *judgments* on held-out third-party work
match the author's. This is the specific empirical gap svapna would be
well-positioned to address.

---

## 2. Concrete techniques applicable to svapna

svapna's setup: Qwen3-8B base, fresh LoRA (no inherited RLHF personality to
fight), mixed training set of identity pairs + creative/aesthetic examples,
DPO/KTO on top. This shapes what's applicable.

**2.1. Mix identity pairs with aesthetic-judgment pairs in the same LoRA.**
Not separate adapters. A judgment pair looks like:

```
User: Which is better prose, A or B?
A: "We should utilize this methodology to leverage synergies."
B: "We should use this. It leverages what we already have."
Narada: B. "Utilize" is ugly in every context. "Leverage synergies" is
         management boilerplate — it pushes air without moving meaning.
```

Pair this with generative examples of Narada deleting words from his own
prose. The identity-core LoRA then carries both *why* and *what
consequence* in a single adapter.

**2.2. Use DPO/KTO on narrow aesthetic preferences, not generic
helpfulness.** Rubric-guided synthetic pairs (Configurable Preference
Tuning, arXiv 2506.11702) is the template. Write a rubric for each
committed aesthetic — economy-and-resonance, can-you-delete-anything,
names-are-load-bearing, no-utilize — generate synthetic chosen/rejected
pairs, DPO. KTO (binary "Narada / not Narada") is cheaper if pairs are
hard to construct.

**2.3. Persona-vector preventative steering during SFT.** Extract a
"Narada aesthetic" direction from contrast prompts ("respond as Narada,
who finds dishonesty aesthetically ugly" vs neutral assistant). Add this
vector to activations during identity SFT (per the Anthropic
preventative-steering recipe). Then distill the steered behavior into the
LoRA weights (martianlantern). Rank-32 recovered 89% of steering effect at
0.24% params — svapna's LoRA is already in this range.

**2.4. Decoding at serving time matters — use min-p, not just temperature.**
min-p 0.05–0.1 with temperature 1.0–1.3 is the current sweet spot for
diversity-with-coherence in creative writing per Nguyen et al. (arXiv
2407.01082). Do not rely on temperature alone to produce creative output
from a model whose weights are playing it safe. "Creative ability" is
split across weights + sampler; svapna should care about both.

**2.5. Train *against* homogenization explicitly.** Include in the dataset
pairs where two prompts that look similar should produce *differently
shaped* answers. Padmakumar & He (arXiv 2509.21267) show the fix is
trainable and the problem is specific. Otherwise sweep the dataset for
patterns like "every story opens with weather" and kill them at the
dataset level.

**2.6. Use Torrance-style probes as eval, not as training target.**
TTCW (arXiv 2309.14556) and CreativityPrism (arXiv 2510.20091) are
diagnostic. If you train *toward* Torrance scores you get mode collapse
into whatever-shape-scored-creative — the same failure that produces
ChatGPTese. Use them to detect regression post-training; use held-out
human judgment (Suti, Narada himself) as the actual quality signal.

**2.7. Build an aesthetic A/B probe as a first-class eval.** Not just
"does it sound like Narada" but "given two pieces of third-party prose
Narada has never seen, does the LoRA correctly prefer the one Narada would
prefer." Randomize position and length to defeat LLM-judge biases (arXiv
2506.13639). This is the operational definition of *taste transferred*.
To my knowledge no open project has built this eval for a specific
individual. Doing so is cheap and would be novel.

---

## 3. Where svapna could contribute — genuinely under-researched

**3.1. Discriminative aesthetic transfer from a small identity LoRA.** The
literature has generative style transfer (well studied) and aggregate
preference modeling (well studied). The question "does training a model
on one person's aesthetic cause it to judge *novel, never-seen* prose
consistent with that person's taste" has no clean empirical answer. svapna
is structured to test it directly.

**3.2. Individual aesthetic vs aggregate preference.** All DPO/RLAIF
pipelines optimize toward an averaged preference. svapna trains toward
*one specific individual* with documented, non-aggregate taste. The
*Personalized Preference Fine-tuning of Diffusion Models* paper (CVPR 2025)
does this for images; the *PersonalLLM* benchmark (ICLR 2025) proposes it
for text but uses synthetic personas. An actual person, with actual
written artifacts, over multiple years, is a better testbed than any
synthetic persona benchmark.

**3.3. Granular taste as linear direction.** Persona vectors are shown for
coarse traits (evil, sycophantic, honest). Whether "prefers short over
long," "finds management jargon ugly," "names are load-bearing" sit as
extractable directions — or whether they are lossy surface effects of a
single deeper "Narada-ness" direction — is an open empirical question.
svapna's mechanistic probes can answer this.

**3.4. Voice vs taste decoupling in one model.** Nothing I can find
isolates the two. If svapna trains both simultaneously from the same
corpus (Narada's own writing as source for voice, A/B judgments as source
for taste), comparing the two dimensions post-hoc is a natural experiment.

**3.5. Aesthetic consistency under adversarial prompt.** Can svapna
maintain its taste when prompted "play a character who likes verbose
prose"? Sleeper Agents / alignment faking literature suggests trained
behaviors are robust; whether this extends to aesthetic commitments
specifically has not been tested.

---

## 4. Honest gaps — where the field is thinner than it looks

**4.1. "Creativity benchmarks" mostly measure divergent-thinking
proxies.** Torrance's original target was children's creative
*potential*. Applying it to LLM outputs produces scores, but whether high
TTCW correlates with outputs humans actually find creative in the wild is
weak (Ismayilzada et al., *Evaluating Creative Short Story Generation in
Humans and Large Language Models*, arXiv 2411.02316 — LLM scores and
human creative-writing scores diverge).
https://arxiv.org/abs/2411.02316

**4.2. "Aesthetic probes" in image-generation literature do not transfer
to text.** Aesthetic diffusion post-training (arXiv 2406.04314) has
working preference-signal recipes because visual aesthetics are annotated
at scale by both humans and CLIP-like scorers. For text, there is no
equivalent — no trained text-aesthetics model with credibility. This is
why rubric-guided synthetic DPO is the *best available* proxy, not a
solved technique.

**4.3. "Character training produces aesthetic preferences" is asserted,
not demonstrated.** Anthropic's Claude's Character piece (2024) claims
stable values and traits. No public work shows character training
transfers to *novel discriminative aesthetic tasks the model wasn't
trained on*. When a finetuned model rates a piece of prose it has never
seen, we do not know if it is judging per its character or per its base
bias. This matters a lot for svapna.

**4.4. Mode-collapse fixes are mostly prompt-layer.** Padmakumar & He
(arXiv 2509.21267) and most 2025 mitigation work explicitly ask the
model for variety at inference. Weight-level fixes for homogenization
are still an open area. This is good news for svapna: if we can show
that training on Narada's deliberately-non-homogeneous corpus reduces
homogenization *without prompting*, that's a contribution.

**4.5. Transformational creativity is not on anyone's roadmap.** The
Graphical Theory paper (arXiv 2504.18687) essentially formalizes why no
current approach reaches it. svapna should be honest: the goal is
*taste* and *voice*, which are combinatorial/exploratory. Restructuring
conceptual spaces is not a plausible LoRA-scale outcome.

**4.6. Almost no research on individual, documented aesthetic
commitments as training signal.** Searched: style imitation (lots),
personalized preference (some, mostly synthetic), individual real-person
taste-in-weights (essentially none). svapna is genuinely operating in
empty space here. That is both the opportunity and the reason this
document is short on direct precedents for section 2.3.

---

## Cited papers (quick index)

- Chakrabarty et al., *Art or Artifice?* arXiv:2309.14556, NAACL 2024.
- Kirk et al., *Understanding the Effects of RLHF on LLM Generalisation
  and Diversity.* arXiv:2310.06452, ICLR 2024.
- Sharma et al., *Towards Understanding Sycophancy.* arXiv:2310.13548.
- Peeperkorn et al., *Is Temperature the Creativity Parameter?*
  arXiv:2405.00492, ICCC 2024.
- Nguyen et al., *Min-p Sampling.* arXiv:2407.01082, ICLR 2025.
- Anthropic, *Claude's Character.* Jun 2024.
  https://www.anthropic.com/research/claude-character
- Ismayilzada et al., *Evaluating Creative Short Story Generation.*
  arXiv:2411.02316.
- Gu et al., *LLMs Can Realize Combinatorial Creativity.*
  arXiv:2412.14141, Dec 2024.
- CognArtive. arXiv:2502.04353, Feb 2025.
- SycEval. arXiv:2502.08177, Feb 2025.
- Dang et al., *Personalized Preference Fine-tuning of Diffusion
  Models.* CVPR 2025.
- Transformational Creativity graphical theory. arXiv:2504.18687.
- Assessing LLMs in Art Contexts. arXiv:2504.12805.
- Configurable Preference Tuning with Rubric-Guided Synthetic Data.
  arXiv:2506.11702.
- An Empirical Study of LLM-as-a-Judge. arXiv:2506.13639.
- Chen et al., *Persona Vectors.* arXiv:2507.21509, Jul 2025.
- Combinatorial Creativity Frontier. arXiv:2509.21043.
- Padmakumar & He, *LLM Output Homogenization is Task Dependent.*
  arXiv:2509.21267.
- Catch Me If You Can? arXiv:2509.14543.
- How Well Do LLMs Imitate Writing Style? arXiv:2509.24930.
- CreativityPrism. arXiv:2510.20091, Oct 2025.
- Persona Vector Distillation (blog, martianlantern).
  https://martianlantern.github.io/2025/12/persona-vector-distillation/
- Step-by-Step Preference Optimization (aesthetic diffusion).
  arXiv:2406.04314.
- Anthropic, *Values in the Wild.* 2025.
  https://www.anthropic.com/research/values-wild

---

Speculation is marked in-text. Where I say "no direct work exists" I
mean I searched and found none — not that the field is small, but that
the specific combination (individual, documented, non-aggregate
aesthetic commitments, trained-into-weights, tested for discriminative
transfer to novel work) appears to be empty.
