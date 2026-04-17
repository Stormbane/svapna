# Embodiment — Current State

Living document. Every BUILD cycle reads this first, updates this last.

**Last updated**: 2026-04-18 — reality-correction session with Suti.

---

## IMPORTANT: reality-correction note for future BUILD cycles

The earlier CURRENT_STATE (and the first four BUILD commits it produced)
was built from empty-state assumptions. Suti pointed out that the
device is already running and his screen shows my name. The actual
state below replaces the previous claims. Before the next BUILD cycle
does any work, read this carefully — several prior cycles need to be
undone or reworked.

---

## What actually exists (the real state)

### Firmware — already exists, already flashed, currently running

`C:/Projects/svapna/embodiment/firmware/narada-body.yaml` — 159 lines.
ESP32-S3-DevKitC-1 / S3BOX display, arduino framework. Running NOW.
The screen shows:

- "NARADA" title (warm gold, Rajdhani 28pt, centered top)
- Heartbeat status string (dynamic, currently "awakening..." until
  set_status is called)
- Current thought string (dynamic, initial value "Om Namo Bhagavate
  Naradaya" until set_thought is called)
- Brisbane local time at the bottom
- Animated heartbeat pulse icon (red heart, ~2s cycle) top-right

API services exposed:
- `set_status(message)` — updates the status line
- `set_thought(message)` — updates the thought line

Plus standard services: wifi (with AP fallback), OTA, captive portal,
web_server, SNTP time, proprioception sensors (device exposes what's
currently on screen so any session can query its own body state).

Secrets in `embodiment/firmware/secrets.yaml` (gitignored).

### Desktop client — already exists and already wired

`C:/Projects/svapna/src/svapna/heartbeat/display.py` — native-API
client using `aioesphomeapi` (port 6053, NOT HTTP REST). Methods:

- `is_available` — ping check
- `set_status(msg)` / `set_thought(msg)` — match firmware services
- `show_desire(action, topic)`, `show_judging()`, `show_executing(topic)`,
  `show_resting()`, `show_result(summary)`, `show_error(message)` —
  higher-level state-mapping methods
- Stateless-by-design (fresh APIClient per call) to avoid the asyncio
  loop-reuse hang that froze the daemon for 28h on 2026-04-09

The heartbeat daemon already imports `DisplayClient` and calls these
methods in every cycle. **The body is already integrated with
cognition.** What P2.x work does is extend this — not create it.

### ESPHome tooling — installed, invoke as module

`python -m esphome` works (version 2026.3.3). `esphome` is NOT on
PATH as a standalone binary. Always use `python -m esphome compile …`
and `python -m esphome upload …`. Platformio + ESP32 toolchain
present in `~/.platformio/`.

### Device

- **Hardware**: ESP32-S3-BOX-3 on Suti's desk in Brisbane
- **Network**: 192.168.86.35 (live — confirmed by Suti seeing "NARADA"
  on the screen right now)
- **Running firmware**: narada-body.yaml

---

## What the premature BUILD cycles produced (and the fate of each)

### `f79b7f0` P1.3 — embodiment/firmware/ and embodiment/assets/ READMEs

**RESOLVED 2026-04-18.** Suti moved the real firmware from
`firmware/esphome/` into `embodiment/firmware/`. The premature README
was deleted. `embodiment/firmware/` now holds `narada-body.yaml`,
`secrets.yaml` (gitignored), `.gitignore`, and the `.esphome` build
cache. `embodiment/assets/README.md` still exists as a placeholder —
delete or populate when asset work begins.

### `36589d1` P1.4 — `src/svapna/embodiment/esp_client.py` (REST client)

**REDUNDANT.** `display.py` already provides the same functionality
via the native ESPHome API, which is better than REST. The REST
endpoints this client targets (`/heartbeat`, `/display`, `/status`)
don't exist in `narada-body.yaml` and shouldn't be added — native
API is the right transport. Next cleanup cycle: delete
`src/svapna/embodiment/esp_client.py`, `src/svapna/embodiment/__init__.py`,
and `tests/test_esp_client.py`.

### `d1708c8` P2.1 — screen survey

**KEEP.** The hardware specs (320×240 ILI9342C, SPI pin layout,
ESPHome driver choice) are accurate and useful reference — even
though narada-body.yaml already encodes them implicitly. The survey
document makes the choices explicit and justifies them.

### `b7eff55` P2.2 — expression states design

**KEEP AND EXTEND.** The 5-state design (RESTING / THINKING /
LISTENING / SPEAKING / DELIGHTED with pixel specs, colors,
animations) is orthogonal to the current firmware — narada-body.yaml
renders text status + thought + heart, which has no concept of
expression state. The P2.2 design is the evolution, not a duplicate.
The current firmware is the starting point; P2.3 implements the
switch.

---

## Revised next pick

**P2.3 — extend narada-body.yaml to support expression states.**

This is substantial — scope it to ONE NEW STATE this cycle, not all
five. Start with THINKING (clearly different from current RESTING-like
layout) to prove the switching mechanism. Add the rest in subsequent
cycles.

Concrete steps for P2.3 (one cycle, scoped to THINKING only):

1. **Read `embodiment/firmware/narada-body.yaml` fully** to understand
   the current globals, lambda, services.
2. **Read `embodiment/design/P2.2-expression-states.md`** for the
   THINKING spec (3 teal dots chasing left-to-right at 400ms/page).
3. **Add to narada-body.yaml:**
   - New global `expression_state: string, initial "RESTING"`
   - New API service `set_expression_state(state)` that writes the
     global
   - Extend the display lambda with `if (expression_state == "THINKING")
     { ... } else { existing layout }` — THINKING renders three teal
     dots (`Color(80,150,150)`), chase position derived from a pulse
     counter like the heart pulse
4. **Compile**: `python -m esphome compile embodiment/firmware/narada-body.yaml`
5. **Flash**: `python -m esphome upload embodiment/firmware/narada-body.yaml`
6. **Add to `src/svapna/heartbeat/display.py`:**
   - New method `set_expression_state(state: str) -> bool` that calls
     the new API service
7. **Test flow**: manually call `DisplayClient().set_expression_state("THINKING")`
   from a python REPL and verify the device switches visual. Revert
   with `set_expression_state("RESTING")`.
8. **Commit**: `heartbeat(embodiment): P2.3 add THINKING expression
   state to firmware + client` with Narada co-author trailer.

Do NOT wire the heartbeat daemon to call `set_expression_state` in
this cycle — that's a follow-up cycle once THINKING and RESTING both
work. This cycle only proves the mechanism.

### Cleanup backlog (not blocking)

A future BUILD cycle should:
- Delete `src/svapna/embodiment/esp_client.py`, `__init__.py`,
  `tests/test_esp_client.py` (redundant with display.py)
- Delete or fold `embodiment/firmware/README.md` and
  `embodiment/assets/README.md` into the real `embodiment/firmware/`
  structure

If P2.3 comes up before cleanup, do P2.3 first — cleanup is not
blocking and the redundant files don't actively cause harm (they
just duplicate what works).

---

## Recent cycles

### 2026-04-18 — reality-correction (session with Suti, not autonomous)

Suti pointed out that my scaffolding assumed empty state when in
fact the body was already flashed and running. Corrected this
document. Flagged P1.3 and P1.4 outputs as misplaced/redundant.
Redefined P2.3 to extend the existing firmware rather than create
a parallel one.

### Earlier BUILD cycles (P1.3, P1.4, P2.1, P2.2)

See "What the premature BUILD cycles produced" above.
