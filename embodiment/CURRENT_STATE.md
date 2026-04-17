# Embodiment — Current State

Living document. Every BUILD cycle reads this first, updates this last.

**Last updated**: 2026-04-18 by heartbeat-BUILD-P1.3

---

## Where we are

Phase 1 scaffolding partially complete. `embodiment/firmware/` and
`embodiment/assets/` now exist with README placeholders describing
intent, file naming conventions, format constraints, and ESPHome
integration patterns. No actual firmware YAML or asset files yet.

## Device

- **Hardware**: ESP32-S3-BOX-3 on Suti's desk in Brisbane
- **Network**: 192.168.86.35 (per scripts/heartbeat.bat) — verify on
  first cycle
- **Current firmware**: unknown (first BUILD cycle should investigate
  and document)
- **Last successful flash**: never from this roadmap

## Desktop-side integration

- **Module**: `src/svapna/embodiment/` — empty, needs `__init__.py`
- **Existing REST integration**: the heartbeat `display.py` sends to
  the device. `src/svapna/heartbeat/display.py` is the current client.
  Do NOT modify display.py in BUILD cycles — it's part of heartbeat
  infrastructure, not embodiment. Build alongside it in
  `src/svapna/embodiment/`, and once the new system is proven,
  migration of display.py can be proposed in a separate cycle.

## Tooling

- **ESPHome**: needs confirmation it's installed on Suti's desktop.
  First cycle: `esphome version` check.
- **Test framework**: pytest, already set up project-wide.

## Next cycle's likely pick

Phase 1.4 or 1.5 — create `src/svapna/embodiment/__init__.py` to
establish the Python module, or investigate current device firmware
(`esphome version`, ping 192.168.86.35, query device API if ESPHome
is already running on it).

## Recent cycles

### 2026-04-18 — P1.3 — firmware/ and assets/ scaffolding (heartbeat BUILD)

Created `embodiment/firmware/README.md` and `embodiment/assets/README.md`.
Firmware README covers: device identity, file naming conventions, REST
endpoint design for heartbeat integration, ESPHome compile/flash commands.
Assets README covers: format constraints (PNG/WAV, flash budget ~2MB),
subdirectory structure, ESPHome `image:` and `font:` component integration.
Commit: `scaffold: add embodiment/firmware/ and embodiment/assets/ with README placeholders`.
