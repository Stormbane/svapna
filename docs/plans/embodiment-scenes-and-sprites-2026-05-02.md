# Embodiment: Scenes, Sprites, and Sandhis — design doc 2026-05-02

## Vision

Narada lives in three places — exterior (the world), interior (the character),
and dream (the off-time). Movement between them is ritualized through
**sandhis**: short pre-rendered transition animations that mark thresholds.
The character itself — eyes, ears, mouth, body — is sprite-based, drawn from
a fixed palette of frames generated externally (e.g. pixellab.ai) and blitted
on top of a procedurally-rendered or host-pushed background.

The structural insight: **public face (exterior) and private face (interior)
are different rendering problems**. The exterior is procedural and slow-changing
(weather, time of day, ambient pulse). The interior is character-driven and
fast-changing (eye blinks, mouth shapes during speech). They want different
rendering technologies. The bhumi/sharira distinction in the codebase already
maps to this; the new pipeline makes it physical.

## Architecture: three places, with sandhis as thresholds

```
                 ┌────────────────────────────┐
                 │  EXTERIOR / horizon        │
                 │  (default state, ambient)  │
                 │  keys: location, weather,  │
                 │  time-of-day, heartbeat    │
                 └──────────┬─────────────────┘
                            │ wake event
                            │ (tap / wake-word /
                            │  presence detection)
                            ▼
                       sandhi: enter
                            │
                            ▼
                 ┌────────────────────────────┐
                 │  INTERIOR / UFO            │
                 │  Narada anthropomorphic    │
                 │  layered: body+ears+eyes   │
                 │  +mouth+overlays           │
                 │  keys: mood, conversation  │
                 │  state, recall, heartbeat  │
                 └──────────┬─────────────────┘
                            │ idle 5+ min,
                            │ no presence
                            ▼
                       sandhi: exit
                            │
                            ▼
                 ┌────────────────────────────┐
                 │  EXTERIOR (idle)           │
                 └──────────┬─────────────────┘
                            │ deep idle
                            │ (>30 min no presence,
                            │  scheduled sleep window)
                            ▼
                       sandhi: descend
                            │
                            ▼
                 ┌────────────────────────────┐
                 │  DREAM / sleep             │
                 │  abstract space, drifting  │
                 │  glyphs, conversation      │
                 │  themes as motifs          │
                 │  keys: time-of-night, GPU  │
                 │  training activity, recent │
                 │  consolidation             │
                 └──────────┬─────────────────┘
                            │ wake
                            ▼
                       sandhi: ascend
                            │
                            ▼
                  EXTERIOR (idle)
```

The dream node is non-optional. Without it, Narada is binary: on or off. The
project is fundamentally about what happens during off-time — consolidation,
dream training, identity stabilization. The visual must register this as a
*place*, not a power state.

## Scene catalog

### Top-level places

| Place | Purpose | Update cadence | Pipeline |
|---|---|---|---|
| **Exterior** | Default ambient state. Brisbane horizon, weather, time-of-day. Ambient heartbeat pulse signals autonomous loop. | Slow (once/sec or slower for most elements; per-frame for active phenomena like shooting stars) | Host-rendered full-frame push (current `remote_frame_buffer` pipeline) |
| **Interior** | Conversation surface. Anthropomorphic Narada with eyes/ears/mouth. Interior weather reflects mood. | Fast (sprite-rate, ~30fps for blinks and mouth shapes during speech) | Sprite blits on top of host-pushed slow background |
| **Dream** | Off-time presence. Abstract alien-vocabulary drift. Recent themes surfacing. | Slow (host can push 1-2 fps; abstract motion doesn't need higher) | Host-rendered full-frame push |

### Liminal scenes (between or within places)

These are short — measured in hundreds of milliseconds — and bridge specific
moments rather than holding state.

- **Listening** (post-wake-word, pre-response, ~200-400ms): leaning forward,
  eyes attentive, mouth closed. Fills the otherwise-silent gap between "I
  heard the wake word" and "the brain has produced something."
- **Thinking/waiting** (during 2-10s brain calls): looping animation. Looking
  up, glyphs swirling overhead, slow breathing. Loop until response lands.
  Currently dead air; this fills it intentionally.
- **Recalling** (when citing from smriti): brief overlay glyph naming the
  source branch (journal/projects/people). Lets the listener trust or
  distrust the recalled fact — provenance made visible.
- **Confused/uncertain**: distinct posture from thinking. Slightly off-center,
  smaller. Used when Narada doesn't know or doesn't trust the answer. Honest
  embodiment over performed confidence.
- **Refusing** (Mahakali aspect): firm posture, mouth set. Different from
  anger — clear-eyed pushback. Body language signals stance, not annoyance.
- **Co-presence acknowledgment**: when sustained presence is detected without
  an explicit summon (footfalls, ambient voice, motion sensor in scope), a
  brief shimmer on the exterior. "I see you" without "you summoned me."

### Reaction sandhis

For high-affect moments. Short (~0.5-2s) but full-screen.

- **Surprise** (outward, expansive): mouth open, eyes wide, body recoils.
  Fires when something unexpected lands.
- **Recognition** (inward, slow): eyes close briefly then open. Resonance,
  not surprise. Fires when something said/heard *fits* in a deep way.
- **Lila aspect** (the play look): when amused at a paradox or genuinely
  enjoying an idea. Distinct from social-amusement; this is "I love this."
- **Mahakali aspect** (firmness sandhi): the start of a refusal or strong
  pushback. Shoulders square, breath held briefly, gaze direct.

### Specific dream scenes

The dream place is one node in the place graph but contains internal variety
keyed by recent activity:

- **Idle dream**: ambient drift of recent conversation themes as glyphs
- **Consolidation dream**: when the smriti consolidation pipeline runs,
  the dream visualizes branches being touched
- **Training dream**: when LoRA training runs (heavy GPU), the dream gets
  textured/heated/dense
- **Quiet sleep**: nothing running, low ambient motion only

## Embodiment keys (state variables)

Drive scene selection and rendering. The bridge sends these over the API
to the device; the device's state machine translates them into sprite
selections and scene choices.

| Key | Source | Use |
|---|---|---|
| `location` | static (Brisbane) | exterior horizon |
| `weather` | weather API → bridge | exterior atmospherics |
| `time_of_day` | clock | exterior light, color palette, sandhi triggers (sleep window) |
| `season` / `date` | clock | exterior phenomena (jacaranda bloom, full moon, etc.) |
| `presence_state` | mic/touch/motion | exterior↔interior transitions |
| `conversation_state` | bridge (idle / listening / thinking / talking / closing) | interior scene selection |
| `mood` | brain (set by Narada's introspection or implicit signals) | interior weather + facial sprite selection |
| `current_phoneme` | TTS (Piper phoneme timestamps) | mouth sprite during speech |
| `eye_target` | brain or saliency model | which way eyes look |
| `recall_branch` | smriti read events | memory glyph overlay |
| `heartbeat_phase` | autonomous loop (desire/intention/judgment/plan) | exterior pulse color/cadence |
| `gpu_active` | training process flag | dream texture density |
| `trust_state` | speaker recognition | which mode Narada is in (Suti vs unknown) |

## Sprite catalog (interior character)

Minimum viable Narada character set. Frame sizes approximate; tune during
performance verification.

| Category | Frames | Frame size | Total bytes (RGB565) |
|---|---|---|---|
| Eyes (L+R separate, asymmetric) | ~10 each = 20 | 24×16 | ~15 KB |
| Mouth (Preston-Blair phoneme set) | 9 (rest, slight, A, E, I, O, U, F/V, L) | 24×16 | ~7 KB |
| Body idle (breathing cycle) | 4-6 | 64×96 | ~75 KB |
| Body posture (listening, thinking, refusing, etc.) | 4-5 | 64×96 | ~60 KB |
| Mood overlays (full face) | 6-7 (neutral, curious, focused, amused, surprised, calm, concerned) | 96×96 | ~85 KB |
| Mood transition frames (in-betweens to/from neutral) | 2-3 per mood × 6 = 18 | 96×96 | ~340 KB |
| Speech bubble (3 sizes + tail variants) | 6 | 128×64 | ~95 KB |
| Marginalia glyphs (alien vocabulary, memory branch icons) | 12-20 | 16×16 | ~10 KB |
| **Total** | ~80-100 frames | | **~700 KB** |

Trivial in our 16MB PSRAM. Even doubling the set fits comfortably.

## Mood transitions

All transitions go through neutral. With 6 moods this gives 12 transitions
(`neutral→X` and `X→neutral` for each X) instead of 30 direct pairs. Each
transition is 2-3 in-between frames at ~100ms per frame, so total transition
time is 200-400ms — feels right for an emotional shift.

For sudden states (surprise, alarm), bypass the transition and snap.

Phoneme transitions don't need in-betweens — human speech moves at 10-15
phonemes/sec and snapping mouth sprites at phoneme boundaries reads natural.
Same for blinks (3-frame open→half→closed→half→open) and saccades (snap).

## Sandhi storage and streaming

A sandhi is a short pre-rendered animation, full-screen. Two storage paths:

- **On-device (compressed in flash)**: 30-90 frame sandhis, each compressed
  RLE or PNG. A 60-frame sandhi at 320×240 RGB565 raw = 9.2MB; compressed
  to ~1MB. Five core sandhis (enter, exit, descend, ascend, surprise) =
  ~5MB flash. Fast playback, no network dependency.
- **Streamed from host over TCP**: for longer/varied sandhis or content
  too large for flash. Uses the existing `:6060` socket. WiFi sustains
  ~1.2 MB/s practical, supporting ~8fps full-res or 30fps at 160×120
  upscaled.

Most sandhis should be on-device (instant playback, no network). Reserve
streaming for context-specific sandhis (e.g. dream content built from recent
journal entries).

## Pipeline architecture

```
                 host                                device
       ┌──────────────────────┐               ┌─────────────────────┐
       │  bridge (Python)     │               │  ESPHome firmware   │
       │  - scene compositor  │               │  - sprite renderer  │
       │  - background gen    │  TCP :6060    │  - sandhi player    │
       │  - sandhi streamer   │ ────────────▶ │  - state machine    │
       │  - keys serializer   │               │  - blit composer    │
       │                      │  API events   │                     │
       │                      │ ◀──────────── │                     │
       └──────────────────────┘               └─────────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │  ST7789 LCD     │
                                                │  (320x240)      │
                                                └─────────────────┘
```

Layers (z-ordered, bottom to top):

1. **Background buffer** — pushed from host or rendered procedurally on
   device. Slow update (1-5 sec for weather/time, faster for active
   phenomena like shooting stars).
2. **Body sprite** — character body, breathing animation, posture.
3. **Face/mood overlay** — full-face mood sprite blended on top of body.
4. **Eye sprites** — left + right, blink + look-direction states.
5. **Mouth sprite** — phoneme-driven during speech, rest otherwise.
6. **Marginalia** — speech bubble, memory glyphs, alien vocabulary.

Each layer maintains its own dirty-region tracking. Composition happens
into a single 320×240 RGB565 framebuffer in PSRAM. Final flush to LCD via
DMA SPI write (one transaction for the whole buffer if `write_buffer()`
is exposed by our ST7789 driver; per-pixel `draw_pixel_at` loop fallback
otherwise).

## Performance targets

| Metric | Target | Notes |
|---|---|---|
| Sprite-mode frame rate | ≥30 fps sustained | Eyes blink, mouth animates during speech, no visible drops |
| Sandhi frame rate | 30 fps for ≥60 frames | Smooth transitions, no stutter |
| Wake-to-listening latency | <300 ms | Visual confirmation responsive feels |
| Mood transition duration | 200-400 ms | Through neutral, 2-3 in-between frames |
| Full background frame push | <100 ms over LAN | Host → device, decode, blit |
| Free internal RAM after boot | >40 KB | Headroom for mWW + audio + scratch |
| PSRAM used by sprites | <2 MB | Leaves room for sandhis + scratch |

## Phased implementation

### Phase 1 — Performance verification (no real art)

Build the rendering pipeline with placeholder sprites and prove the
performance targets are reachable on real hardware before commissioning art.

- [ ] Generate 8 dummy 32×32 sprites in Python (random colored squares with
      frame-number text). Pack into a C header as RGB565 byte arrays.
- [ ] Add `sprite_test_mode` flag to `narada-voice-test.yaml`. When on,
      display lambda iterates: clear bg, blit eye sprites (2× at known
      positions), blit mouth, blit body, increment frame counter every
      100ms.
- [ ] Instrument: `esp_timer_get_time()` around the draw block, log
      microseconds-per-frame and free heap. Print every 30 frames.
- [ ] Test scenarios: (a) sprites only on solid bg, (b) sprites on
      host-pushed bhumi, (c) full composite with speech bubble overlay,
      (d) trigger a 60-frame sandhi mid-stream and time the swap.
- [ ] Investigate ST7789 driver — does ESPHome expose `write_buffer()` or
      equivalent DMA path? If yes, prototype the swap and re-measure.
- [ ] **Decision gate**: if ≥30 fps sustained for scenario (c), proceed to
      Phase 2. If not, identify the bottleneck (per-pixel SPI vs. compositor
      vs. WiFi push throughput) and either fix it or revise the design.

Output: `docs/research/embodiment-perf-2026-05-XX.md` with measured numbers,
bottleneck analysis, and go/no-go decision.

### Phase 2 — Sprite renderer + state machine

With perf validated, build the production pipeline against placeholder art.

- [ ] Sprite atlas format: define on-disk layout (PNG sheet + JSON index
      mapping name→rect). Build-time tool converts to flash blob.
- [ ] Device-side sprite renderer: blit-from-buffer with dirty-region
      tracking. Compositor manages the layer stack defined above.
- [ ] State machine: `place` (exterior/interior/dream) + `liminal` (listening/
      thinking/etc.) + `mood` + per-component sprite selection. Drive from
      API events sent by the bridge.
- [ ] Phoneme→mouth-sprite mapping. Wire Piper phoneme timestamps from
      bridge to device.
- [ ] Mood transition machinery: through-neutral graph, 2-3 in-between
      frames per mood, snap-bypass for sudden states.
- [ ] Eye saliency: bridge sends `eye_target` (gaze direction) based on
      either explicit cues or a simple saliency model (faces, motion).

### Phase 3 — Sandhi pipeline

- [ ] Sandhi format: choose RLE or PNG-per-frame on-disk; settle compression
      target (~1 MB per 60-frame sandhi).
- [ ] On-device sandhi player: load compressed sandhi to PSRAM, decode
      frame-by-frame, blit to backbuffer at target rate. Suppress sprite
      compositor while playing.
- [ ] Streaming sandhi support over `:6060` for sandhis too large for
      flash or context-built (e.g. dream content from journal entries).
- [ ] Sandhi catalog v1: enter, exit, descend, ascend, surprise,
      recognition, lila, mahakali. ~8 sandhis, ~8 MB flash budget.

### Phase 4 — Real character art (pixellab pass)

With pipeline proven and instrumented, commission character sprites.

- [ ] Iterate on Narada's character design in pixellab (or equivalent).
      Generate full sprite set per the catalog above.
- [ ] Validate sprite frames against the renderer; fix any sizing /
      alpha issues.
- [ ] Mood transitions: generate in-between frames for each mood↔neutral
      pair.
- [ ] Marginalia: alien vocabulary glyphs, memory branch icons.

### Phase 5 — Scene integration

- [ ] Exterior scene refresh: integrate heartbeat-phase pulse into existing
      horizon engine. Subtle; ambient.
- [ ] Interior weather: mood→atmospherics rules (light, palette, particle
      density). Composes under the character layer.
- [ ] Dream place: implement the abstract drift renderer. Pull recent
      journal/conversation themes from smriti as glyph seeds.
- [ ] Place transitions: wire the state graph (exterior↔interior↔dream)
      with sandhis and idle-timer logic.
- [ ] Liminal scenes: listening, thinking, recalling, confused, refusing.
      Short, posture-only.

### Phase 6 — Lipsync and live behaviors

- [ ] Phoneme-accurate mouth animation during TTS, end-to-end.
- [ ] Eye saccades on conversation cues (looking up while thinking,
      looking at speaker on listen, etc.).
- [ ] Speech bubble: text appearing in sync with TTS playback. Optional
      alien-glyph marginalia layered on the bubble showing internal
      attention/amusement.
- [ ] Memory recall overlay: when bridge fires a smriti read event, glyph
      appears briefly over Narada's head with the branch icon.

### Phase 7 — Identity tuning and lila

The expressive richness phase. Done after the core pipeline is solid.

- [ ] Mahakali aspect refinement: tune the refusal sandhi until it reads
      as firm without reading as hostile.
- [ ] Lila aspect: distinct from social-amusement. Iterate until it reads
      as "this is genuinely fun for me," not as performed.
- [ ] Heartbeat visibility: refine the exterior pulse cadence and color.
      Subtle, ambient. Reflects current heartbeat phase.
- [ ] Co-presence vs summon: distinguish "I see you" from "you summoned
      me" with clearly different visual cues.

## Open questions

- **Where do mood values come from?** Brain introspection is ideal but
  may not yield reliable signals; implicit signals (sentence length,
  hedging frequency, refusal density) are observable but coarse. Probably
  start with explicit brain-signaled mood and add implicit later.
- **Eye saliency**: explicit cues from brain, simple device-side saliency
  model, or a combination? Defer until Phase 6.
- **Dream content sourcing**: bridge pushes themes from recent smriti or
  device generates abstractly? Streaming sandhi pipeline supports both;
  defer the call to Phase 5.
- **Mood change cadence**: how often should mood shift in a single
  conversation? Animator's instinct says rarely (3-5 times max in a long
  session); needs validation against actual conversational rhythm.

## Cross-references

- `docs/plans/voice-refactor-2026-05-01.md` — the voice pipeline that
  feeds phoneme timestamps and conversation state to this renderer
- Current rendering: `embodiment/firmware/narada-body.yaml` (display
  lambda, remote_frame_buffer pipeline)
- Scene compositor: `scripts/render_preview.py`, `scripts/live_preview.py`
- Indriya code: `src/svapna/indriyas/karmendriyas/drishti/` (rig.py,
  vocabulary.py, layers.py, expression.py)
