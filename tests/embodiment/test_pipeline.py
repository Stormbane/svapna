"""Pipeline state machine — drives a fake APIClient through one turn
and asserts the event sequence. Stubs out STT/Brain/TTS so pytest runs
without faster-whisper or piper installed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from svapna.embodiment.voice.pipeline import Pipeline
from svapna.embodiment.voice.protocol import VAEvent
from svapna.embodiment.voice.vad import VadVerdict


class FakeVad:
    """Stays in LISTENING — tests drive close via handle_stop."""

    def process(self, chunk):
        return VadVerdict.LISTENING

    def reset(self):
        pass


class FakeAPIClient:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []
        self.audio_chunks: list[bytes] = []

    def send_voice_assistant_event(self, event_type, data):
        self.events.append((event_type.name, dict(data)))

    def send_voice_assistant_audio(self, chunk):
        self.audio_chunks.append(bytes(chunk))


class FakeSTT:
    def __init__(self, text: str = "hello narada"):
        self.text = text

    async def transcribe(self, pcm_bytes: bytes) -> str:
        return self.text


class FakeBrain:
    def __init__(self, reply: str = "loud and clear traveler"):
        self.reply = reply
        self.calls: list[str] = []

    async def respond(self, user_text: str) -> str:
        self.calls.append(user_text)
        return self.reply


class FakeTTS:
    sample_rate = 22050

    async def synthesize(self, text: str) -> bytes:
        # Minimal valid WAV header + 4 bytes of silence.
        return b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 24


class FakeTTSServer:
    def write(self, audio_bytes: bytes, ext: str = ".wav") -> str:
        return f"http://fake/tts/abc{ext}"


def _make_pipeline(client, **kwargs) -> Pipeline:
    return Pipeline(
        client=client,
        stt=kwargs.get("stt", FakeSTT()),
        brain=kwargs.get("brain", FakeBrain()),
        tts=kwargs.get("tts", FakeTTS()),
        tts_server=kwargs.get("tts_server", FakeTTSServer()),
        streaming_tts=kwargs.get("streaming_tts", False),
        vad_factory=lambda: FakeVad(),
    )


@pytest.mark.asyncio
async def test_full_turn_url_mode_emits_expected_events():
    client = FakeAPIClient()
    brain = FakeBrain("hi traveler")
    pipeline = _make_pipeline(client, brain=brain)

    audio_settings = MagicMock()
    port = await pipeline.handle_start(
        conversation_id="conv1",
        flags=0,
        audio_settings=audio_settings,
        wake_word_phrase="okay nabu",
    )
    assert port == 0

    # 0.5s of fake audio (8000 int16 samples, all zeros) — fail VAD's
    # "speech_required_s" threshold so we go through the silence path
    # via handle_stop instead. handle_stop drives _process directly.
    audio = b"\x00\x00" * 8000
    await pipeline.handle_audio(audio)
    await pipeline.handle_stop(server_side=False)
    # Allow the close task to finish.
    for _ in range(10):
        await asyncio.sleep(0)

    names = [name for name, _ in client.events]
    # Required ordering: RUN_START -> STT_START -> STT_VAD_START
    # -> STT_VAD_END -> STT_END -> INTENT_START -> INTENT_END
    # -> TTS_START -> TTS_END -> RUN_END
    expected_subsequence = [
        "VOICE_ASSISTANT_RUN_START",
        "VOICE_ASSISTANT_STT_START",
        "VOICE_ASSISTANT_STT_VAD_START",
        "VOICE_ASSISTANT_STT_VAD_END",
        "VOICE_ASSISTANT_STT_END",
        "VOICE_ASSISTANT_INTENT_START",
        "VOICE_ASSISTANT_INTENT_END",
        "VOICE_ASSISTANT_TTS_START",
        "VOICE_ASSISTANT_TTS_END",
        "VOICE_ASSISTANT_RUN_END",
    ]
    # Subsequence check (no extra events between, in this order).
    idx = 0
    for name in names:
        if idx < len(expected_subsequence) and name == expected_subsequence[idx]:
            idx += 1
    assert idx == len(expected_subsequence), \
        f"missing events. got: {names}"

    # TTS_END must carry a non-empty url (load-bearing for state transition
    # in the device firmware — see protocol.py docstring).
    tts_end = next(d for n, d in client.events if n == "VOICE_ASSISTANT_TTS_END")
    assert tts_end.get("url"), "TTS_END must include a non-empty url"

    # Brain was called with the STT text.
    assert brain.calls == ["hello narada"]


@pytest.mark.asyncio
async def test_phantom_turn_skips_brain():
    client = FakeAPIClient()
    brain = FakeBrain()
    pipeline = _make_pipeline(client, brain=brain)

    await pipeline.handle_start(
        conversation_id="conv1", flags=0,
        audio_settings=MagicMock(), wake_word_phrase=None,
    )
    audio = b"\x00\x00" * 8000
    await pipeline.handle_audio(audio)
    await pipeline.handle_stop(server_side=False)
    for _ in range(10):
        await asyncio.sleep(0)

    assert brain.calls == [], "phantom turn must not invoke brain"
    names = [name for name, _ in client.events]
    assert "VOICE_ASSISTANT_RUN_END" in names


@pytest.mark.asyncio
async def test_streaming_tts_sends_audio_chunks():
    client = FakeAPIClient()

    class StreamingTTS(FakeTTS):
        async def synthesize_streaming(self, text):
            # Yield two "sentences" of fake PCM.
            yield b"\x10\x00" * 1000  # 1000 samples = ~45ms at 22050
            yield b"\x20\x00" * 1000

    pipeline = _make_pipeline(client, tts=StreamingTTS(), streaming_tts=True)

    await pipeline.handle_start(
        conversation_id="conv1", flags=0,
        audio_settings=MagicMock(), wake_word_phrase="okay nabu",
    )
    await pipeline.handle_audio(b"\x00\x00" * 8000)
    await pipeline.handle_stop(server_side=False)
    for _ in range(20):
        await asyncio.sleep(0)

    assert len(client.audio_chunks) > 0, "streaming mode must call send_voice_assistant_audio"
    names = [name for name, _ in client.events]
    assert "VOICE_ASSISTANT_TTS_STREAM_START" in names
    assert "VOICE_ASSISTANT_TTS_STREAM_END" in names
