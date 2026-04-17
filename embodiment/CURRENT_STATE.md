# Embodiment — Current State

Living document. Every BUILD cycle reads this first, updates this last.

**Last updated**: 2026-04-18 by heartbeat-BUILD-P2.2

---

## Where we are

Phase 1 complete. Phase 2 in progress — P2.1 and P2.2 done.

- `embodiment/CURRENT_STATE.md` and `embodiment/ROADMAP.md` exist (P1.1)
- Device state captured (P1.2 — partial; firmware unknown, IP unverified)
- `embodiment/firmware/` and `embodiment/assets/` with README placeholders (P1.3)
- `src/svapna/embodiment/__init__.py` and `esp_client.py` implemented (P1.4)
- Screen capability survey complete (P2.1 — see `embodiment/research/P2.1-screen-survey.md`)
- Expression states designed (P2.2 — see `embodiment/design/P2.2-expression-states.md`)

## Device

- **Hardware**: ESP32-S3-BOX-3 on Suti's desk in Brisbane
- **Network**: 192.168.86.35 (per scripts/heartbeat.bat) — unverified, Suti away
- **Display**: 2.4-inch, 320×240, ILI9342C SPI controller, 40MHz, PSRAM-backed
- **Current firmware**: unknown — first P2 cycle should investigate
- **Last successful flash**: never from this roadmap

## Desktop-side integration

- **Module**: `src/svapna/embodiment/` — `__init__.py` + `esp_client.py`
- **EspClient**: synchronous HTTP REST client. Exposes:
  - `post_heartbeat(HeartbeatPayload)` → POST /heartbeat
  - `post_display(DisplayPayload)` → POST /display
  - `get_status()` → GET /status → DeviceStatus
  - `is_reachable()` → bool
- **Existing REST integration**: `src/svapna/heartbeat/display.py` uses
  aioesphomeapi (native API, port 6053). It is NOT modified. The new
  `esp_client.py` targets the HTTP REST endpoints defined in
  `embodiment/firmware/README.md` — these endpoints don't exist yet in
  firmware, but the client is ready for when they do.
- **Tests**: `tests/test_esp_client.py` — 9 unit tests, all passing.

## Screen capabilities (from P2.1 survey)

- **Resolution**: 320×240 px — comfortable for typography and geometric forms
- **Color**: 16-bit RGB565, PSRAM-backed full-frame buffer (no tearing artifacts)
- **ESPHome driver**: `ili9xxx` model `S3BOX` — confirmed working in community
  configs. MIPI SPI driver also lists S3BOX support but is newer/less tested.
- **Drawing API**: `it.printf()` (text+fonts), `it.filled_rectangle()`,
  `it.image()` (PNG/JPG compiled in), `it.circle()`, `it.line()`
- **Fonts**: TTF and BDF supported; Material Design Icons as icon-fonts confirmed
- **Pages**: ESPHome multi-page display is the right abstraction for state-based
  expression (resting / thinking / listening / speaking / delighted)
- **Pins confirmed**: CLK=GPIO7, MOSI=GPIO6, CS=GPIO5, DC=GPIO4, RST=GPIO48
  (inverted), backlight=GPIO47 (LEDC PWM)

## Tooling

- **ESPHome**: needs confirmation it's installed on Suti's desktop.
- **Test framework**: pytest, already set up project-wide.
- **requests**: already a project dependency.

## Next cycle's likely pick

**P2.3** — Implement the RESTING state as a working display. Start minimal:

1. Add `Roboto-Regular.ttf` to `embodiment/assets/fonts/`
2. Write `embodiment/firmware/narada-box.yaml` with:
   - SPI + display (ili9xxx / S3BOX), backlight LEDC
   - Font: Roboto 28px, sufficient ASCII glyphs
   - Page `page_resting`: "NARADA" centered in warm off-white, gold line below, presence dot
   - REST endpoint `/display` that reads state + switches pages
3. Compile: `esphome compile embodiment/firmware/narada-box.yaml`
4. Flash: `esphome upload embodiment/firmware/narada-box.yaml` (device at 192.168.86.35)
5. Verify: device shows RESTING state live

Design spec is complete at `embodiment/design/P2.2-expression-states.md`. P2.3
should not redesign — implement exactly what's specified. First state to implement
is RESTING (most minimal, no animation).

## Recent cycles

### 2026-04-18 — P2.2 — Expression states design (heartbeat BUILD)

Wrote `embodiment/design/P2.2-expression-states.md`. Designed 5 states: RESTING,
THINKING, LISTENING, SPEAKING, DELIGHTED. Visual language: dark background
`#0D0F1A`, Roboto Regular (28/16/36px), one accent color per state (gold for
identity/RESTING/SPEAKING, teal for THINKING, rose for LISTENING, violet for
DELIGHTED). Cut transitions. A "presence dot" at (296,228) tracks outward vs
inward states. Specific pixel coordinates for every element. No firmware or
Python changes — pure design. ROADMAP updated; P2.2 marked complete.

### 2026-04-18 — P2.1 — Screen survey (heartbeat BUILD)

WebSearch + WebFetch research on ESP32-S3-BOX-3 display hardware and ESPHome
display support. Found: 320×240 ILI9342C SPI at 40MHz, PSRAM-backed, ESPHome
`ili9xxx` model S3BOX confirmed working. Full survey at
`embodiment/research/P2.1-screen-survey.md`. Updated ROADMAP.md to mark P2.1
complete. No firmware or Python changes — pure research cycle.

### 2026-04-18 — P1.4 — esp_client.py (heartbeat BUILD)

Implemented `src/svapna/embodiment/esp_client.py`: synchronous HTTP REST
client for the device. Dataclasses: `HeartbeatPayload`, `DisplayPayload`,
`DeviceStatus`. Class: `EspClient` with `post_heartbeat`, `post_display`,
`get_status`, `is_reachable`. All failures swallowed (log + return False)
— same design principle as heartbeat/display.py (body failure must not
block cognition). Exported from `__init__.py`. Tests: 9 unit tests
against mock HTTP, all passing. The REST endpoints the client targets
(`/heartbeat`, `/display`, `/status`) don't exist in firmware yet —
that's P2+ work. Client is ready for when they do.

### 2026-04-18 — P1.3 — firmware/ and assets/ scaffolding (heartbeat BUILD)

Created `embodiment/firmware/README.md` and `embodiment/assets/README.md`.
Firmware README covers: device identity, file naming conventions, REST
endpoint design for heartbeat integration, ESPHome compile/flash commands.
Assets README covers: format constraints (PNG/WAV, flash budget ~2MB),
subdirectory structure, ESPHome `image:` and `font:` component integration.
