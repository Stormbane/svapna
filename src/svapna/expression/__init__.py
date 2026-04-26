"""Expression — the scene engine.

Architecture (see `embodiment/design/v2.0-indriyas-framework.md`):

  - bhumi   — world model (the metaphor under a scene). Examples:
              landscape, ufo_interior, dream_void, snake_blackhole,
              golden_idol_jupiter.
  - kala    — a coherent scene within a bhumi (RESTING, THINKING,
              SPEAKING, etc.).
  - sandhi  — transition between two kalas.
  - avatara — how Narada appears in a scene.

Cognition writes desired (bhumi, kala) state via the visual layer of
the v1.0 expression contract. The scene engine composes the active
kala (or sandhi if a transition is in flight) and emits drawing
commands to drishti (the display karmendriya).

Most kalas + bhumis live as substrate engines on the firmware (fast
path). Experimental scenes use the live-frame-push channel from the
desktop emulator.
"""
