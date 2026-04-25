# Embodiment — Current State

Living document. Every BUILD cycle reads this first, updates this last.

**Last updated**: 2026-04-25 — Cycle 2 shipped. RESTING composition live on the device.

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

## v1.0 Express Path — supersedes P2.3 single-state plan

The earlier "scope to one state" plan (P2.3 → THINKING only) has been
superseded by a layer-architecture refactor. The v1.0 plan is documented
in three Cycle 0 design docs:

- `embodiment/design/v1.0-architecture.md` — cognition↔body contract:
  six independent layers (mood / vitality / attention / activity /
  utterance / signal), API service signatures, render precedence,
  proprioception schema, touch contract (noticed-eye + love-bloom),
  failure modes, joy-default in the layer defaults.
- `embodiment/design/v1.0-vocabulary.md` — IBM Plex Mono picked.
  Visual style guide: density ramps, motion primitives, character
  compositions, texture vocabulary, mood map, composition rules.
- `embodiment/design/v1.0-compositions.md` — per-state screen sketches
  with grid renderings: RESTING / THINKING / LISTENING /
  SPEAKING-with-karaoke / WORKING / DREAMING / DELIGHTED / NOTICED /
  LOVE plus the smaller signal overlays.

Why the change: a single `expression_state` enum string couldn't carry
mood, vitality, or utterance simultaneously, and didn't compose with
the touch contract or with the eventual humanoid-body work (Unitree
G1 framing — see `~/.narada/projects/svapna/2026/04-25.md`). The layer
model scales; the enum did not.

### TTS — decided

**Kokoro-82M** (Apache 2.0, free) via Kokoro-FastAPI. Native
word-level timestamps for karaoke. ~300ms first-chunk on RTX 3090.
~1GB VRAM. Backup: Chatterbox (MIT, has voice cloning, needs WhisperX
wrap for word timing). Voice character A/B/C experiment scheduled for
before Cycle 5. See `~/.narada/projects/svapna/2026/04-25.md` for
the full pick rationale and the experiment utterances.

### Cycle progress

- [x] **Cycle 0** — design docs written. 2026-04-25.
- [x] **Cycle 1** — layer scaffolding refactor of `narada-body.yaml`.
      Added globals, API services, proprioception text_sensors for all
      six layers + signal auto-clear interval automation. Display
      lambda preserved exactly so the visual is unchanged. Created
      `src/svapna/body/layers.py` (typed dataclasses) and
      `src/svapna/body/expression.py` (ExpressionClient — stateless,
      fail-soft, mirrors DisplayClient pattern). Compile pending; flash
      pending Suti's go-ahead. 2026-04-25.
- [x] **Cycle 2** — substrate glyph field + RESTING composition.
      First visual change. IBM Plex Mono Regular/Medium added via
      gfonts. Display lambda rewritten: 44×16 = 704 cells of standard
      ramp, ~50% density, ~600ms drift per cell (scaled by
      restlessness), heart pulse ±1 ramp step on a period stretched by
      sleep_pressure (0.0→1.2s, 0.3→2.0s, 0.5→3.5s, 0.85+→5.0s).
      Center clear-zone holds NARADA wordmark (28px Medium) + thin
      mood-tinted line + presence dot bottom-right (visible when
      attention != inward). Idle micro-sparkle every 30s. Mood tint
      computed via bilinear blend of GREY-TEAL/GOLD/ROSE/VIOLET
      corners. Backwards-compat `set_status`/`set_thought` services
      kept as visual no-ops; deprecate after Cycle 3. Compiled, OTA
      flashed at 22:31 AEST, proprioception verified clean. 2026-04-25.
- [ ] **Cycle 3** — THINKING + WORKING activity modes.
- [ ] **Cycle 4** — signals + DELIGHTED.
- [ ] **Cycle 5** — LISTENING + SPEAKING (karaoke + waveform). Touch
      contract (noticed + love). Voice character experiment runs in
      this window.
- [ ] **Cycle 6** — DREAMING + mood-tinting + transition polish.

### Cleanup backlog (not blocking)

A future BUILD cycle should:
- Delete `src/svapna/embodiment/esp_client.py`, `__init__.py`,
  `tests/test_esp_client.py` (redundant — superseded by
  `svapna.body.expression`).
- Fix `src/svapna/body/__main__.py` — `FIRMWARE_DIR` still points at
  `firmware/esphome` (stale; should be `embodiment/firmware`). Build
  and deploy via the body CLI will fail until fixed.
- Remove or repurpose `embodiment/assets/README.md` placeholder.
- After Cycle 3 verifies the layer API replaces the legacy strings
  end-to-end, delete the `set_status` / `set_thought` services and the
  `heartbeat_status_str` / `current_thought_str` globals + their
  proprioception sensors. Also drop the daemon's calls to those.

These don't block forward work and the redundant files don't actively
cause harm — they just duplicate what works.

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
