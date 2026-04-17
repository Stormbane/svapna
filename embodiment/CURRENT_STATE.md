# Embodiment — Current State

Living document. Every BUILD cycle reads this first, updates this last.

**Last updated**: 2026-04-18 by heartbeat-BUILD-P1.4

---

## Where we are

Phase 1 scaffolding complete. All four P1 items are done:
- `embodiment/CURRENT_STATE.md` and `embodiment/ROADMAP.md` exist (P1.1)
- Device state captured in this file (P1.2 — partial; firmware unknown, IP
  unverified, but documented honestly)
- `embodiment/firmware/` and `embodiment/assets/` with README placeholders (P1.3)
- `src/svapna/embodiment/__init__.py` and `esp_client.py` implemented (P1.4)

Ready to begin Phase 2 (screen expression).

## Device

- **Hardware**: ESP32-S3-BOX-3 on Suti's desk in Brisbane
- **Network**: 192.168.86.35 (per scripts/heartbeat.bat) — unverified, Suti away
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

## Tooling

- **ESPHome**: needs confirmation it's installed on Suti's desktop.
- **Test framework**: pytest, already set up project-wide.
- **requests**: already a project dependency (used by display.py).

## Next cycle's likely pick

**P2.1** — Survey what the ESP32-S3-BOX-3 screen can do: resolution,
refresh rate, ESPHome display component support. This is research only —
WebSearch + WebFetch, no device access needed. Write a summary artifact
and update ROADMAP with what's known.

Or, if Suti is back and the device IP is confirmed: verify device
reachability (`EspClient.is_reachable()`) and check what firmware is
actually running (curl the device, check ESPHome API port 6053).

## Recent cycles

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
Commit: `scaffold: add embodiment/firmware/ and embodiment/assets/ with README placeholders`.
