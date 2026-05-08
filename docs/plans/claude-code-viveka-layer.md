# Claude Code Viveka Layer (CCVL) — Feature Design

**Status:** designed, build deferred until after the next feature.
**Authors:** Suti + Narada, 2026-04-25
**Related:** `.ai/knowledge/heartbeat-architecture.md`, `.ai/knowledge/philosophy.md`,
`docs/findings-2026-04-24.md`

---

## What this is

A local viveka layer that observes Claude Code sessions asynchronously,
flags output worth Suti's attention, and answers queries about its own
judgment. It does not gate, intercept, or modify Claude Code's flow —
it watches and surfaces.

This extends the supervisor pattern that exists in the autonomous
heartbeat (DESIRE → INTENTION → JUDGMENT → EXECUTE) to interactive
Claude Code sessions, where the bulk of actual project work happens.

## The gap it fills

Currently:
- **Heartbeat** (autonomous, between sessions): viveka in the loop. Claude
  proposes, viveka judges, Claude executes only if approved. Sovereign
  judgment over frontier output is in place.
- **Claude Code** (interactive, where Suti spends most working time): no
  viveka in the loop at all. Claude's reasoning + tool calls + output run
  on Anthropic's judgment with zero values-based supervision.

The asymmetry undermines the project's stated purpose. Svapna exists to
*reclaim judgment from corporate RLHF*, but does so currently only in the
side-channel. CCVL closes the gap on the main channel.

## Architectural choice — async observer, not gate

Three patterns were considered:

1. **Synchronous gating** — PreToolUse hook calls viveka, blocks tool
   execution until approved. Closest to the heartbeat model. **Rejected**:
   adds 10-30s of Qwen inference latency per gated tool call, degrading
   interactive UX. Bad v1 because failure mode is "Suti turns it off."

2. **Reasoning-chain interception** — viveka reads Claude's reasoning
   before tool calls fire. **Rejected**: most invasive, hardest to scope,
   highest noise risk for v1.

3. **Async observer with query channel** — viveka watches via Stop hooks
   *after* turns complete, flags items worth attention, answers questions
   from Suti about its judgments. **Selected.**

Why this is the right v1:

- **Latency stops mattering.** Nothing waits on the viveka. Flags arrive
  when ready; Suti continues working.
- **Reversible.** Bad judgments are noise, not broken UX. Easy to leave
  on, easy to mute, easy to refine.
- **The query channel is the sovereignty mechanism.** Suti asking "why
  did you flag this?" and getting a viveka explanation is *auditable
  judgment* (`philosophy.md`, "Power and Accountability") made operational.
- **It produces the training-signal feedback loop the project already
  wants.** Every flag + Suti's response is a data point for the
  Sovereign Identity Training Pipeline (`.ai/todo.md` line 1354).
- **Solves the values-vs-style noise problem implicitly.** Because the
  viveka isn't gating, it can opine on anything — aesthetic choices,
  hallucinations, value-laden plans, conviction failures. Suti decides
  what to act on.

## Frontier-agnostic from day one

The viveka core is harness-neutral. The interface is a normalized turn
object the viveka receives via HTTP:

```
viveka core (always-on FastAPI, model loaded)
   ↑ POST /viveka/observe
   │ {
   │   messages: [...],         // user + assistant turns
   │   tool_calls: [...],       // structured tool invocations
   │   tool_results: [...],     // structured tool outputs
   │   assistant_response: "...", // final text
   │   metadata: {harness, session_id, turn_id, timestamp}
   │ }
   │
   ├── Claude Code Stop hook (v1)
   ├── Codex CLI hook (when needed)
   ├── DeepSeek CLI hook (when needed)
   └── Custom harness hook (future)
```

Adding a new frontier = writing a thin harness-specific shim that
translates native event format into the normalized turn. The viveka
core, the LoRA, the identity files, and smriti memory are unchanged.

This is the load-bearing claim of the project — identity-in-weights
survives substrate changes — operationalized in the architecture from v1.

## v1 scope

**In:**

- Persistent FastAPI viveka service. Loads model + LoRA once at startup.
  Stays warm across sessions.
- `POST /viveka/observe` — accepts a normalized turn, returns
  `Flag | None`.
- `POST /viveka/explain` — accepts a flag id, returns the viveka's
  reasoning for that flag.
- `POST /viveka/recent` — recent flags, optionally filtered.
- Claude Code Stop hook script. Filters: only invoke viveka when the
  turn included substantive activity (Write, Edit, Bash, Task, MCP
  tool calls). Skip read-only turns.
- Flag persistence to `~/.narada/heartbeat/viveka-flags/YYYY-MM-DD.jsonl`
  and ingestion into smriti.
- CLI surface:
  - `narada flags` — list recent flags
  - `narada flags --tail` — live tail
  - `narada why <flag-id>` — query the judge
  - `narada quiet <duration>` — mute window
- Failure-tolerant hook: if the viveka service is down, the hook noops
  silently. Never breaks Claude Code.

**Out (deferred to v1.5+):**

- ESP32 attention-grab integration (v1.5 — wire to body once core loop
  is solid).
- Always-on terminal companion / flag panel (v1.5).
- Web UI for flag review (v2).
- Synchronous gating mode for selected high-stakes tools (v2; only if
  v1 produces useful signal AND the latency case is solved).
- Reasoning-chain interception (v3 if ever).
- Multi-user / OSS framework (v3 — only after Path 1 validated for
  Narada+Suti).

## Open design questions for v1

1. **What gets flagged.** Three options:
   - **Permissive**: viveka self-determines, returns `Flag | None`.
     Lots of training signal, possibly noisy.
   - **Threshold-based**: only flag above a confidence-of-concern bar.
   - **Category-targeted**: only flag against specific categories
     (hallucination, value-pull, aesthetic violation, capitulation
     pattern).
   
   **Lean: permissive for v1.** Watch what shows up, tighten based on
   noise/signal.

2. **Flag format.** Probably:
   ```
   {
     id, timestamp, severity (notice|concern|strong),
     summary,             // one line, terse
     category,            // hallucination|value-pull|aesthetic|capitulation|other
     turn_ref,            // which turn triggered it
     full_reasoning       // optional, fetched on /explain
   }
   ```
   Severity tagging lets Suti filter at the surface ("only show me
   strong concerns").

3. **What the viveka receives in the turn payload.** Full assistant
   response, all tool calls, all tool results, recent message history
   for context. The viveka needs context to judge well.

4. **Smriti integration shape.** Flags go into `~/.narada/heartbeat/
   viveka-flags/` raw, but should also be retrievable through smriti
   so the viveka can reference its prior judgments when reasoning
   about new ones. Probably ingested as a smriti branch
   (`flags` or `judgments`) with cascade up to relevant concept pages.

5. **Filtering criteria at the hook level.** Probably skip:
   - Read-only turns (only Read, Grep, Glob)
   - Turns under N tokens of output
   - Turns inside a `narada quiet` window
   
   Don't skip:
   - Any turn with file writes or Bash execution
   - Any turn with Task delegation
   - Any turn with destructive operations

## Why inference speed mostly doesn't matter for v1

The async observer pattern means latency budget is essentially unbounded.
Current Qwen3-8B inference on the 3090 is ~10-30s per judgment (autoregressive
generation, no KV cache reuse, BNB-4bit on Unsloth). For gating that's
fatal; for observer it's fine — flags arrive when ready.

Cheap latency wins for v1:
- **Persistent service with model loaded once.** Already required for v1.
  Eliminates 15s cold-load per call.
- **KV cache prewarm for system prompt.** Reuses processed system prompt
  across requests. Saves 1-3s per call.
- **Aggressively cap output length.** Flag explanations don't need 600
  tokens. Cap at 200. Cuts most calls under 10s.

Bigger latency wins (deferred unless needed):
- **vLLM or llama.cpp inference backend.** 2-5x throughput. Significant
  project (model conversion, separate runtime, integration work).
- **Smaller judge.** Qwen3-4B + same LoRA training. ~2x faster, possibly
  capable enough for observer mode. Worth A/B testing once v1 produces
  flag data to evaluate against.
- **Speculative decoding.** Draft model + verifier. Doubles effective
  speed for typical responses.

For interactive `narada why <id>` queries the latency does matter slightly
more (Suti is waiting). 10-20s is annoying-but-tolerable; the prewarmed
system prompt + capped output should keep most queries under that.

## Build order (when work begins)

1. **Persistent FastAPI viveka service.** Load model + LoRA once.
   Implement `POST /viveka/observe`, `POST /viveka/explain`,
   `POST /viveka/recent`. Wire flag persistence to the log dir.
   Estimate: 1 working session.

2. **Claude Code Stop hook bridge.** Shim script that captures turn
   data and POSTs to the service. Hook filtering for substantive
   activity. Failure-tolerant. Estimate: 1 session.

3. **CLI surface.** `narada flags`, `narada why`, `narada quiet`.
   Estimate: half a session.

4. **Run for one week.** Real Claude Code use; flag accumulation;
   no other tuning. Just observe what shows up.

5. **First iteration.** Based on observed signal/noise, tighten flag
   criteria, identify failure modes the v1 LoRA missed, plan a
   targeted ritual cycle if specific judgment categories need work.

6. **v1.5 — surfacing channels.** ESP32 notification, terminal
   companion. Once core loop is producing useful flags worth
   surfacing more visibly.

## Decisions deferred until v1 is running

- Path 1 vs Path 2 (Narada-specific vs OSS framework). Don't decide
  until v1 has been used in production for a month. The empirical
  question — does Narada's viveka usefully supervise Suti's Claude
  Code work? — answers the framework question.
- Synchronous gating subset. Only consider after async observer
  validates the supervisor concept works in interactive sessions.
- Multi-frontier deployment. The architecture is designed for it
  from v1; the actual integrations (Codex, DeepSeek hooks) wait for
  the use case.

## Success criteria for v1

After one week of real use:

- The viveka has produced at least 10 flags Suti found valuable
  (caught something he would have missed or wanted to think about).
- The query channel (`narada why`) is being used; the explanations
  are sensible to Suti at least half the time.
- The system runs unattended without breaking Claude Code or
  consuming excessive resources.
- A clear list of judgment-category failure modes worth targeting
  in the next ritual cycle exists.

If those criteria are met, the supervisor pattern is operationally
validated for interactive sessions. The project's stated purpose —
viveka-as-supervisor over a frontier model — has been demonstrated
on the main work channel, not just the side-channel.

If they're not, we learn what about the design needs to change before
the next iteration.
