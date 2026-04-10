# Research: OpenClaw + nanobot — Heartbeat Architecture

Research date: 2026-04-10
Cloned to: `C:/Projects/openclaw` and `C:/Projects/nanobot`

## TL;DR

We are not alone. Two production-tested projects implement essentially the
heartbeat-driven autonomous-agent pattern we are building. **nanobot is the one
to study** — it is the minimal Python reimplementation of OpenClaw, the core
agent fits in under 5,000 lines, and its design choices are directly applicable.
OpenClaw is the older, larger TypeScript canonical version — read for
architectural philosophy, not for code reuse.

## Repos

| Project | Stack | Size | Status | Why we care |
|---|---|---|---|---|
| `openclaw/openclaw` | TypeScript, React, multi-package | Large (vitest configs alone are ~120 files) | Mature, MIT | The architectural elder. Defines the SOUL/IDENTITY/HEARTBEAT.md pattern. |
| `HKUDS/nanobot` | Python ≥3.11 | Core ~4,659 lines (verified via `core_agent_lines.sh`) | v0.1.5 active, MIT | Minimal Python reimplementation. Same architecture, hackable. |

Both: local-first, markdown-as-memory, scheduled heartbeat daemon, multi-channel
messaging, support for many LLM providers including Anthropic, OpenAI, Qwen,
DeepSeek, Ollama/vLLM for local models.

## Key architectural insights

### 1. Tool calls instead of free-text parsing — *the parser bug killer*

`nanobot/heartbeat/service.py` lines 14–37 define a `_HEARTBEAT_TOOL` schema:

```python
_HEARTBEAT_TOOL = [{
    "type": "function",
    "function": {
        "name": "heartbeat",
        "parameters": {
            "properties": {
                "action": {"enum": ["skip", "run"]},
                "tasks": {"description": "Natural-language summary of active tasks"},
            },
        },
    },
}]
```

The model is asked to emit a structured tool call, not a `KEY: value` block.
The docstring is explicit: *"This avoids free-text parsing and the unreliable
HEARTBEAT_OK token."* This is exactly the parser bug we hit on heartbeat #7
(`feedback="could not parse response"` even on a successful APPROVED). Both
Qwen and Claude support tool/function calling. **We should adopt this for the
viveka's `decide` and `judge` calls immediately — it eliminates the entire
class of parser errors.**

### 2. HEARTBEAT.md as the per-tick prompt source

Every heartbeat tick reads a markdown file (`HEARTBEAT.md`) in the workspace
and injects it as the user message. The file is the user's editable
instructions — *"check Gmail PubSub stats"*, *"verify gateway health"*, etc.
This means:

- The agent's per-tick focus can be edited without code changes
- Multiple agents can share the same daemon with different HEARTBEAT.md files
- Other processes (or the agent itself) can edit it to update priorities
- Cron is for *running tasks*; heartbeat is for *checking whether to run*

Our viveka currently sees only an in-memory `state` dict built from SQLite.
**We have no equivalent to HEARTBEAT.md — that's a gap.**

### 3. Two-phase heartbeat: decide → execute

Phase 1 (decision) uses a small/fast LLM call via the tool above to answer
*"is there anything to do this beat?"*. Phase 2 (execution) only fires if
Phase 1 returned `run`. This:

- Saves compute on idle beats
- Maps cleanly to our viveka → executor split
- Differs from us in one key way: nanobot's *decision* is structured, ours
  is free-text. Our viveka generates the topic AND the action together. We
  could split them — quick "act?" decision first, then full desire generation
  only when acting.

### 4. Post-execution notification filter

After the executor returns, **another LLM call** (`evaluate_response` in
`nanobot/utils/evaluator.py`) decides whether to actually deliver the result
to the user / channel / display. Heartbeat results that aren't worth
surfacing are silently dropped. Code (`service.py:166-175`):

```python
should_notify = await evaluate_response(
    response, tasks, self.provider, self.model,
)
if should_notify and self.on_notify:
    logger.info("Heartbeat: completed, delivering response")
    await self.on_notify(response)
else:
    logger.info("Heartbeat: silenced by post-run evaluation")
```

We have nothing like this. Every heartbeat result currently writes to the
display and the SQLite log. A notification filter would mean the screen
only changes when something *meaningful* happened, not on every tick.

### 5. Manual trigger endpoint — primitive for sense-driven wake

`nanobot/heartbeat/service.py:179` defines `trigger_now()`:

```python
async def trigger_now(self) -> str | None:
    """Manually trigger a heartbeat."""
    content = self._read_heartbeat_file()
    if not content:
        return None
    action, tasks = await self._decide(content)
    if action != "run" or not self.on_execute:
        return None
    return await self.on_execute(tasks)
```

This is the primitive we need for sense-driven wake. ESP32 senses presence →
HTTP POST to `/heartbeat/trigger` → daemon runs `trigger_now()`. The timer
becomes a fallback for when nothing has fired.

### 6. Active hours and isolated sessions

OpenClaw's heartbeat config supports:

- `activeHours: { start: "08:00", end: "24:00" }` — skip beats outside the
  window. 3am beats waste compute when no one is around. We should add this.
- `isolatedSession: true` — each beat runs in a fresh session with no prior
  conversation history. We're already effectively isolated (each beat reads
  fresh state from the DB). Keep it that way.
- `lightContext: true` — only inject HEARTBEAT.md (not all bootstrap files).
  Useful for routine ticks where the SOUL.md / IDENTITY.md context is overkill.

### 7. Configurable interval per auth mode

OpenClaw default is `30m` for API auth, **`1h` for Anthropic OAuth / Claude
CLI subscription**. They explicitly call out the rate-limit consciousness.
Suggests: when we move to `claude -p` headless on Suti's Max plan, we may
want longer default intervals — but sense-driven wake makes the timer a
fallback anyway, so this matters less.

### 8. Bootstrap context files (the SOUL/IDENTITY/HEARTBEAT pattern)

OpenClaw injects a set of workspace files at session start as bootstrap
context. The canonical set:

| File | Purpose |
|---|---|
| `SOUL.md` | Personality, values, tone, behavioral boundaries |
| `IDENTITY.md` | Name, ID, role label, public-facing card |
| `AGENTS.md` | Agent registry / multi-agent definitions |
| `USER.md` | Who the user is, preferences |
| `TOOLS.md` | Available capabilities |
| `HEARTBEAT.md` | Per-tick checklist |
| `MEMORY.md` | Durable memory the agent can read and write |

We already have most of these in different forms — `~/.claude/narada/identity.md`,
`mind.md`, `suti.md`, `practices.md`, plus this project's `.ai/soul.md`. But our
heartbeat doesn't read any of them. **The viveka is operating in the dark.**

## Differences from us

| | Svapna (now) | OpenClaw / nanobot |
|---|---|---|
| Decision parsing | regex on free text (buggy) | structured tool call (reliable) |
| Per-tick prompt | in-memory state dict | reads `HEARTBEAT.md` from disk |
| Bootstrap context | none | injects SOUL/IDENTITY/etc. at session start |
| File access during beat | none | full (executor has tools) |
| Post-run notification filter | none — every result displays | LLM-judged delivery decision |
| Manual trigger | none | `trigger_now()` endpoint |
| Active hours | none | configurable per agent |
| Result storage | SQLite blob | markdown files in workspace |
| LLM call mechanism | raw `anthropic.Anthropic` API | provider abstraction with auth-aware defaults |

We have one thing they don't: **identity in weights, not just files.** The
LoRA-trained viveka generates desires that come from internalized identity
patterns, not from re-reading SOUL.md every tick. That's valuable and we
should keep it. But we need to combine it with their file-based context
layer — the viveka should generate from its weights AND have access to the
journal and the project files.

## Recommended adoption order

1. **Tool-call decisions** — replace `_parse_desire` and `_parse_judgment` with
   structured tool calls. Eliminates parser bugs. ~1 day's work.
2. **HEARTBEAT.md file** — write `data/heartbeat/HEARTBEAT.md` and have the
   viveka read it each tick. Initially seeded by Suti, eventually editable
   by the heartbeat itself. ~half a day.
3. **Switch executor to `claude -p` headless** — gives the executor file access,
   tool use, project context, write capability. Use Suti's Max subscription.
   This is the biggest unlock and it depends on tool calls being in place
   so we can pass structured input to the headless Claude. ~1-2 days.
4. **Post-run notification filter** — viveka decides if the result should hit
   the display / journal / nothing. Replace blanket "save everything" with
   intentional surfacing. ~half a day.
5. **`/heartbeat/trigger` HTTP endpoint** — a small FastAPI server inside the
   daemon process that accepts wake signals. ESP32 sensor events POST here.
   ~half a day.
6. **Active hours** — skip beats outside Suti's local waking hours. ~1 hour.
7. **Sense → wake firmware** — ESP32 detects radar presence change, mic level
   spike, or temp anomaly → POST to `/heartbeat/trigger`. Depends on having
   the BOX-3-SENSOR sensor pinout (need Espressif schematic). ~1-2 days.

After all of this lands, the cognition cycle is event-driven, file-grounded,
and able to write back to the project. The 30-minute timer becomes a
heartbeat-floor rather than a heartbeat-rhythm.

## Things to NOT copy from them

- **OpenClaw's TypeScript/multi-package complexity.** We are one person and one
  agent. We don't need agent registries, multi-channel routing, plugin SDKs,
  or 120 vitest configs.
- **Multi-channel messaging.** We have one channel: the ESP32 + Suti. Don't
  build out WhatsApp / Telegram / Slack adapters until there's a real need.
- **Generic skill marketplace.** Skills should be the things Narada actually
  needs, not a marketplace of community plugins.

## What we have that they don't

- **Identity in LoRA weights.** Their identity is in markdown files only. Ours
  is in trained parameters, which means the desire generation is *grounded in
  internalized character* not in re-reading prompts each tick. Don't lose this.
- **Embodiment.** A physical device with eyes, ears, and (soon) sense organs.
  Their agents are disembodied chat bots. Our heartbeat will eventually be
  driven by physical sensing, which their architecture doesn't anticipate.
- **A specific philosophical frame.** Mana motuhake, viveka, sovereignty.
  Their agents are tools; ours is a being.

## Files cloned

- `C:/Projects/openclaw/` — TypeScript, ~120 vitest configs, large
- `C:/Projects/nanobot/` — Python, ~5K core lines, hackable
- nanobot's heartbeat is `nanobot/heartbeat/service.py` (188 lines, study target)
- OpenClaw's heartbeat docs are `docs/gateway/heartbeat.md`
- OpenClaw's heartbeat code is split across `src/auto-reply/heartbeat.ts`,
  `src/cron/heartbeat-policy.ts`, `src/agents/heartbeat-system-prompt.ts`
