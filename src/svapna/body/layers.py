"""Layer state dataclasses for the v1.0 expression contract.

See `embodiment/design/v1.0-architecture.md` for the full schema.
See `embodiment/design/v1.0-vocabulary.md` for the visual realization.

Cognition constructs these and hands them to ExpressionClient. The firmware
renders. No cognition code touches a color, glyph, or animation timing.

This module is also the contract that scales beyond the screen: a future
humanoid body (Unitree G1 or similar) adds new layers (pose, gait, gaze,
proximity) without restructuring the ones below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AttentionMode = Literal["inward", "outward", "diffuse"]
ActivityMode = Literal[
    "resting", "thinking", "listening", "speaking",
    "seeing", "working", "dreaming",
]
SignalKind = Literal[
    "none", "oh", "q", "dots", "check", "bang", "ask", "noticed", "love",
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class Mood:
    """Continuous (valence, arousal). Mood drives accent color, not geometry."""
    valence: float = 0.3        # [-1, +1]
    arousal: float = 0.4        # [0, 1]

    def clamped(self) -> "Mood":
        return Mood(
            valence=_clamp(self.valence, -1.0, 1.0),
            arousal=_clamp(self.arousal, 0.0, 1.0),
        )


@dataclass
class Vitality:
    """Slow-changing body condition. Drives breath rate and substrate density."""
    sleep_pressure: float = 0.3   # [0, 1]
    restlessness: float = 0.2     # [0, 1]
    warmth: float = 0.6           # [0, 1]

    def clamped(self) -> "Vitality":
        return Vitality(
            sleep_pressure=_clamp(self.sleep_pressure, 0.0, 1.0),
            restlessness=_clamp(self.restlessness, 0.0, 1.0),
            warmth=_clamp(self.warmth, 0.0, 1.0),
        )


@dataclass
class Attention:
    """Where the body is oriented. Drives presence-dot visibility, eye direction."""
    mode: AttentionMode = "diffuse"
    target: str = ""               # conventional: "" | "suti" | "self" | "task" | "environment"
    intensity: float = 0.4         # [0, 1]

    def clamped(self) -> "Attention":
        return Attention(
            mode=self.mode,
            target=self.target,
            intensity=_clamp(self.intensity, 0.0, 1.0),
        )


@dataclass
class Activity:
    """What the body is currently doing. Drives the foreground motif."""
    mode: ActivityMode = "resting"


@dataclass
class Utterance:
    """A spoken sentence with karaoke-style word-index advance.

    text empty → no utterance is active.
    """
    text: str = ""
    total_words: int = 0
    word_index: int = 0

    def is_active(self) -> bool:
        return bool(self.text)


@dataclass
class Signal:
    """Discrete event overlay. duration_ms == 0 means persistent until cleared."""
    kind: SignalKind = "none"
    duration_ms: int = 2000

    def is_active(self) -> bool:
        return self.kind != "none"


@dataclass
class BodyExpressionState:
    """The full v1.0 expression state — six layers.

    Used for batched updates and for read-back via proprioception.
    """
    mood: Mood = field(default_factory=Mood)
    vitality: Vitality = field(default_factory=Vitality)
    attention: Attention = field(default_factory=Attention)
    activity: Activity = field(default_factory=Activity)
    utterance: Utterance = field(default_factory=Utterance)
    signal: Signal = field(default_factory=Signal)
