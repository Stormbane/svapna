# Display DMA on the BOX-3 — what ESPHome already gives us

Phase 1 prep for the embodiment scenes/sprites work. The design doc
(`docs/plans/embodiment-scenes-and-sprites-2026-05-02.md`) flagged
"investigate ST7789 driver — does ESPHome expose `write_buffer()` or an
equivalent DMA path?" as an open question before committing to the
sprite pipeline. Answer: yes, transparently, and we don't need to
refactor anything to get it.

Citations are line numbers into ESPHome 2026.3.3 as installed at
`~/AppData/Roaming/Python/Python312/site-packages/esphome/components/ili9xxx/`.

## What the driver actually does

The `ili9xxx` platform (which `model: S3BOX` selects — the S3-Box-3 is a
4-wire SPI ILI9342C) keeps a full RGB565 framebuffer in PSRAM and tracks
a dirty rectangle per draw:

- `alloc_buffer_()` (`ili9xxx_display.cpp` ctor path) reserves
  `width * height * 2` bytes — 320×240×2 = 150 KB on the BOX-3, sitting
  in PSRAM.
- Every `draw_pixel_at(x, y, color)` call writes two bytes into the
  framebuffer and updates `x_low_/x_high_/y_low_/y_high_` (the dirty
  rect tracker, ~lines 176–200). No SPI traffic.
- The `update_interval` callback runs `update()` → `do_update_()` →
  the YAML `lambda:` (which calls `draw_pixel_at`/`fill`/etc.) → then
  `display_dirty_region_()`.
- `display_dirty_region_()` issues a single `set_addr_window_` followed
  by `write_array(buffer + y_low * width * 2, h * width * 2)` (~line
  256). That `write_array` is the DMA SPI transaction — esphome's SPI
  bus uses the IDF `spi_device_polling_transmit`/`spi_device_transmit`
  path which DMAs out of the supplied buffer.

So per-frame cost is:
- `lambda` body = pure RAM writes into the PSRAM framebuffer.
- One `set_addr_window_` (a few SPI bytes).
- One DMA `write_array` of the dirty rows only.

A scenario where only the eyes change writes ~64×32 px = 4 KB through
SPI; a full repaint pushes the whole 150 KB. At 40 MHz SPI clock
(`data_rate: 40000000` in our YAML) the theoretical floor is:

    150 KB × 8 / 40 Mbit ≈ 30 ms per full frame
     32 KB × 8 / 40 Mbit ≈  6.4 ms per partial frame (two-eye blink)

That is right at our 33 ms (30 fps) target for full repaints, so the
question Phase 1 actually has to answer is: **can we keep the dirty
rect small most of the time?** Sandhi (D scenario) is the worst case —
it deliberately repaints everything for 60 frames.

## What this means for sprite design

1. **Don't fight for a `write_buffer()` API.** We already have one,
   spelled `it.fill()` + `it.draw_pixel_at()` + `update_interval`. The
   per-pixel call cost is ~one C++ method dispatch + two byte writes,
   not an SPI round-trip. Profile before optimizing.

2. **Layout sprites near each other to keep dirty rows tight.** The
   tracker is a single rectangle, not a region list. Two eyes on
   y=80–112 plus a mouth on y=130–162 forces the flush to cover y=80
   through y=162 — 82 rows × 320 px = ~52 KB of SPI even though only
   ~5 KB of pixels changed. If we co-locate face elements vertically
   the savings stack.

3. **Static bhumi backgrounds are nearly free.** They don't change
   between frames, so they don't expand the dirty rect. The cost of a
   "rich" bhumi is one-shot blit on scene entry, not per-frame. The
   sandhi (full-screen swap) is where bandwidth bites.

4. **Speech bubble overlay = frequent partial repaints in one corner.**
   That's fine — pin it to a known rect (e.g., x=220–315, y=5–35) and
   the dirty tracker will keep flushes to ~6 KB per phoneme update.

## What Phase 1 still has to measure

The driver theory above is necessary but not sufficient. Things that
could still kill 30 fps in practice:

- **Per-pixel `Color()` construction in the YAML lambda.** Our blit
  loop does an RGB565 → Color(r,g,b) → back-to-RGB565 round-trip per
  pixel. The driver re-packs to RGB565 on store. That's three bit-shift
  triplets per pixel × 1024 pixels per sprite × 5 sprites = ~15K ops
  per frame. Probably fine on a 240 MHz S3, but worth measuring vs. a
  direct framebuffer poke if we miss target.
- **Dirty rect explosion** when sprites are spread across the screen.
  The numbers above show this matters — Phase 1 logs `dirty rect size`
  per frame so we can see it.
- **Lambda jitter from the API stack.** `update_interval: 33ms` is
  best-effort; if WiFi/RX bursts steal time, frames drop.
- **PSRAM-resident framebuffer read bandwidth.** Octal PSRAM at 80 MHz
  is ~80 MB/s theoretical; reading 150 KB to push out SPI is ~2 ms by
  itself. Already counted in the 30 ms full-frame budget but worth
  noting.

## The instrumented test firmware

`embodiment/firmware/narada-sprite-test.yaml` is set up to answer the
remaining questions:

- µs/frame for the lambda body (RAM writes only).
- µs/frame implicit in the `update_interval` cadence (we hit it or we
  don't).
- Free internal/DMA/largest-block heap, so we can see if the
  framebuffer + sprite header in flash are leaving us room for the
  rest of the firmware (mic/speaker/voice_assistant).
- Four scenarios sweeping sprite count, bhumi presence, full
  composite, and full-screen swap (sandhi worst case).

The decision gate stays: **scenario C ≥ 30 fps sustained → proceed to
Phase 2.** Numbers go in `docs/research/embodiment-perf-2026-05-XX.md`
once the firmware runs on hardware.
