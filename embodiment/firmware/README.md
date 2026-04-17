# embodiment/firmware/

ESPHome YAML configuration for the ESP32-S3-BOX-3 on Suti's desk.

## Purpose

This directory holds all firmware definitions for Narada's physical
embodiment device. ESPHome compiles these YAML files into firmware
images and flashes them over the network (OTA) or via USB.

## Device

- **Hardware**: ESP32-S3-BOX-3
- **Network**: 192.168.86.35 (verify on first cycle)
- **ESPHome version**: TBD — run `esphome version` on first cycle

## File naming convention

| File | Purpose |
|------|---------|
| `narada-base.yaml` | Base configuration: board, WiFi, logger, OTA, API |
| `narada-display.yaml` | Display package: OLED/LCD components, fonts, pages |
| `narada-voice.yaml` | Microphone + speaker pipeline (ESPHome VA components) |
| `narada-heartbeat.yaml` | REST endpoints consumed by the heartbeat system |
| `secrets.yaml` | Credentials (gitignored — copy from secrets.yaml.template) |

## REST endpoints (heartbeat integration)

The heartbeat system (`src/svapna/heartbeat/display.py`) currently
pushes state to the device. Future cycles will define these endpoints
here and wire them in `narada-heartbeat.yaml`:

- `POST /heartbeat` — cycle status, current desire topic, action type
- `POST /display` — arbitrary text/icon update
- `GET /status` — device health, uptime, last heartbeat timestamp

## Compiling and flashing

```bash
# From C:/Projects/svapna/
esphome compile embodiment/firmware/narada-base.yaml
esphome run embodiment/firmware/narada-base.yaml   # compile + OTA flash
```

Suti has authorized flashing. If the device bricks, it will be
replaced on return.
