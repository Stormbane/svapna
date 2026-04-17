# Embodiment — Current State

Living document. Every BUILD cycle reads this first, updates this last.

**Last updated**: 2026-04-18 by session-2026-04-18-coder-mode-setup

---

## Where we are

Phase 1 not yet started. The scaffolding exists (`embodiment/`,
`src/svapna/embodiment/`, ROADMAP.md, this file) but no firmware or
desktop integration code yet.

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

Phase 1.1 or 1.2 — either establish the template of CURRENT_STATE
update discipline (already done here) or investigate what firmware
is currently on the device.

## Recent cycles

(none yet — this is the seed)
