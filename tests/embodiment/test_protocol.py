"""Protocol constants — sanity checks. No I/O."""

from svapna.embodiment.voice.protocol import (
    MIC_RATE,
    MIC_BYTES_PER_SAMPLE,
    VAD_FRAME_BYTES,
    VAD_FRAME_SAMPLES,
    VAEvent,
)


def test_mic_rate_matches_whisper():
    assert MIC_RATE == 16000


def test_vad_frame_is_silero_size():
    # silero-vad v5+ requires exactly 512 samples per frame at 16kHz.
    assert VAD_FRAME_SAMPLES == 512
    assert VAD_FRAME_BYTES == 512 * 2
    assert abs(VAD_FRAME_SAMPLES / MIC_RATE - 0.032) < 1e-6


def test_voice_assistant_events_present():
    # The events the pipeline actually sends.
    needed = [
        "VOICE_ASSISTANT_RUN_START",
        "VOICE_ASSISTANT_RUN_END",
        "VOICE_ASSISTANT_STT_START",
        "VOICE_ASSISTANT_STT_VAD_START",
        "VOICE_ASSISTANT_STT_VAD_END",
        "VOICE_ASSISTANT_STT_END",
        "VOICE_ASSISTANT_INTENT_START",
        "VOICE_ASSISTANT_INTENT_END",
        "VOICE_ASSISTANT_TTS_START",
        "VOICE_ASSISTANT_TTS_STREAM_START",
        "VOICE_ASSISTANT_TTS_STREAM_END",
        "VOICE_ASSISTANT_TTS_END",
    ]
    for name in needed:
        assert hasattr(VAEvent, name), f"missing: {name}"
