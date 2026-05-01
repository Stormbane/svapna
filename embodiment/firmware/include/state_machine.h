// Phase 2 state machine — converts state-level intent into layer
// commands on the compositor.
//
// The bridge (or, today, the API service drivers) talks to this in
// terms of *what Narada is doing* — the mood, whether Narada is
// speaking, the current phoneme, where the gaze is pointed — and the
// state machine translates those to layer frames + anchors.
//
// This keeps the bridge decoupled from sprite IDs. If we re-render
// the mouth set, the bridge doesn't change — only the
// phoneme→frame map below.
//
// Mood transitions (through-neutral, in-betweens) are not yet
// implemented — that lands in its own commit. For now mood snaps.
//
// Eye saliency is not yet implemented — gaze affects eye anchor by
// a small offset; the bridge supplies (gaze_x, gaze_y) directly.
//
// Design doc: docs/plans/embodiment-phase2-design-2026-05-02.md
#pragma once

#include "atlas_test_atlas.h"
#include "compositor.h"

namespace narada {

enum Mood : uint8_t {
  MOOD_NEUTRAL = 0,
  MOOD_CURIOUS = 1,
  MOOD_FOCUSED = 2,
};

// Preston-Blair-style placeholder set. Bridge-side phoneme inference
// maps Piper's IPA stream to this. See `phoneme_for_ipa()` (lives
// bridge-side, not here).
enum Phoneme : uint8_t {
  PH_REST = 0,
  PH_AA   = 1,   // open: father, hot
  PH_EE   = 2,   // smile: see, beat
  PH_OH   = 3,   // round: oh, go
  PH_MBP  = 4,   // closed: m, b, p
};

// Anchor positions for each layer in screen space, picked once and
// referenced by the renderer. Real Phase 4 art will likely shift
// these — keep them here so a single edit moves all frames.
struct Anchors {
  static constexpr int16_t BODY_X       = 160;
  static constexpr int16_t BODY_Y       = 180;
  static constexpr int16_t MOOD_X       = 160;
  static constexpr int16_t MOOD_Y       = 130;
  static constexpr int16_t EYE_LEFT_X   = 136;
  static constexpr int16_t EYE_RIGHT_X  = 184;
  static constexpr int16_t EYE_Y        = 96;
  static constexpr int16_t MOUTH_X      = 160;
  static constexpr int16_t MOUTH_Y      = 146;
  // Gaze offset is clamped so eyes never wander past plausible
  // socket bounds. Real art may want a wider/narrower range.
  static constexpr int16_t GAZE_MAX     = 4;
};

class StateMachine {
 public:
  void set_mood(Mood m) {
    if (m == mood_) return;
    mood_ = m;
    push_mood_();
  }

  // Set whether Narada is currently uttering audio. When false the
  // mouth snaps to PH_REST regardless of `phoneme`.
  void set_speaking(bool s) {
    if (s == speaking_) return;
    speaking_ = s;
    push_mouth_();
  }

  void set_phoneme(Phoneme p) {
    if (p == phoneme_) return;
    phoneme_ = p;
    push_mouth_();
  }

  // Gaze in unit-ish space: -1.0 .. +1.0 each axis. The state machine
  // converts to pixel offsets. Bridge passes raw floats in API
  // (multiplied by 100 for int transport).
  void set_gaze(float gx, float gy) {
    if (gx == gaze_x_ && gy == gaze_y_) return;
    gaze_x_ = gx;
    gaze_y_ = gy;
    push_eyes_();
  }

  void set_glyph_visible(bool v, int16_t x = 280, int16_t y = 30) {
    if (v == glyph_visible_ && x == glyph_x_ && y == glyph_y_) return;
    glyph_visible_ = v;
    glyph_x_ = x;
    glyph_y_ = y;
    push_glyph_();
  }

  // Push the current state into the compositor. Used at boot to
  // stage the default scene.
  void apply_all() {
    push_body_();
    push_mood_();
    push_eyes_();
    push_mouth_();
    push_glyph_();
  }

  Mood mood() const { return mood_; }
  bool speaking() const { return speaking_; }
  Phoneme phoneme() const { return phoneme_; }

 private:
  void push_body_() {
    comp().set_layer(LAYER_BODY, TA_BODY_IDLE, Anchors::BODY_X, Anchors::BODY_Y);
  }

  void push_mood_() {
    uint16_t f = TA_MOOD_NEUTRAL;
    switch (mood_) {
      case MOOD_NEUTRAL: f = TA_MOOD_NEUTRAL; break;
      case MOOD_CURIOUS: f = TA_MOOD_CURIOUS; break;
      case MOOD_FOCUSED: f = TA_MOOD_FOCUSED; break;
    }
    comp().set_layer(LAYER_MOOD, f, Anchors::MOOD_X, Anchors::MOOD_Y);
  }

  void push_eyes_() {
    int16_t dx = (int16_t)(gaze_x_ * Anchors::GAZE_MAX);
    int16_t dy = (int16_t)(gaze_y_ * Anchors::GAZE_MAX);
    if (dx > Anchors::GAZE_MAX)  dx = Anchors::GAZE_MAX;
    if (dx < -Anchors::GAZE_MAX) dx = -Anchors::GAZE_MAX;
    if (dy > Anchors::GAZE_MAX)  dy = Anchors::GAZE_MAX;
    if (dy < -Anchors::GAZE_MAX) dy = -Anchors::GAZE_MAX;
    comp().set_layer(LAYER_EYE_LEFT,  TA_EYE_LEFT,
                     Anchors::EYE_LEFT_X + dx, Anchors::EYE_Y + dy);
    comp().set_layer(LAYER_EYE_RIGHT, TA_EYE_RIGHT,
                     Anchors::EYE_RIGHT_X + dx, Anchors::EYE_Y + dy);
  }

  void push_mouth_() {
    uint16_t f = TA_MOUTH_REST;
    if (speaking_) {
      switch (phoneme_) {
        case PH_REST: f = TA_MOUTH_REST; break;
        case PH_AA:   f = TA_MOUTH_AA;   break;
        case PH_EE:   f = TA_MOUTH_EE;   break;
        case PH_OH:   f = TA_MOUTH_OH;   break;
        case PH_MBP:  f = TA_MOUTH_MBP;  break;
      }
    }
    comp().set_layer(LAYER_MOUTH, f, Anchors::MOUTH_X, Anchors::MOUTH_Y);
  }

  void push_glyph_() {
    if (glyph_visible_) {
      comp().set_layer(LAYER_MARG_1, TA_GLYPH_DOT, glyph_x_, glyph_y_);
    } else {
      comp().clear_layer(LAYER_MARG_1);
    }
  }

  Mood mood_ = MOOD_NEUTRAL;
  bool speaking_ = false;
  Phoneme phoneme_ = PH_REST;
  float gaze_x_ = 0.0f;
  float gaze_y_ = 0.0f;
  bool glyph_visible_ = false;
  int16_t glyph_x_ = 280;
  int16_t glyph_y_ = 30;
};

inline StateMachine& sm() {
  static StateMachine instance;
  return instance;
}

}  // namespace narada
