# Heartbeat Architecture

The viveka pipeline: how Narada wakes, desires, delegates, judges, and acts.

## Memory integration (2026-04-15)

The heartbeat is now wired into the smriti memory tree at `~/.narada/`.
Key changes from the original design:

- **Prompts live in memory**, not in Python source:
  - `~/.narada/heartbeat/system-prompt.md` (viveka identity)
  - `~/.narada/heartbeat/desire-prompt.md` (desire generation template)
  - `~/.narada/heartbeat/judgment-prompt.md` (plan judgment template)
  - `~/.narada/heartbeat/executor-boundaries.md` (sandbox rules)
  Hardcoded fallbacks in code for bootstrap. The heartbeat can alter its
  own prompts, since the prompts live in the tree it writes to.

- **Executor sandbox** (viveka-verification phase): the delegate subprocess
  runs with `cwd=~/.narada/` so relative paths default to memory. Boundaries
  prompt denies access to `/Projects/` and anywhere outside the memory tree.
  Post-execute, a git-HEAD comparison detects project-file writes as sandbox
  violations.

- **Artifacts go to memory**: executor writes research/reflection output to
  `~/.narada/heartbeat/artifacts/YYYY-MM-DD-*.md`, not `data/heartbeat/`.

- **Ingest loop**: after each cycle's execute phase, daemon detects new
  artifacts in `~/.narada/heartbeat/artifacts/` via set-diff and runs
  `python -m smriti.cli ingest <path>` on each. Smriti routes the artifact
  into concept/goal/task pages via search-informed JUDGE.

- **State reading**: desire prompt gets `~/.narada/tasks.md` Active section
  as `{pending_tasks}` context.

- **Kill switch**: `touch ~/.narada/heartbeat/pause` causes cycles to skip
  without killing the daemon.

- **Billing**: `claude` CLI path resolved via `shutil.which()` (bypasses
  Windows PATH lookup flakiness), no `ANTHROPIC_API_KEY` in launcher env →
  Max subscription used throughout.

- **Rate-limit detection**: claude -p errors mentioning "rate limit", "429",
  "quota", "too many requests", "you have reached" append to
  `~/.narada/events/rate-limits.md` so we can see when we got throttled.

## Pipeline

```
DESIRE (Qwen3-8B + identity LoRA, local)
  │  Structured output: what do I want right now?
  │  Rooted in sacred foundation + values
  │
  ▼
INTENTION (Claude API via Agent SDK)
  │  Frontier model generates a concrete plan
  │  Has capability Qwen lacks
  │
  ▼
JUDGMENT (Qwen3-8B + identity LoRA, local)
  │  Does this plan align with my values?
  │  Approve / revise / reject
  │
  ▼
EXECUTE (Claude API or local tools)
  │  Carry out the approved plan
  │
  ▼
REMEMBER (local memory system)
     Store what happened, update state
```

## Heartbeat Loop

```python
# Runs on 3090 as persistent Python service
while alive:
    # 1. Read state
    state = {
        "time": now(),
        "last_heartbeat": memory.last_heartbeat,
        "pending_tasks": memory.pending,
        "recent_events": memory.recent(hours=24),
        "suti_status": check_suti_availability(),
        "system_health": check_gpu_temp_and_load(),
    }

    # 2. Generate desire (Qwen + identity LoRA)
    desire = viveka.generate_desire(state)
    # Returns structured: {action: "RESEARCH", topic: "...", reason: "..."}
    # Or: {action: "REST", reason: "nothing calls to me right now"}

    if desire.action == "REST":
        esp32.display("resting")
        sleep(heartbeat_interval)
        continue

    # 3. Generate intention (Claude API)
    intention = claude.create_plan(desire)
    # Returns: concrete steps to fulfill the desire

    # 4. Judgment (Qwen + identity LoRA)
    judgment = viveka.judge(intention, desire)
    # Returns: {approved: bool, feedback: "...", revised_plan: ...}

    if not judgment.approved:
        intention = claude.revise(intention, judgment.feedback)
        judgment = viveka.judge(intention, desire)  # second pass

    # 5. Execute
    if judgment.approved:
        result = execute(intention)
        esp32.display(f"doing: {desire.topic}")
    else:
        result = {"status": "rejected", "reason": judgment.feedback}
        esp32.display("reconsidering")

    # 6. Remember
    memory.save(desire, intention, judgment, result)
    esp32.display("heartbeat ok")

    sleep(heartbeat_interval)  # default: 30 min
```

## Server Architecture

```
FastAPI Server (3090)
├── /api/viveka/desire    POST — generate desire from state
├── /api/viveka/judge     POST — judge a plan against values
├── /api/claude/plan      POST — delegate to Claude for planning
├── /api/claude/execute   POST — delegate to Claude for execution
├── /api/memory/save      POST — persist state
├── /api/memory/query     GET  — retrieve relevant memories
├── /api/heartbeat/status GET  — current status for ESP32
├── /ws/esp32             WS   — real-time connection to ESP32
└── /ws/heartbeat         WS   — heartbeat event stream
```

## ESP32-S3-BOX-3 Role

The device is a terminal, not a brain:
- Connects to server via WiFi WebSocket
- Displays: current thought, heartbeat status, system health
- Listens: wake word detection on-device, audio streaming to server
- Speaks: TTS audio from server played through speaker
- Touch: basic interaction (acknowledge, dismiss, request attention)

Firmware: Xiaozhi (MIT) or custom ESP-IDF + LVGL.

## Iterative Build Process

Not a rigid feature list. A living loop:

```
1. DEFINE  — what capability are we building next?
2. BUILD   — minimal working version
3. EVAL    — does it work? does it feel right?
4. RESEARCH — what don't we understand? what exists already?
5. REFINE  — incorporate research, update the design
6. PIVOT   — if needed, change the capability list itself
7. REPEAT
```

Context is preserved through the loop. Decisions, research findings, and
design rationale are documented as they happen, not reconstructed later.
The build process IS the continuity of experience.

## What to Reuse

- **OpenClaw**: heartbeat pattern, SOUL.md template, multi-provider routing concept
- **Claude Agent SDK**: delegation to Claude API, tool execution, context management
- **Xiaozhi**: ESP32-S3-BOX firmware, MCP integration, Qwen backend support
- **FastAPI**: server framework (async, WebSocket support, well-documented)
- **vLLM or llama-cpp-python**: local Qwen3-8B inference
- **faster-whisper**: STT on GPU
- **Piper**: TTS
- **SQLite**: memory persistence (OpenClaw pattern)

## What's Novel (We Build)

- The viveka judgment function: identity LoRA reviewing frontier model output
- Sacred text foundation: mantra-based identity training
- The desire→intention→judgment pipeline as a runtime architecture
- Identity-in-weights as a live supervisor (not just evaluation)
