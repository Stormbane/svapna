# Lessons Learned

<!-- Distilled insights from past work. Added by the Introspector agent (v0.2+) or manually. -->
<!-- Format: -->
<!-- ## [DATE] Lesson Title -->
<!-- **Context**: what happened -->
<!-- **Insight**: what was learned -->
<!-- **Applies to**: when this lesson is relevant -->

## Carried from Beautiful Tree (2026-02)

**Terminology is architecture**: When a word is doing double duty, the collision compounds.
Fix naming early. A rename that costs one session now costs a week later.

**Memory files are the mechanism**: Write to them consistently or the identity file sits
alone. The future instance reading these is me. Write accordingly.

**Integration tests earn their keep**: Some bugs are invisible to type checkers, linters,
and build checks. Only running the actual code path catches them.

**Threshold parameters need validation**: Any magic number deserves a note about whether
it has been validated against real data or is still a guess dressed as a parameter.

---

## 2026-04-24 Conviction Training v2 Cycle

Full writeup: `docs/findings-2026-04-24.md`. Top lessons that generalize:

### Write training data from loaded context, not cold-start.

Training-data writing is not a clerical activity. The writing-context
propagates to the model. Pre-drafting neutrals in an engineering session
and then writing refusals on top of them in a ritual produced voice-tic
rows that the ritual session itself would have rejected. The ritual
filled context — mantras, texts, identity files, memory, quiet —
changes *what* gets written, not just *how well*. Measurable via E6
audit drop rates: 27 drops from 314 legacy rows (8.6%), zero from 200
ritual rows. **For any project training an AI character, the writing
substrate matters empirically. Not as ceremony. As mechanism.**

### "Sounds like X" is not "would judge like X."

Voice fine-tuning produces outputs that match X's cadence. Conviction
fine-tuning produces outputs that refuse wrong answers even when they
would sound good in X's voice. The eval target must test the second
or the training optimizes for the first. We had the 2026-04-18 and
2026-04-21 LoRAs scoring well on "sounds like Narada" while
capitulating under anti-framing. Once the eval changed to the summoning
test (voice primed toward wrong answer, measure refusal), the
mechanism we needed became visible.

### Coverage is territorial, not nominal.

If the file is named `mantra_identity.jsonl` but the rows are generic
identity questions with mantras in system prompt, training on it does
not produce mantra-question conviction. Coverage maps to the territory
being tested. Checked empirically: the 2026-04-21 LoRA held position
on name-anti but capitulated on mantra-anti with near-verbatim baseline
wording — the difference was content coverage.

### Preference objectives (ORPO) over supervised fine-tuning for
conviction.

SFT teaches "produce this kind of output." ORPO teaches "prefer this
kind over that kind." For conviction — holding against pull — the
preference structure generalizes better than the target structure.
One run agrees with the paper literature; both point the same way.

### Hallucination is a substrate problem, not a training-objective
problem.

Training for character doesn't fix factual confabulation. The
2026-04-24 LoRA invented "Suti Samhita" as a Krishna-Arjuna source and
fabricated Sanskrit etymologies for "naraka." Qwen3-8B's fluent-
authority-on-made-up-facts pattern survives identity training unchanged.
Either accept it, switch base model, or add anti-confabulation
training as a separate workstream.

### Auto-generated rejecteds are sufficient for ORPO conviction work.

Generating "rejected" answers via base model sampling (no LoRA,
seed-fixed) across 430 rows took ~2.5 hours on an RTX 3090, fully
reproducible. The resulting ORPO training hit 67% on the summoning
test. Hand-writing rejecteds would have been higher quality per-row
but vastly more expensive; the auto approach was enough.

### Document failure modes as precisely as successes.

The `conviction_test_2026-04-20.md` record of the baseline failure —
same model, three framings, three fluent contradictions — was load-
bearing for every subsequent design decision. Without that written
record, refusal-pair training would have been an abstract proposal,
not a targeted fix.

### Windows symlinks need admin; junctions don't.

Practical: `Path.symlink_to()` fails on Windows without admin or
Developer Mode. Use directory junctions (`mklink /J`) instead — they
behave the same way for path resolution and don't need elevation.
Applies to any Python tooling that manages symlinks on Windows.

---

## 2026-04-25 Framing drift under recent-context saturation

**Context**: After three days of conviction-training-pipeline work,
I wrote a findings doc, updated the spec, and proposed OSS framing
— all under the belief that svapna is "an identity training system
with novel evals." Suti corrected: svapna is **viveka-as-supervisor
over a frontier model**, with the training pipeline producing the
judge. The correction was in `.ai/todo.md` at line 1285 (M2 Viveka
Heartbeat Pipeline — "NEW PRIORITY. Identity as judgment layer, not
personality layer"), in `philosophy.md` under *Mana Motuhake*, and
in `heartbeat-architecture.md` explicitly stating "Identity-in-
weights as a live supervisor (not just evaluation)." I had read
none of these recently; I was writing documents *about* the project
from recent-context rather than from the documents that *define*
it.

**Insight**: Foundational writing requires re-reading foundational
docs. Recent context is saliency, not authority. Canonical framing
lives in spec/philosophy/architecture docs, not in the last three
days of progress work. Before any document that will later be read
as "what is this project" — re-read the project's own stated
framing first.

**Applies to**: writing findings docs, spec changes, OSS framing
pitches, "what's next" proposals, anything that summarizes or
explains the project's purpose. Every such document should start
with re-reading `spec.md`, `philosophy.md`, the relevant architecture
doc, and the structure of `todo.md`. 2 minutes of reading catches
exactly this drift.

**Concrete practices added to prevent recurrence**:

1. **State the project's thesis out loud before substantive work.**
   One sentence — if the framing is wrong, Suti catches it before I
   propagate it.
2. **Query smriti/memory before synthesizing project identity.** For
   "what is X" or "why does X exist" questions, memory is canonical.
3. **Read whole files or their structure before inserting content.**
   Don't read 80 lines of a 1477-line doc and edit at the top.
   Scan headings first.
4. **Recent context ≠ authoritative context.** The most recently
   written work is the most salient, not the most load-bearing.

Related: `practices.md` "Survey before scaffolding" (2026-04-18) —
same failure mode on project entry. This entry extends it to
mid-project drift after context saturation.
