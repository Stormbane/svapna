# Embodiment Phase 2 — design (2026-05-02)

Phase 1 (`docs/research/embodiment-perf-2026-05-02.md`) cleared the
go/no-go gate at 47.5 fps for the full composite. Phase 2 builds the
real renderer + state machine, still using placeholder art —
pixellab-generated sprites land in Phase 4.

This doc records the architectural calls we make as we build. It is
not a tutorial; later phases should be able to read this and know why
choices were made.

## Scope of Phase 2

From `.ai/todo.md`, Phase 2 consists of six bullets:

1. **Sprite atlas format** — PNG sheet + JSON index → flash blob
2. **Device-side sprite renderer** with layer compositor + dirty-region
   tracking
3. **State machine** — `place × liminal × mood` driving per-component
   sprite selection, fed by API events
4. **Phoneme → mouth mapping** — Preston-Blair 9-shape set, driven by
   Piper phoneme timestamps from the bridge
5. **Mood transitions** — through-neutral graph with in-betweens
6. **Eye saliency v1** — bridge sends explicit `eye_target`

This doc commits decisions for #1 and #2 (the foundation). #3–#6 each
get their own design note when their session starts.

## Atlas format

### Constraints

- **Flash-resident.** PSRAM is 16 MB but we don't want to load 700 KB+
  of sprites into RAM at boot. Atlases live in flash, accessed via
  `static const uint16_t[]`.
- **Per-frame indexing without parsing.** Lookup is `atlas[frame_id]`,
  not `find_by_name("eye_left_neutral_03")`. Names → frame_ids
  resolved at build time.
- **Variable sprite size.** A face with a large mouth and small eyes
  shouldn't pay for the largest sprite × N entries. Each frame
  carries `(w, h, x_offset, y_offset, *pixels)` so the compositor can
  blit at the right position relative to a logical anchor.
- **No alpha channel for v1.** Sprites are RGB565. A reserved
  "transparent" pixel value (`0xF81F` = magenta) is treated as
  pass-through during blit. Cheap, sufficient for placeholder; alpha
  comes in Phase 4 when we have real art.
- **Stable IDs.** Frame IDs are stable across builds for a given
  source so firmware doesn't have to rebuild when a single sprite is
  re-rendered. Achieved by sorting source files by name.

### File layout

Atlas source: `embodiment/sprites/<atlas_name>/`
  ├ `<atlas_name>.json`     — manifest: name, anchor convention, frames
  └ `<frame_name>.png`      — one PNG per frame (RGB or RGBA)

Manifest schema:

```json
{
  "name": "narada_face",
  "version": 1,
  "anchor": "top_left",   // or "center", "bottom_center"
  "frames": [
    {
      "name": "eye_left_neutral",
      "file": "eye_left_neutral.png",
      "tags": ["eye", "left", "mood:neutral"]
    },
    ...
  ]
}
```

The build tool sorts `frames` alphabetically by `name` before
assigning IDs, so adding a frame in the middle does shift IDs of
later frames — but firmware references frames by **C enum**, not by
raw integer, so a recompile is the only impact.

### Generated header

`embodiment/firmware/include/atlas_<name>.h`:

```c
#pragma once
#include <cstdint>

// Auto-generated. DO NOT EDIT.

enum NaradaFaceFrame : uint16_t {
  NF_EYE_LEFT_NEUTRAL = 0,
  NF_EYE_RIGHT_NEUTRAL = 1,
  NF_MOUTH_AA = 2,
  ...
  NF_FRAME_COUNT
};

struct AtlasFrame {
  uint16_t w;
  uint16_t h;
  int16_t  ox;       // anchor offset (logical to top-left)
  int16_t  oy;
  uint32_t pixel_offset;  // index into atlas_pixels[]
};

extern const AtlasFrame narada_face_frames[NF_FRAME_COUNT];
extern const uint16_t   narada_face_pixels[];
extern const uint32_t   narada_face_pixel_count;
```

The pixel pool is a single flat `uint16_t[]` shared across all frames
so we don't pay padding per frame and rodata-locality stays good.

### Build tool

`scripts/build_atlas.py <atlas_dir>` reads the manifest, loads each
PNG via Pillow, converts to RGB565 with magenta-as-transparent, sorts
by name, and emits the `.h` file. Idempotent — no-op if inputs haven't
changed (mtime check).

Phase 1's `gen_test_sprites.py` becomes a special case: it generates
PNGs into `embodiment/sprites/test_atlas/` then invokes
`build_atlas.py`. The two scripts share format.

## Device-side renderer

### Layer model

Five layers, composited bottom-up each frame:

  1. **Background** — solid color or static bhumi blit.
  2. **Body** — sprite at `body_anchor`, frame from current state.
  3. **Mood overlay** — optional; e.g., aura for joy, droop for
     melancholy.
  4. **Eyes** — left + right; each independently positioned by
     `eye_target`.
  5. **Mouth** — sprite at `mouth_anchor`, frame from phoneme.
  6. **Marginalia** — alien glyphs, memory icons, speech bubble.

Each layer queries the state machine for its current frame ID, then
blits via the atlas. Order is fixed.

### Dirty-region strategy

Phase 1 confirmed ESPHome's ili9xxx driver does dirty-rect SPI flush
for free. The compositor's job is to keep the dirty rect **small**:

- Maintain `prev_frame_id` per layer. If unchanged, skip the layer.
- When a layer changes, blit the new frame at `(layer.x, layer.y,
  frame.w, frame.h)` — overwriting the old. The dirty rect grows to
  cover that area.
- Background and bhumi are written **once** on scene entry, then never
  redrawn. The compositor only redraws layers above them when those
  layers change AND the area newly exposed by a smaller new frame is
  re-painted with the bhumi pixels at those coords.

That last point matters: if the mouth shrinks from `aa` (wide) to
`ee` (narrow), the area between old-mouth-edges and new-mouth-edges
must be re-painted. Two paths:
  - **Bounding box repaint.** Cheap: redraw the full bbox of the
    larger of (prev, new) frames using the underlying bhumi/body. If
    no bhumi, repaint the bg color. Costs one extra blit per layer
    change.
  - **Sprite differencing.** More efficient but complex; defer.

Phase 2 uses bounding-box repaint. Phase 3 revisits if frame budget
gets tight.

### Per-layer state

```
struct LayerState {
  uint16_t current_frame;    // FRAME_NONE = invisible
  uint16_t prev_frame;
  int16_t  x;                // anchor position
  int16_t  y;
  bool     dirty;
};
```

Compositor loop:

```
for each layer:
  if !layer.dirty: continue
  if layer.prev_frame != FRAME_NONE:
    repaint_under(layer.prev_frame at (x, y))
  if layer.current_frame != FRAME_NONE:
    blit(atlas[layer.current_frame] at (x, y))
  layer.prev_frame = layer.current_frame
  layer.dirty = false
```

`repaint_under` reads from the bhumi buffer (or the bg color if no
bhumi) for the bounding box.

### Blit path

Phase 1 showed that the per-pixel `Color()` round-trip costs ~146 ns
per pixel. For Phase 2 the renderer uses `it.draw_pixel_at(x, y,
Color(...))` because that's the supported API surface. We accept this
cost — at 47.5 fps with headroom, optimization is premature.

If/when frame budget gets tight, the path forward (deferred to Phase
3) is calling the lower-level driver buffer directly: ESPHome's
`ili9xxx_display_t` exposes the framebuffer pointer in some forks,
and we can write RGB565 directly without the Color() round-trip. We
won't go there until measurements demand it.

### Magenta-as-transparent

In the blit inner loop:

```c
uint16_t px = atlas_pixels[frame.pixel_offset + dy * frame.w + dx];
if (px == 0xF81F) continue;   // transparent
draw_pixel_at(x + dx, y + dy, rgb565_to_color(px));
```

One branch per pixel. Cheap. The atlas tool reserves 0xF81F (pure
magenta) as the transparent key — sprites that need true magenta map
it to the nearest non-key color (0xF83F).

## What lands in this commit

- `scripts/build_atlas.py` — atlas build tool.
- `embodiment/sprites/test_atlas/` — placeholder sprites in the new
  format (regenerated from the gen_test_sprites logic, but as PNG +
  JSON manifest).
- `embodiment/firmware/include/atlas_test.h` — generated.
- `embodiment/firmware/narada-embodiment.yaml` — first-cut Phase 2
  firmware: layer compositor, no state machine yet (state set by API
  service for now). Replaces narada-sprite-test for development;
  narada-sprite-test stays as the perf reference.
- This design doc.

What does **NOT** land in this commit:

- State machine driven by API events (next commit).
- Phoneme → mouth mapping (next commit; needs bridge work).
- Mood transitions (later — needs in-between frames).
- Eye saliency (later — needs bridge `eye_target` push).

## Open questions for later phases

- **Memory budget for atlas.** Real Phase 4 art at ~80 frames × 32×32
  RGB565 = 160 KB. ESP32-S3 has 4 MB internal flash; we have plenty.
  But variable-size frames (face: 32×32, body: 80×80, bhumi: 320×240)
  could push individual atlases to ~500 KB. Still fine.
- **Atlas streaming for sandhi.** Phase 3 problem. Sandhi frames are
  too big for flash if we want >2 of them; bridge streams over TCP.
- **Multiple atlases.** Face + body + marginalia probably want
  separate atlases so we can swap one without rebuilding all.
  Decision: yes, multiple atlases. Build tool takes one atlas dir per
  invocation.
