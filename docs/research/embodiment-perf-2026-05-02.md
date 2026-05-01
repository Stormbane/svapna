# Embodiment perf — Phase 1 measurements (2026-05-02)

**Decision: GO for Phase 2.** The headline target (scenario C, full
composite) sustains **47.5 fps** with 80 KB of internal-RAM headroom.
Scenarios B and D reveal optimization opportunities for later phases
but do not gate progress.

Hardware: ESP32-S3-Box-3, 16 MB flash, 16 MB octal PSRAM @ 80 MHz, CPU
@ 240 MHz. Firmware: `embodiment/firmware/narada-sprite-test.yaml`,
ESPHome 2026.3.3, esp-idf framework. Display: ili9342c (`model: S3BOX`)
on SPI bus at 40 MHz. Frame target: 33 ms (30 fps) via
`update_interval: 33ms`.

## Numbers

Each scenario sampled over multiple 30-frame batches; values are stable
across batches. `avg_lambda_us` is the time inside the YAML lambda
(per-pixel composite work, before the SPI flush). Effective fps is
`1e6 / avg_lambda_us` — what we'd hit if the lambda were the only
constraint. Actual frame cadence is also gated by the 33 ms
`update_interval`, so when the lambda is faster than 33 ms we land at
30 fps; when slower, fps drops to whatever the lambda allows.

| Scenario | Description | Lambda µs | Effective fps | Frame cost |
|----------|-------------|-----------|---------------|------------|
| A (s=0)  | Solid black bg + 4 sprites | 11,820 | **84.6** | 11.8 ms |
| B (s=1)  | Host-pushed bhumi + 4 sprites | 96,500 | **10.4** | 96.5 ms |
| C (s=2)  | Full composite — bg fill + body + 2 eyes + mouth + speech bubble | 21,030 | **47.5** | 21.0 ms |
| D (sandhi) | Full-screen tiled sprite blit (60 frames timed end-to-end) | 205,000 | **4.9** | 205 ms |

Heap stayed flat throughout the sweep:
- `free_internal`: 224–225 KB
- `free_dma`: 216–217 KB
- `largest_internal`: 213 KB

(For reference: voice firmware leaves only ~12 KB of internal heap
free after mWW boot. The display-only firmware has ~18× more headroom
because no mWW tensor arena and no I2S DMA buffers.)

## What this means for each scenario

**A — solid bg + 4 sprites: 84.6 fps.** The lambda is doing 4 ×
1024 = 4,096 pixel writes plus a `fill(black)` (76,800 pixel writes).
At 11.8 ms that's a per-pixel cost of ~146 ns including the
RGB565→Color→RGB565 round-trip the YAML lambda forces. We're
effectively bottlenecked by `update_interval` (33 ms) here, not by
draw work — there's headroom to burn.

**B — host bhumi + 4 sprites: 10.4 fps.** Significant drop. The
lambda is now also doing 76,800 pixel writes from the PSRAM bhumi
buffer, each going through `Color()` construction. PSRAM read at
~80 MB/s is fine — the cost is the per-pixel CPU work, not the
memory. Two paths if we ever need bhumi at 30 fps:

  1. Add a `write_buffer()`-style path that pushes the bhumi buffer
     directly into the framebuffer with `memcpy` (skipping
     `Color()`/RGB565 round-trip). ~10× speedup expected.
  2. Treat bhumi as static — load once on scene entry, don't redraw
     per frame. Most bhumis don't need per-frame updates. The
     compositor only marks the body region dirty.

**Phase 3 picks one or both of these.** For Phases 2 & 4 we don't
need bhumi at 30 fps; static bhumi (path 2) is sufficient.

**C — full composite: 47.5 fps.** This is the headline result. The
33 ms `update_interval` would cap us at 30 fps even if we could go
faster, but having 12 ms of headroom (33 − 21) means jitter from the
API stack, WiFi, or extra animation layers won't push us off target.

**D — sandhi (full-screen tiled): 4.9 fps.** Worst-case scenario
gives 200 ms per frame — 60 frames took 12.3 s wall-clock. Two factors
compound here:
  - **76,800 pixel writes per frame** (10× a sprite blit), all going
    through the per-pixel `draw_pixel_at` path.
  - **Full-frame dirty rect** forces a 150 KB SPI flush every frame.
    At 40 MHz that's ~30 ms of pure SPI bandwidth.

Sandhi is the sub-system Phase 3 needs to redesign anyway:
pre-rendered, RLE- or PNG-compressed frames decoded into the
framebuffer with `memcpy`-style blits, not 76,800 individual
`draw_pixel_at` calls. The 30 ms SPI floor is unavoidable for
full-frame swaps but gives us a target — sandhi at 30 fps means lambda
time has to be <3 ms, achievable with direct buffer writes.

For Phase 2 we accept that any sandhi triggered today plays at ~5 fps.
That's fine for testing the state machine; aesthetic sandhis come in
Phase 3.

## Bugs found during Phase 1

1. **`alloc_bhumi` leaked PSRAM.** Original YAML had
   `interval: 100ms / startup_delay: 2s` as the entry point; the
   `static bool done` guard was in the *next* lambda, not in the
   `alloc_bhumi` script. Result: 150 KB allocated per tick until
   PSRAM ran out (~10 s), then a flood of "alloc failed" errors.
   Fix: idempotency check inside the script (`if (id(bhumi_buffer) !=
   nullptr) return`) plus moved the trigger into `esphome.on_boot`.

2. **`esp_timer_get_time()` not in ESPHome lambda includes.** Tried
   it for higher-precision timestamps; compile failed. Switched to
   ESPHome's `micros()` (uint32_t, wraparound-safe across our short
   measurement windows).

3. **Initial flash was the wrong YAML.** The device hostname stayed
   `narada-voice` after a reflash that was supposed to land
   `narada-sprite-test`. The `services advertised:` debug print
   in the control script caught it (`['trigger_listen']` not
   `['set_scenario', 'trigger_sandhi']`). Worth keeping that print —
   it would have saved time on the first flash too.

4. **No `ota:` block in the test YAML.** First flash had to be USB.
   Adding `ota: - platform: esphome` lets us iterate over WiFi
   thereafter.

## Next (Phase 2)

The Phase 2 scope (sprite renderer + state machine, phoneme→mouth
mapping, mood transitions) is unblocked. The numbers also tell us
what to budget:

- **Per-frame composite**: ~21 ms today, ~12 ms headroom. Adding
  2-3 layers (mood overlay, marginalia) costs ~1 ms per layer at
  current per-pixel speed; we have room.
- **Phoneme rate**: Piper produces ~30 phonemes/sec; mouth shape
  changes at <33 ms cadence are imperceptible — current 47.5 fps
  composite handles this without strain.
- **Bhumi strategy**: implement path 2 (static bhumi blitted once
  on scene entry, not per frame). Phase 2 should not depend on
  per-frame bhumi.

Decision gate: **GO**.
