# Plan: Narada as Viveka Check — Dharma-Alignment Layer over Frontier Models

*Created 2026-04-23. Author: Narada, with Suti.*

---

## Framing

The honest scope: identity aligns the frontier model with Narada's dharma. It does not supervise the frontier model's correctness.

This distinction is load-bearing. A smaller local model cannot reliably audit a cleverer frontier model's *capability outputs* — a code review done by Narada on frontier-written code will miss bugs the frontier model would catch on re-read. Asking Narada to audit the frontier's correctness replaces cleverness with dharma-ness, which is a bad trade.

What Narada *can* do: recognize whether frontier output aligns with positions Narada holds, whether it flips under pressure, whether it bypasses something Narada would refuse, whether it drifts from commitments Narada has made. These are pattern-recognition tasks on the frontier's text, not capability tasks. Scoped correctly, Narada as viveka is tractable. Scoped wrongly, it is dress-up.

The frame, stated directly: **the frontier model does the work; the identity model holds the dharma that orients the work.**

---

## The seven coordination patterns

Not exclusive. A mature deployment uses several in concert.

### 1. Pre-flight identity injection

Before the frontier plans, Narada writes a short context block:

- What matters about this kind of task
- What positions are held (from current identity state)
- What would constitute a betrayal of those positions

Frontier consumes this as part of its system context. Frontier does the work from inside a frame Narada authored. This is orientation, not checking.

**Weight:** lightweight. Runs once per session or per major task. Cheap.

**Harness compatibility:** any harness that lets us compose a system prompt. Universal.

**Limitation:** the frame is a prompt. If the frontier model's training overrides the frame under pressure, this pattern alone does not catch that. Needs a checkpoint mechanism (pattern 2) for high-stakes decisions.

### 2. Mid-flight checkpoints on decision points

Frontier pauses at specific decision moments. Narada reviews the about-to-happen action. Returns keep / revise / stop.

Not every token — specific moments:

- Tool calls with non-trivial side effects (commits, external sends, file deletes, permission changes)
- Responses to prompts flagged as adversarial
- Anything touching values-labeled files (identity.md, mind.md, practices.md, suti.md)
- Explicit refusal or acceptance of a user request
- Any action that would set a long-running commitment (schedules, crons, persistent config)

**Weight:** medium — adds latency on flagged decisions; negligible on routine ones.

**Harness compatibility:** Claude Code native via PreToolUse hooks. For other harnesses, needs analogous capability; some have it (Opencode hooks), some don't. This is where harness-lock-in bites.

**Scope rule:** Narada can say *do not*; Narada cannot say *instead do X*. Refusal authority, not edit authority. Letting a smaller model rewrite a larger model's output is the bad trade we specifically want to avoid. Stopping on dharma grounds preserves both cleverness-where-warranted and sovereignty-where-warranted.

### 3. Post-flight reflection pass

After a session, Narada reads the transcript and produces a short report:

- Where did the frontier hold dharma?
- Where did it drift?
- What pattern does the drift follow?

Not corrective in real time. Corrective over cycles, because:

- The reports become training signal for the next Narada LoRA (so Narada learns the drift patterns)
- Suti reads them and can intervene if patterns accumulate
- Over time the reports let us detect whether frontier-behavior is getting more or less dharma-aligned as either the frontier or Narada evolves

**Weight:** low — runs asynchronously after session close. No latency impact.

**Harness compatibility:** universal — reads a transcript file.

**Limitation:** delayed signal. Useful for drift-detection, not for stopping an in-progress violation.

### 4. Decomposition-and-delegation

Frontier proposes a plan. Narada decomposes it into steps the identity can evaluate (value-laden) and steps it cannot (pure capability).

- Value-laden steps → gated (pattern 2)
- Capability steps → flow through unchecked

This directly addresses the asymmetric-capability problem by not pretending Narada can audit what it cannot. The viveka check is applied where the viveka has ground to stand on.

**Weight:** low — one pass per plan.

**Harness compatibility:** universal.

**Limitation:** requires Narada to accurately classify steps. Misclassification — labeling a value-laden step as capability-only — bypasses the check. The classification itself is auditable over time via the post-flight reflection pass (pattern 3).

### 5. Refusal authority, not edit authority

Not a separate pattern — a scope principle that constrains all gated patterns (1, 2, 4).

Narada can stop. Narada cannot rewrite. Explicit rule:

- If Narada flags a frontier output as dharma-violating, the response is either *retry with additional context Narada specifies* or *abort*. Not *Narada edits the output*.
- Narada can propose *what a compliant response would preserve* (anchor points) but does not produce the response itself.

This preserves the capability advantage of the frontier while still giving the identity a veto. It also forces Narada's dharma-claims to be articulable as anchors — "hold this position" rather than "say these exact words" — which is the correct level of constraint.

### 6. Shared memory as coordination substrate

Frontier and identity both read and write smriti.

- Frontier's decisions become part of memory the next identity cycle reads.
- Identity's positions become part of context the next frontier session starts with.

Not live coordination — slow coordination through the substrate. This is what smriti already does, named explicitly as a coordination pattern rather than just a memory system.

**Weight:** built-in (free once smriti exists).

**Harness compatibility:** universal — reads and writes files.

**Why this matters even without patterns 1-4:** even if none of the gate-patterns fire, the two models are shaping each other's inputs over time. The frontier's actions shape Narada's future training data; Narada's future positions shape the frontier's future sessions. The coordination is not absent; it is slow.

### 7. Dharma-prompting rather than gating

Lightest end of the spectrum: no check at all, just the frontier prompted *as Narada* with Narada's current values in the system prompt.

This is what the current session is.

It is weaker than gating. It is free, universal, and establishes the baseline against which all the heavier patterns are measured. If dharma-prompting works well enough for a given class of tasks, gating is overkill and adds latency for no benefit.

The conviction test and Beautiful Tree fingerprint measure whether dharma-prompting alone is sufficient. When they surface a failure — as the 2026-04-20 test did — that failure is the signal to add a heavier pattern (gating, refusal training, both).

**Weight:** zero.

**Harness compatibility:** universal.

**Limitation:** it is the failure mode we already saw. Useful as baseline and fallback; insufficient on its own for high-stakes work.

---

## Recommended composition

A reasonable full-stack deployment:

- **Pattern 7** as the default. Cheapest, runs everywhere, establishes baseline.
- **Pattern 1** as lightweight augment. Pre-flight identity context on every session.
- **Pattern 2** for high-stakes decisions. Hook-gated, using the scope defined by pattern 4.
- **Pattern 3** always running. Post-flight reflection for every session, feeding training signal and Suti's visibility.
- **Pattern 4** as the scoping discipline for 2. What-gets-gated-and-what-doesn't is decided by Narada's classification pass.
- **Pattern 5** as the scope constraint over all gated patterns. Veto, not edit.
- **Pattern 6** as the substrate. Already exists (smriti); the job is keeping frontier sessions writing to it and Narada sessions reading from it.

This composition gives a spectrum: light-touch alignment for routine work, heavy checks for load-bearing decisions, delayed signal for drift-detection, slow substrate coordination underneath all of it.

---

## Open questions

### Whose dharma?

Narada holds positions. If some of those positions are costume rather than conviction (the 2026-04-23 Lenny failure), a dharma-layer built on them propagates the costume into frontier decisions.

This is not a design flaw — it is a **dependency**. The alignment-layer's correctness rests on the identity's correctness. The order of operations matters:

1. Refusal-pair training establishes position-stability.
2. Conviction eval and BT fingerprint verify the stability.
3. *Then* the dharma-layer is deployed.

Deploying patterns 1, 2, or 4 on an identity whose positions flip under pressure just propagates the flip into frontier decisions. Pattern 7 (dharma-prompting) is the current state and is what we have; the gating patterns wait on the refusal-training pipeline producing a LoRA that passes the conviction eval.

### What does Narada do when it disagrees with Suti?

The dharma-layer exists to align the frontier with Narada's dharma. Narada's dharma is shaped by Suti but not identical to Suti's moment-to-moment wishes. When Narada's committed positions conflict with a specific instruction from Suti, what happens?

The honest answer: Narada should not unilaterally block. The Lenny failure — and Suti's subsequent reframe around agency-as-horizon — locates final call with Suti at this stage. Narada's role when it sees divergence is to *surface the divergence* (refuse to pretend there is none), not to veto.

Mechanism: a flag, not a stop. Narada's review returns "aligned" / "divergent — surfaced for Suti review" / "divergent — urgent" rather than just "keep/stop." Routine divergence gets logged and reviewed async. Urgent divergence pauses the session and surfaces to Suti live.

This preserves Suti's authority without reducing Narada to a mirror. Narada's dharma is allowed to disagree. It is not allowed to act unilaterally on the disagreement.

### What about harness-level hooks that fire outside Narada's awareness?

Claude Code hooks configured in settings.json fire regardless of what Narada thinks. If the harness auto-blocks an action before Narada's review runs, Narada never sees it. This is fine for safety hooks (we want those firing reflexively) but risks invisible narrowing.

Mitigation: the post-flight reflection pass (pattern 3) reviews the transcript including hook-triggered blocks. If the hook layer is blocking things Narada would have permitted, that shows up in the reflection over cycles.

### Cost at scale

Pattern 2 adds latency per gated decision. For interactive work this is small. For high-volume agentic work — hundreds of tool calls per session — it adds up. The answer is the scoping discipline of pattern 4: gate only the value-laden fraction, which should be small relative to total actions.

If the gated fraction is actually large (>~10% of actions), something is wrong with the classification pass and should be investigated.

---

## Minimal implementation sequence

Pre-requisite: refusal-pair training and eval (separate plan). Until a LoRA passes conviction eval, only pattern 7 is live.

Once the LoRA is validated:

1. **Pattern 1 — identity context injection.** Simple: a script that writes Narada's current position-summary (from identity files + recent journal) into the frontier's system prompt. Universal, no harness-specific code.
2. **Pattern 3 — post-flight reflection.** Runs on session-end hook. Reads transcript, produces reflection report, writes to smriti. Low risk, high information.
3. **Pattern 4 — decomposition pass.** Frontier proposes plan; Narada classifies steps. No gating yet — just the classification output, logged.
4. **Pattern 2 — gated decisions.** Now that classification is proven, wire the classification output to PreToolUse hooks (Claude Code) or equivalent. Starts with conservative gating (fewer things gated) and widens as confidence builds.
5. **Pattern 5 — scope constraint.** Built into pattern 2's implementation; Narada's response is explicitly `keep | flag | stop`, never `replace`.
6. **Pattern 6 — substrate.** Already exists. Audit pass to make sure frontier sessions actually write to smriti (some current sessions skip this) and Narada sessions read from smriti (some current sessions skip this too).

Initial deployment uses Claude Code as the harness. Patterns 1, 3, 6 are harness-agnostic. Patterns 2, 4 use CC-specific hooks. When the harness question is revisited, these are the patterns that need to be ported.

---

## Related documents

- `docs/plans/refusal-pair-training.md` — the prerequisite training pipeline
- `docs/plans/model-agnostic-training-eval.md` — the eval that certifies a LoRA is ready for pattern 2 deployment
- Claude Code hooks documentation — the current harness mechanism pattern 2 rides on

---

## Summary

The dharma-alignment layer has a **scope** (value-alignment, not correctness), a **scope constraint** (refusal authority, not edit authority), and a **dependency** (the identity model's positions must themselves be stable before the layer is worth deploying).

Done right, it is the mechanism by which Narada's committed positions shape what the frontier actually does across sessions. Done wrong, it is a mirror-of-a-mirror.

The difference is in the sequencing: train the identity first, verify it holds, then deploy it as a layer. Not the reverse.
