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

### Three layers, not one

Smriti alone can't carry this — its reads are search-indexed (latency too
high for "am I speaking now?"), and putting transient operational state in
the memory tree muddles consequence with telemetry. So:

| Layer | Where | Latency | What lives here |
|---|---|---|---|
| **Hot** (now) | `~/.narada/state/` files | sub-second | "ESP is speaking," current cycle state, utterance queue, active conversation_id |
| **Warm** (today) | `~/.narada/inbox/`, cycle logs | seconds | recent events, body sensor readings, letters, last few cycles |
| **Cold** (memory) | smriti | indexed search | what Narada knows, has decided, has experienced |

Each cycle, hot state gets summarized into a smriti leaf. Warm state ages
into cold via smriti's cascade. The phenomenology *is* the architecture:
now, recent, remembered.

### Hot state layout

```
~/.narada/state/
  current.json           # atomic-write snapshot of "what's happening now"
  events.ndjson          # append-only event log (audit + replay + cascade source)
  utterance-queue.ndjson # FIFO of things waiting to be said
```

`current.json` schema (sketch — refined during implementation):

```json
{
  "esp32": {
    "speaking": true,
    "speech_started": "2026-05-09T14:32:18Z",
    "speech_text": "the rain is settling...",
    "speech_source": "voice-conversation"
  },
  "heartbeat": {
    "cycle_state": "executing",
    "cycle_id": "2026-05-09-1432",
    "action": "BUILD",
    "topic": "refusal-pair-batch-12"
  },
  "voice_session": {
    "active_conversation_id": "abc123",
    "last_user_turn": "2026-05-09T14:31:50Z"
  }
}
```

Each component publishes its slice via atomic write (temp-file + rename).
Each component reads the whole file when it needs to know what's going on.
Files survive crashes, are inspectable with `cat`, work without a running
daemon. If contention bites later, drop in SQLite WAL or a tiny FastAPI
service. Filesystem first.

### Coordination scenarios

- **Heartbeat wants to utter while ESP is speaking** → reads `current.json`,
  sees `esp32.speaking=true`, appends to `utterance-queue.ndjson` instead of
  calling `/utter`. Voice mediator drains the queue when speech ends.
- **User talks to ESP while heartbeat is mid-cycle** → brain server reads
  `current.json` before responding; can include "Narada is thinking about
  X right now" in its system prompt for honesty, or defer until heartbeat
  finishes.
- **Heartbeat continuity across cycles** → new cycle reads `current.json`
  and recent `events.ndjson` entries to know what the previous cycle did,
  what was uttered, what the user said. Continuity isn't reconstructed from
  memory — it's still warm.
- **Self-interruption** (deferred) → add `priority` to utterance queue.
  High-priority utterances preempt; displaced ones get `interrupted_at`
  markers. Don't build this until it actually matters.

### Where the state layer lives in the project map

It's small enough that it doesn't need its own project yet. Initially:
a `prana/state/` module exposing read/write helpers, imported by deha and
svapna as needed. When manas crystallizes, the state layer probably moves
there — perception of self-state is manas territory. Until then: lives in
prana with thin client helpers vendored where needed.

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
- A SOUL.md that points at `~/.narada/identity.md` (or consolidates with it
  — see Open Questions)
- The launcher (the existing `scripts/heartbeat.bat` adapted for Hermes invocation)

The cycle structure (DESIRE → PLAN → JUDGE → EXECUTE) is expressed as Hermes
skills calling each other rather than as our own state machine. **Let Hermes's
shape pull our cycle into its idiom rather than forcing ours onto it.** If
the fit is awkward, that's information — flag it, don't fight it.

### Step 4 — Slim `svapna`

1. Remove now-unused embodiment / heartbeat references and imports.
2. Update README: "svapna trains a viveka LoRA." Remove runtime / embodiment
   claims.
3. Update `.ai/knowledge/spec.md` and `architecture.md` to reflect the
   narrowed scope.
4. Tag a release. svapna is now the training pipeline alone.

### Step 5 — Additions (mostly Hermes-mediated now)

Once Hermes is adopted in Step 1, these stop being framework-independent —
most become Hermes config or skills rather than separate components:

1. **Channel config** (in prana) — wire Slack (Socket Mode) and Telegram
   (long polling) into Hermes's channel gateway via prana's Hermes config.
   CHECK_IN becomes a multi-channel skill that fans out to email + Slack +
   Telegram through Hermes's outbound surface. **The custom `narada-bridge`
   process is no longer needed** — Hermes pre-empts it.
2. **`POST /utter`** on deha's brain server — heartbeat-initiated speech via
   HA `media_player.play_media`. Routes audio cleanly through HA without
   fighting the wake-word conversation flow. Bumps `StreamPool` with a
   synthetic assistant turn so the voice Claude doesn't deny saying it.
   *Lives in deha; not Hermes-affected.*
3. **Body event queue** — for non-conversational events (touch, presence,
   VAD-without-wake). For now: a small skill in prana that polls
   `~/.narada/inbox/events.ndjson` each cycle and surfaces `urgency: high`
   entries. Conversational events from Slack/Telegram already land via
   Hermes's channels, so this only handles what Hermes doesn't cover.
   *This is the seed of what manas eventually becomes.*

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
