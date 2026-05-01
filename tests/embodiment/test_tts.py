"""TTS helpers — sentence segmentation and PCM resampling. Pure-Python,
no model loading, runs without piper-tts installed."""

import numpy as np

from svapna.embodiment.voice.tts import (
    clean_for_voice,
    resample_pcm_to_16k,
    split_sentences,
)


def test_split_sentences_simple():
    out = split_sentences("Hello there. How are you? Fine!")
    assert out == ["Hello there.", "How are you?", "Fine!"]


def test_split_sentences_keeps_punctuation():
    out = split_sentences("One. Two. Three.")
    assert all(s.endswith(".") for s in out)


def test_split_sentences_handles_no_terminator():
    out = split_sentences("just one fragment")
    assert out == ["just one fragment"]


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_clean_for_voice_strips_emoji():
    out = clean_for_voice("Hello 🌟 traveler")
    assert "🌟" not in out
    assert "Hello" in out
    assert "traveler" in out


def test_clean_for_voice_collapses_whitespace():
    out = clean_for_voice("a\n\n   b\t\tc")
    assert out == "a b c"


def test_resample_passthrough_at_16k():
    pcm = (np.array([100, -100, 200, -200], dtype=np.int16)).tobytes()
    assert resample_pcm_to_16k(pcm, 16000) == pcm


def test_resample_22050_to_16k_changes_length():
    # 220 samples at 22050 Hz = 10ms; resampled to 16k should be ~160.
    pcm = (np.zeros(220, dtype=np.int16)).tobytes()
    out = resample_pcm_to_16k(pcm, 22050)
    out_samples = len(out) // 2
    assert 155 <= out_samples <= 165
