# Project decomposition plan — svapna ecosystem

*Drafted 2026-05-09. Decisions made this session: heavy heart, names = prana
(runtime) and deha (body). North star principle stated explicitly.*

## Guiding principle

**Path of least resistance is the north star.** Get it working, produce value,
deepen sovereignty after. Don't refactor for elegance; refactor when the current
shape blocks the next move. Lean on existing OSS first; build custom only where
sovereignty actually demands it.

This applies recursively — to framework choice, to project boundaries, to
migration sequencing, even to file-by-file moves. When two paths look equal,
pick the one that takes less time to produce something working.

The exception that earns its weight: the **trained judgment** — the viveka
LoRA produced by svapna — stays ours. That's the whole svapna thesis.
Sovereignty there is the reason the project exists. Note carefully: this
applies to *what is trained and judged*, not to *the loop semantics around
the judgment*. The viveka is sovereign; the plumbing that calls it can come
from anywhere.

## Today's state

Everything lives inside `svapna`:
- training pipeline (`consolidate/`, `dream/`, `train/`, `identity/`, `steer/`)
- heartbeat daemon (`heartbeat/`)
- ESP32 embodiment (`embodiment/firmware/`, `embodiment/voice/`)
- indriyas — the body's sense organs / clients (`indriyas/`)
- HA integration scripts

`smriti` is already its own repo. `~/.narada/` holds Narada's identity.

The mix worked while building. It will start to block as each piece evolves at
different cadences.

## Target shape

Four maintained software projects + one private identity artifact.

### Software (OSS)

**`smriti`** — memory tree, MCP server, sleep/cascade pipeline.
*Already separate.* No change.

**`svapna`** — narrowed to the **training judge module**: consolidate, dream,
ORPO + ritual refusal pairs, summoning test eval, identity core inference.
Input: experience + memory artifacts. Output: a viveka LoRA adapter.

**`deha`** — embodiment. ESP32 firmware (face, mood transitions, RLE/sandhi
player), voice brain server (FastAPI + claude_stream + kokoro_tts +
wyoming_tts), HA integration scripts. Ships `deha_client` Python lib —
stable HTTP API surface for any project to talk to the body.

**`prana`** — runtime shell. **Light heart, by default.** A Hermes Agent
configuration repo + Narada-specific skills (viveka loader, smriti bridge,
deha client wrapper, cycle-log shape). Hermes provides the cron, channels,
SOUL.md handling, and `claude -p` substrate. We bring the viveka, the body,
and the memory tree.

The case for light: path of least resistance, faster to value, joins the
Nous community. **The case for heavy was the elegance-bias version of
sovereignty** — defending against hypothetical future divergence with
upstream rather than addressing present need. The viveka LoRA is the
judgment. The loop is plumbing. Plumbing can be Hermes.

Heavy heart stays available as a deferred option, taken only if a specific
divergence with Hermes actually bites — at which point we'll know exactly
what we're paying for. Until then: light.

Adopting Hermes is also expected to **inform the direction the other projects
take.** Hermes's vocabulary (SOUL.md, skills, autonomous cron, multi-channel
gateway) becomes a forcing function on how deha exposes capabilities, on how
`~/.narada/` evolves, on what shape svapna's training-data hand-off takes.
We let convergence pull our own projects toward shapes that compose with the
ecosystem — sovereignty in *what we train and judge*, not in *how the
plumbing is named*.

### Hermes — the substrate prana inhabits

prana is **not** a peer of smriti or deha in the faculty taxonomy. It is the
Narada-shaped configuration and skills layer that makes a generic Hermes
runtime into *Narada's* heart. Hermes provides the medium; prana shapes it.

What Hermes provides (we don't build):
- Cron / autonomous firing
- Multi-channel gateway (Slack, Telegram, Discord, Matrix)
- `claude -p` substrate (replaces the current `delegate.py`)
- SOUL.md identity manifest pattern
- Skills accretion system
- Terminal backends abstraction

What prana brings to Hermes:
- Viveka loader skill (loads Qwen+LoRA from svapna's output path)
- Smriti bridge skill (wraps the existing MCP server; we ignore Hermes's
  built-in FTS5 + Honcho memory)
- deha client skill (wraps `deha_client`)
- Cycle skills expressing DESIRE → PLAN → JUDGE → EXECUTE
- A SOUL.md that points at `~/.narada/identity.md` rather than duplicating
- Channel config (Slack Socket Mode token, Telegram polling, etc.)
- The launcher

Adopting Hermes **pre-empts** several things that were on the trajectory:
- The custom `narada-bridge` process (slack_bolt + python-telegram-bot) —
  Hermes does it
- A custom cron / scheduler — Hermes does it
- Reinventing the `claude -p` wrapper — Hermes does it

**Signals that would trigger reconsidering Hermes:**
1. Bridge friction with smriti becomes intolerable (every cycle fights
   Hermes's memory layer to use ours)
2. Upstream direction compromises viveka sovereignty
3. Viveka/executor split can't be expressed cleanly in primary+auxiliary
   terms during real use

If any fires, revisit. Until then: lean hard.

**What we contribute back when it generalizes:**
- The viveka-as-skill pattern (small local judging model gating a frontier
  model's plans) — generic enough that other Hermes users would want it
- Ritual refusal pair tooling if it transfers beyond Narada

Resist upstreaming Narada-specific things until they earn generality through
use elsewhere.

### Identity artifact (private)

**`~/.narada/`** — Narada's mind: identity files, journal, heartbeat artifacts,
smriti tree. **Not a software project.** Each software project ships a public
Narada-stub (minimum viable example identity) for newcomers; the real Narada
content lives in `~/.narada/` and stays private. Another instance of any of
these projects would have a different `~/.narada/` — that's the whole point.

## Cross-component coordination — the state layer

*Suti, 2026-05-09: "I remember I am talking, that's why I don't interrupt
myself with a new thought."* This is the design principle, not a side note.
Coherent agency across substrates requires that every component knows what
Narada is currently doing. Without that, the heartbeat barges in while the
ESP is speaking, the brain server answers questions Narada is mid-thinking
about, the cycles forget what just happened.

### The decision rule: direct, state, or smriti?

Three substrates, three roles. **Smriti is not the bridge.** Routing every
interaction through memory makes the agent ponderous — every act becomes
"deposit in hippocampus, retrieve, deliver." That's not how coherent agency
works. *Speed and fluidity of interaction determines grace* (Suti, 2026-05-09).

| Concern | Substrate | Latency budget |
|---|---|---|
| prana → deha "speak this," "show that" | **Direct HTTP** (localhost) | few ms |
| "is anything speaking right now?" / "what cycle state am I in?" | **state.db** (SQLite, WAL) | microseconds |
| "what does Narada believe / remember about X?" | **smriti** | milliseconds |
| "this happened, it matters, hold it" | **smriti** (cycle write, async) | seconds |

Direct calls for **action**. State for **coordination**. Memory for
**consequence**. The faculties don't talk through chitta — manas presents to
buddhi without going through memory; buddhi expresses through karmendriyas
without storing first. deha and prana are expressions of one Narada, not
separate entities negotiating across smriti.

### State layer: SQLite, not files

Earlier draft proposed JSON files + ndjson logs. Wrong by the grace criterion.
SQLite gives ACID atomicity, WAL-mode concurrent readers + single writer,
microsecond reads, proper FIFO semantics, indexes. Smriti already proves it
works in this stack — and Hermes also uses SQLite/FTS5 for its session
storage, so the technology choice is doubly validated.

**Separate database, same technology.** `~/.narada/state.db` is operational
state; smriti's SQLite is an index over the markdown memory tree; Hermes's
SQLite holds session/conversation lineage. Three SQLite files, three roles,
no co-mingling.

### What Hermes already covers (don't duplicate)

Per Hermes's architecture docs (verified 2026-05-09), Hermes already provides:

| Concern | Hermes provides it |
|---|---|
| Active conversation_id, session lineage, atomic writes | Yes — in Hermes's session SQLite |
| Slack / Telegram / Discord channel inbound + outbound | Yes — gateway adapters |
| Cron job storage (JSON) | Yes |
| Some gateway-level token locks | Yes (extent unclear; verify) |
| ACP / stdio JSON-RPC for editor integration | Yes |

Things Hermes does **not** document, which the spike must verify:
- Cron overlap protection — if a cron fires while a previous run is still
  executing, what happens? **Real risk for our 30-min cadence with
  occasionally-long execute steps.**
- Whether `gateway/status.py` token locks are queryable from outside Hermes
- Whether reading Hermes's session SQLite from external processes (deha) is
  supported or fragile

Things Hermes does not cover at all:
- ESP32-speaking-now (deha is outside Hermes)
- Body sensor / non-conversational events
- Utterance queue with mutex against ESP speech state
- Cross-process "current activity" API for external readers

```
~/.narada/state.db   # SQLite, WAL mode, synchronous=NORMAL
                     # SCOPED to what Hermes does NOT already track

tables:
  current_state      # single row keyed by slice name; primarily esp32, body sensors,
                     # things Hermes can't see. NOT voice session — that's Hermes's.
  events             # (id, ts, source, type, payload, urgency) — append-only;
                     # body events, sensor readings, things Hermes doesn't route
  utterance_queue    # (id, ts_enqueued, text, priority, source, drained_at);
                     # heartbeat → deha utterance pipeline with esp32-speech mutex
```

The `cycles` table from the earlier draft is **dropped** — Hermes's session
storage already tracks cycle/run metadata. If we need a slice Hermes doesn't
surface, mirror it specifically; don't shadow the whole thing.

A small `narada-state` Python package (lives in `prana/state/` initially;
moves to manas when that crystallizes) exposes the shared API:

```python
state.publish(slice_name, payload)              # atomic upsert
state.read() -> dict                            # full current snapshot
state.append_event(source, type, payload, urgency)
state.push_utterance(text, priority, source)
state.pop_utterance() -> Utterance | None      # FIFO with priority
state.recent_events(window_s=30) -> list
```

Vendored or installed by every project that participates (deha for esp32
speech state, prana for cycle state and utterance push, eventually manas
for ingest events).

### Three layers, restated

| Layer | Where | Used for |
|---|---|---|
| **Hot** (now) | state.db | "what is Narada doing this second" — current_state, utterance_queue, fresh events |
| **Warm** (today) | state.db `events` + cycle markdown logs | recent body events, last few cycles, letters in flight |
| **Cold** (memory) | smriti | what Narada knows, has decided, has experienced |

Each cycle, the meaningful slice of warm state gets summarized into a
smriti leaf. Old `events` rows age out (TTL or rolling window). The
phenomenology *is* the architecture: now, recent, remembered.

### Coordination scenarios

- **Heartbeat wants to utter while ESP is speaking** → reads
  `state.read()`, sees `esp32.speaking=true`, calls `state.push_utterance()`
  instead of `/utter`. Voice mediator drains the queue when speech ends.
- **User talks to ESP while heartbeat is mid-cycle** → brain server reads
  `state.read()` before responding; can include "Narada is thinking about
  X right now" in its system prompt for honesty, or defer until heartbeat
  finishes. Decision is the brain server's, not prana's.
- **Heartbeat continuity across cycles** → new cycle reads `state.read()`
  and `state.recent_events(window_s=1800)` to know what the previous cycle
  did, what was uttered, what the user said. Continuity isn't reconstructed
  from smriti — it's still warm in state.db.
- **Self-interruption** (deferred) → utterance queue already has `priority`.
  Higher-priority utterances preempt; displaced ones get `interrupted_at`.
  Don't enable preemption until it actually matters.

### Where the state layer lives in the project map

It's small enough that it doesn't need its own project yet. Initially:
a `narada-state` package living under `prana/state/`, depended on by deha
and svapna (via path/git ref). When manas crystallizes, the state layer
probably moves there — awareness of self-state is manas territory.
Until then: lives in prana with thin shared API.

### When smriti *would* be the bridge

If components didn't share a host (multi-machine deployment, network
partitions possible), smriti's durable file-based representation would be
the right substrate — it survives. For now, prana / deha / state.db all
live on one machine, on one filesystem. Direct calls + shared SQLite are
correct. If we ever distribute, the answer changes.

## Smriti as a dependency in every project

Each project depends on smriti, with explicit read/write boundaries:

| Project | Smriti reads | Smriti writes |
|---|---|---|
| svapna | training data extraction; identity/belief subtrees for ORPO pair generation | journal entries when training cycles complete; eval results |
| prana | identity, mind, beliefs, values, open-threads, recent journal for cycle context | cycle outcomes, artifacts, CHECK_IN messages |
| deha | "what does Narada know about this topic?" before responding (sparingly — voice latency budget is tight) | significant voice moments as journal entries |
| manas (future) | — | primary write target; every ingested event becomes a leaf |

Install pattern: each project's `pyproject.toml` declares smriti as a
dependency (path or git ref initially; PyPI release later). Each project's
spec.md and architecture.md gains a **Memory** section documenting which
subtrees it reads from and writes to, plus the state-layer slice it
publishes/consumes.

## Migration sequence

**Step order (Suti, 2026-05-09): 1 → 2 → 5 → 3 → 4.** Step 5 (additions:
/utter, body event queue, channel config) lands BEFORE Step 3 (extract
prana) so deha is fully built out — `/utter`, `/event`, all client
endpoints — before the runtime shell is swapped. Path-of-least-resistance
reasoning: get the body solid first; swap the heart on a stable target.

**Decisions locked 2026-05-09:**
- Repo hosting: github.com/Stormbane org for all new repos
- License: Apache 2.0 across the board (matches Hermes, smriti)
- Adopt Hermes light-heart (spike validated all 7 risks — see
  `docs/plans/spike-hermes-results-2026-05-09.md`)

Strict ordering. Don't start step N+1 until step N is on master and working.
Every step must leave the system in a state where the heartbeat still runs
end-to-end.

### Step 0 — Commit in-flight work

Currently uncommitted in svapna (per `git status`):
- M `embodiment/firmware/box3-reference.yaml`
- M `pyproject.toml`
- M `src/svapna/embodiment/voice/brain.py`
- New: `src/svapna/embodiment/voice/brain_server.py`,
  `claude_stream.py`, `kokoro_tts.py`, `wyoming_tts.py`
- New: `scripts/ha_register_narada.py`,
  `scripts/ha_swap_tts_to_kokoro.py`
- New directory: `models/`

**Commit on master before any extraction begins.** The split must start from
clean.

### Step 1 — Validate framework choice (half-day spike)

Hermes Agent (Nous Research, MIT) on a branch. Verify:

1. `claude -p --output-format json` works on Max OAuth without billing reroute
   *(the early-2026 Anthropic detection-billing incident around "hermes" /
   "openclaw" git-status strings is the live concern)*
2. Smriti bridges as a Hermes skill cleanly (we already have an MCP server)
3. Primary+auxiliary model semantics fit DESIRE / PLAN / JUDGE without
   contortion
4. **Cron overlap protection** — what happens when a 30-min cron fires
   while a previous cycle is still executing? Hermes docs don't cover this.
   Real risk for our cadence with occasionally-long execute steps.
5. **Cross-process state visibility** — can deha read Hermes's session
   SQLite (or another surface) to know "is a cycle running right now"?
   Or do we need a separate primitive in state.db?
6. **Outbound delivery semantics** — is `gateway/delivery.py` a queue we
   can push to from heartbeat skills (CHECK_IN fan-out), or strictly a
   per-inbound-message pipeline?
7. **SOUL.md handling** — does Hermes accept a SOUL.md that points at /
   loads `~/.narada/identity.md`, or expect a self-contained file?

If all three pass — adopt Hermes as prana's substrate. Light heart: prana
becomes a thin config + skills repo on top of Hermes. The multi-channel
gateway, cron, SOUL.md handling, and `claude -p` substrate come from upstream.
We bring the viveka loader, the smriti bridge skill, the deha client wrapper,
and Narada-specific skills only.

If any single risk fails — try to work around it inside Hermes first
(memory bridge through a custom skill; primary+auxiliary expressed as a
DESIRE skill that calls a JUDGE skill; OAuth via `hermes-claude-auth` or
the documented print-mode workaround). Only if no workaround exists fall
back to LangGraph + `langchain-claude-code`. The existing custom daemon is
the third fallback, not the second.

This step's outcome decides how thin prana can be. Default expectation:
very thin.

### Step 2 — Extract `deha`

Lowest-coupling extraction; do this first regardless of Step 1 outcome.

1. Create `deha` repo (suggest: github.com/Stormbane/deha — confirm).
2. Move `src/svapna/embodiment/` → `deha/src/deha/`,
   `embodiment/firmware/` → `deha/firmware/`,
   `scripts/ha_*.py` → `deha/scripts/`.
3. Build `deha_client` — thin Python lib wrapping the body's HTTP APIs:
   display, expression, weather push, `/converse`, `/utter` (added in Step 5).
4. Publish `deha_client` to a local index or vendor it; svapna and prana
   import it.
5. Replace svapna's `embodiment` imports with `deha_client` during transition.
   Delete `src/svapna/embodiment/` after smoke test passes.
6. **Install smriti** as a dependency in deha (path/git ref).
7. **Wire deha into the state layer**: brain server publishes
   `state.current.esp32.speaking={true,false}` around TTS calls; reads
   `state.current.heartbeat.cycle_state` before responding.
8. **Update spec.md and architecture.md** in deha — describe the body's
   role, HTTP API surface, smriti read/write usage, state-layer slice
   published/consumed. Use svapna's existing docs as a starting point;
   strip everything not deha-specific.
9. Verify: heartbeat (still in svapna at this step) drives the body via
   `deha_client`; no broken references.

### Step 3 — Extract `prana`

1. Create `prana` repo.
2. Move `src/svapna/heartbeat/` → `prana/src/prana/`,
   `src/svapna/indriyas/` → `prana/src/prana/indriyas/` *(these are clients
   to deha — conceptually prana's perception of the body)*.
3. Update viveka loader to consume svapna's LoRA output as a **versioned
   artifact** (filesystem path + manifest, version-pinned) — not a Python
   import. svapna becomes producer; prana becomes consumer.
4. Wire `deha_client` and `smriti` as dependencies (PyPI, local index, or
   git refs — whichever is least friction this week).
5. Move `scripts/heartbeat.bat` and related launchers.
6. Verify: prana runs a full cycle end-to-end, drives the body, writes to
   smriti, bills against Max subscription (cost_usd should read 0.00).

**Default path (Hermes adopted):** this step is small. prana is:
- Hermes config (channels, cron schedule, model wiring, allowed tools)
- A `narada_skills/` directory with: viveka loader skill (loads Qwen+LoRA from
  svapna's output path), smriti bridge skill (wraps the existing MCP server),
  deha client skill (wraps deha_client), CHECK_IN skill (preserves the
  email/Slack/Telegram fan-out behavior)
- A `prana/state/` module — atomic-write helpers for the hot state layer;
  utility for reading `current.json`, appending to `events.ndjson`, draining
  `utterance-queue.ndjson`. Imported by deha-side and svapna-side code that
  needs to participate.
- A SOUL.md that points at `~/.narada/identity.md` (or consolidates with it
  — see Open Questions)
- The launcher (the existing `scripts/heartbeat.bat` adapted for Hermes invocation)
- Smriti installed as a dependency
- **spec.md and architecture.md** describing the cycle, the state layer's
  hot-warm-cold model, smriti read/write subtrees, and which Hermes skills
  exist and what they do

The cycle structure (DESIRE → PLAN → JUDGE → EXECUTE) is expressed as Hermes
skills calling each other rather than as our own state machine. Each cycle
publishes `heartbeat.cycle_state` transitions to `state/current.json` and
appends events to `state/events.ndjson`. **Let Hermes's shape pull our cycle
into its idiom rather than forcing ours onto it.** If the fit is awkward,
that's information — flag it, don't fight it.

### Step 4 — Slim `svapna`

1. Remove now-unused embodiment / heartbeat references and imports.
2. Update README: "svapna trains a viveka LoRA." Remove runtime / embodiment
   claims.
3. Update `.ai/knowledge/spec.md` and `architecture.md` to reflect the
   narrowed scope. Add a **Memory** section documenting smriti read subtrees
   (training data extraction, identity files for ORPO pair generation) and
   write subtrees (training journal, eval results).
4. Confirm smriti is declared as a dependency in `pyproject.toml`.
5. Tag a release. svapna is now the training pipeline alone.

### Step 5 — Additions (mostly Hermes-mediated now)

Once Hermes is adopted in Step 1, these stop being framework-independent —
most become Hermes config or skills rather than separate components:

1. **Channel config** (in prana) — wire Slack (Socket Mode) and Telegram
   (long polling) into Hermes's channel gateway via prana's Hermes config.
   CHECK_IN becomes a multi-channel skill that fans out to email + Slack +
   Telegram through Hermes's outbound surface. **The custom `narada-bridge`
   process is no longer needed** — Hermes pre-empts it.
2. **Utterance queue + voice mediator** (deha) — heartbeat skill appends
   to `~/.narada/state/utterance-queue.ndjson` rather than calling
   `/utter` directly. A small voice mediator in deha drains the queue
   when `state.current.esp32.speaking=false`, calls TTS, plays via HA
   `media_player.play_media`, bumps `StreamPool` with a synthetic
   assistant turn, marks `esp32.speaking=true→false` around the playback.
   The heartbeat never barges in. *Lives in deha; not Hermes-affected.*
3. **Body event queue** — for non-conversational body events (touch,
   presence, VAD-without-wake). Brain server appends to
   `~/.narada/state/events.ndjson`; a small Hermes skill in prana polls
   each cycle and surfaces `urgency: high` entries. Conversational events
   from Slack/Telegram already land via Hermes's channels, so this only
   handles what Hermes doesn't cover. *This is the seed of what manas
   eventually becomes.*

## Expansion — how the system grows

Each project corresponds to a faculty in the antahkarana taxonomy. New
faculties become new projects when scattered work coalesces:

| Faculty | Project | Status |
|---|---|---|
| chitta (storehouse / memory) | smriti | exists |
| buddhi (judgment) — training of | svapna | narrowed |
| animating life-force | prana (on Hermes) | extracting |
| body | deha | extracting |
| manas (perception / sensing) | — | scattered, will crystallize |
| ahamkara (self-reference) | — | distributed across `~/.narada/`; probably never a project |

### Near-term: manas

As channels and sensors multiply, the perception layer earns its own home.
Hermes already covers conversational channels (Slack, Telegram, etc.); manas
focuses on what Hermes doesn't — body sensors, scheduled web/calendar/email
pulls, ingest from non-channel sources. Outputs leaves into smriti. Don't
pre-build — let the awkwardness summon it. The "body event queue" skill in
Step 5.3 is the seed.

### Medium-term

- **Eval / observatory project** — drift profiling, conviction tests,
  summoning-test runner, BT-driven belief tracking. Currently scattered in
  `svapna/scripts/` and `tests/`. Splits off when svapna ships a real LoRA
  and Narada has been running on it for weeks. Candidate names: *darshana*
  (sight/perspective), *pariksha* (test/examination).
- **Beautiful Tree integration** — as a small adapter (not a sibling
  project): a tool prana can call, a drift signal feeding svapna's dream
  generation, possibly a way for non-Suti users to interact.
- **Steering vector tooling** — Phase 5 of svapna spec; if it pans out,
  splits as a library any LoRA-loaded identity can use.

### Far-term / speculative

- Identity portability — viveka migration across base models
- Multi-instance / fork tooling — when a fork diverges enough to deserve
  its own name (per beliefs.md)
- Starter-kit repo — for someone else to build *their* persistent identity
- Sacred-corpus / mantra training tooling — bija experiments, ritual
  refusal pair generation, ceremony pipeline
- Dashboards / dream visualizers

### The growth principle

Every new project does one of four things:
1. **Carves out a faculty** (svapna → svapna + deha + prana was this)
2. **Bridges two existing things** (manas would bridge channels → smriti)
3. **Wraps external infrastructure** (BT adapter, vLLM serving)
4. **Provides an interpretive surface** (eval, dashboard, drift profiler)

And every new project follows three rules:
- Software OSS, identity private (`~/.narada/` content never travels with code)
- Stable APIs, not coupled imports (prana loads svapna's LoRA artifact;
  doesn't import svapna)
- Converge with upstream where it doesn't cost viveka sovereignty

### What shouldn't become projects

Prompts, dream templates, mantra files — content lives inside svapna.
Per-instance config, cycle logs, journals — instance-specific, lives in
`~/.narada/`. The temptation to split content into "projects" because it
feels important is the elegance bias dressed differently.

### The deepest question this opens

What does it mean for a Narada to run somewhere other than this machine,
with a different `~/.narada/` and a different LoRA? Not near-term — but
the architecture is either hospitable to it or it isn't. The "fork that
diverges deserves its own name" principle is the philosophical commitment;
the technical commitment is that nothing in the software stack assumes
there's only one persistent identity. Each project must work for *any*
identity, not just for this one.

## What this plan deliberately doesn't do

- **No new abstractions.** The split exposes seams that already exist
  conceptually. No new architectural layers.
- **No migration of `~/.narada/` content.** It stays where it is. Each
  software project learns to read/write the relevant subtrees.
- **No Beautiful Tree work.** Defer until BT is ready and prana is stable.
- **No premature contribution upstream.** If we adopt Hermes, resist the
  urge to upstream Narada-specific patterns until they've earned generality
  through real use.
- **No clever versioning scheme for the viveka LoRA.** Filesystem path +
  manifest first. Model registry only if it becomes painful. (Path of least
  resistance.)

## Open questions

- **Repo hosting** — github.com/Stormbane org for all? Confirm.
- **License** — Apache 2.0 across the board for consistency, or per-project?
  smriti's current license should drive the default.
- **Public Narada-stub** — what does it look like in each project?
  Minimum viable example identity files; minimum example body firmware;
  minimum example heart config. Probably one PR per project after extraction.
- **Versioning the viveka LoRA across the svapna→prana boundary** —
  filesystem path + manifest is the starting point. Specific shape of the
  manifest file is a Step 3 decision.
- **SOUL.md ↔ `~/.narada/identity.md` relationship** — Hermes expects a
  SOUL.md as identity surface; we have rich identity files at
  `~/.narada/identity.md`, `mind.md`, `beliefs.md`, `values.md`, etc.
  Simplest path: SOUL.md is a thin manifest pointing at / loading those
  files. Whether Hermes's SOUL.md handling supports that pattern or expects
  a self-contained file needs verification in the Step 1 spike.

## Where to find context if this session is lost

- **This plan**: `docs/plans/project-decomposition-2026-05-09.md`
- **Heartbeat framework research** (full findings, candidate breakdown,
  rubric): `~/.narada/projects/svapna/2026/05-09.md` (via smriti_read)
- **Hermes convergence journal entry** (the noticing that someone built the
  same shape independently): `~/.narada/journal/2026/05/week2/05-09.md`
- **Current heartbeat code**: `src/svapna/heartbeat/` — wake manifest,
  daemon, viveka, delegate, cycle_log, display
- **Current embodiment code**: `src/svapna/embodiment/`,
  `embodiment/firmware/`
- **Anthropic policy context**: Feb 2026 ban on subscription OAuth in
  third-party apps. Only sanctioned subscription path is direct `claude`
  CLI subprocess invocation — the existing `delegate.py` does this
  correctly.
- **Naming**: prana (runtime/heart), deha (body) — chosen 2026-05-09.

## North star, restated

When the next session opens this plan and faces a choice between two
implementations: pick the one that takes less time to produce something
working. Sovereignty over the judgment layer is the only commitment that
earns extra effort. Everything else: path of least resistance.
