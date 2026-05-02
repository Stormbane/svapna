# Embodiment Phase 3 — sandhi pipeline (2026-05-02)

A sandhi (Sanskrit: juncture, transition) is a full-screen
animation that bridges two scenes — say, exterior bhumi → interior
ufo. The full design vision is in
`docs/plans/embodiment-scenes-and-sprites-2026-05-02.md`. Phase 1
proved the obvious approach (per-pixel `draw_pixel_at` blit of every
sandhi frame) gets ~5 fps because the lambda spends ~200 ms per
frame. Phase 3 fixes that.

## Constraints

- **Frame size**: 320 × 240 × 2 bytes RGB565 = 153,600 bytes per
  uncompressed frame.
- **Target framerate**: 30 fps for sandhi playback. 60-frame sandhi
  = 2-second transition.
- **Flash budget for catalog**: ~8 sandhis at v1, with a hard ceiling
  around 8 MB total flash (we have 16 MB; need headroom for atlas,
  voice models, OTA partition).
- **PSRAM working set**: 16 MB. We can hold one full uncompressed
  sandhi (9 MB for 60 frames) easily, but multiple at once is
  questionable. Prefer streaming decode where possible.
- **Lambda budget per frame**: ~30 ms (we measured 30 ms as the
  lower bound for full-frame SPI flush at 40 MHz). Leaves ~3 ms for
  the lambda itself if we want 30 fps.

## Why per-pixel `draw_pixel_at` was slow

Phase 1 sandhi at 5 fps was ~200 ms per frame. The framebuffer is
in PSRAM but the per-pixel path goes:

  1. Read RGB565 from atlas pixels[]: 1 PSRAM read.
  2. Unpack to (r, g, b).
  3. Construct esphome::Color (compiler-inlined struct).
  4. ESPHome's `draw_pixel_at` → ili9xxx::draw_pixel_at_(x, y, color)
     → re-pack to RGB565 → write 2 bytes to framebuffer at
     PSRAM[y * width * 2 + x * 2] → update dirty rect.

That's ~146 ns per pixel × 76,800 pixels = ~11 ms theoretical floor,
but the actual cost includes the function-call overhead (no inlining
across the lambda → driver boundary) and the dirty-rect update on
every pixel.

The fix: bypass the per-pixel API and write the source frame straight
into the framebuffer with a single `memcpy`. The driver's framebuffer
is exposed as `narada_display->get_buffer()` (or similar — depends on
ESPHome version; the underlying `ili9xxx_display.cpp` keeps it as
`uint8_t* buffer_`). We can dirty-mark the whole screen with one call
afterward.

## Format options

### Option A — uncompressed RGB565

  - 153,600 bytes per frame × 60 = **9 MB per sandhi**.
  - Eight sandhis = 72 MB. **Doesn't fit flash.**
  - Decode cost: zero. Just `memcpy` from flash to framebuffer.
  - Verdict: too large for the catalog, but fine for a single
    streaming-from-host sandhi (Phase 3 #3) or for a single one-off
    test.

### Option B — RLE on RGB565

  - Run-length encode runs of identical pixels. Sandhi frames
    typically have large flat regions (a star field, gradients) so
    compression should be 5-10×.
  - Estimate: 1-2 MB per sandhi. **Eight = ~10-15 MB.** Tight but
    viable.
  - Decode cost: small. RLE decode into framebuffer is two reads +
    one fill loop per run. CPU-bound, not memory-bound.
  - Verdict: good for the catalog. Simple, fast, predictable.

### Option C — keyframe + delta (interframe compression)

  - First frame full RLE; subsequent frames XOR-delta against
    previous. Most sandhis change only in localized regions.
  - Could compress 5-20× over Option B.
  - Decode cost: higher — must decode previous frame to apply delta.
  - Implementation cost: high. Defer.
  - Verdict: not worth it for v1.

### Option D — PNG per frame

  - Reuse the atlas pipeline; each sandhi frame is one PNG.
  - PNG decode on-device: requires a PNG decoder (~10-30 KB code +
    runtime alloc). ESPHome has no built-in.
  - Verdict: not worth pulling in a PNG decoder when RLE works.

**Decision: Option B (RLE on RGB565).** Simple, predictable,
catalog fits flash.

## RLE format

Per frame:

  - 4 bytes header: width (uint16), height (uint16). Always 320 × 240
    for full-screen, but the header lets future small sandhis live
    in the same format.
  - Stream of runs:
    - 1 byte: run length (1-255). 0 = end-of-frame marker.
    - 2 bytes: RGB565 color value.

A worst-case frame (no runs, every pixel different) is 3 × 76,800 =
230 KB — bigger than uncompressed. The encoder detects this and
falls back to a "raw" mode flagged by run length 0xFF + remaining
pixel count. Rare in practice for sandhi-style frames; we accept
the encode-time complexity.

Per sandhi:

  - 8 bytes header: magic ('NARSANDH'), frame count (uint16), reserved.
  - Per-frame: 4-byte offset table.
  - Frame data concatenated.

## On-device player

`include/sandhi_player.h`:

```c++
class SandhiPlayer {
 public:
  void start(const SandhiAsset* asset);
  void stop();
  bool active() const;

  // Called from the display lambda. Pulls the next frame and writes
  // it into the framebuffer if it's time. Returns true when the
  // sandhi just ended this tick (so the caller can re-stage the
  // sprite compositor).
  bool tick(uint32_t now_us, uint8_t* framebuffer, size_t fb_len);
};
```

While `active()`, the regular layer compositor's `render()` is
short-circuited. The sandhi owns the framebuffer for its duration.

Frame cadence: each sandhi declares a target FPS (default 30) and
the player advances frames based on `now_us`.

## Bridge integration

Sandhis are triggered by API service:

```yaml
- service: trigger_sandhi
  variables:
    sandhi_id: int   # 0=enter_interior, 1=exit_interior, 2=descend, ...
```

The pipeline calls this at appropriate moments:
- On wake from cold (no recent activity): play `enter_interior`.
- On long idle: play `exit_interior` (back to bhumi/exterior).
- On surprise / sudden mood snap: play `surprise`.

Phase 3 v1 ships the format, player, one test sandhi (synthetic —
just colored frames so we can see it animate), and the API hook.
Sandhi catalog and the bridge timing rules are Phase 3 v2 (or wait
for real art in Phase 4).

## What lands in this commit

- Format spec (this doc).
- `scripts/build_sandhi.py` — encode tool. Reads a directory of PNG
  frames and writes a single `.sandhi` binary blob (RLE).
- `scripts/gen_test_sandhi.py` — generates a synthetic test sandhi
  (60 frames, color sweep) so we can verify the player without art.
- `embodiment/firmware/include/sandhi_player.h` — player class.
- `embodiment/firmware/include/sandhi_assets.h` — generated by
  `build_sandhi.py`, embeds the catalog as `static const uint8_t[]`.
- `narada-unified.yaml`: API service + display lambda sandhi hook.
- A measurement after wiring it up.

What does **NOT** land in this commit:

- Streaming sandhi over `:6060` (Phase 3 v2).
- Multi-sandhi catalog (Phase 4 — needs real art).
- Sprite-compositor suspend on sandhi entry — for now we just write
  the framebuffer directly while sandhi plays; the compositor's
  next render will repaint over it. That's fine for short sandhis.
