"""Per-turn voice pipeline state machine.

Owns one turn: handle_start (from APIClient subscribe_voice_assistant)
through handle_audio (driven by VAD) through STT, brain, TTS, and
eventual TTS_END. Stateless across turns — instance state is reset on
each handle_start.

Phantom-turn gate: turns arrive with wake_word_phrase=None when the
device starts a turn without a real wake-word event (the legacy 8s
phantom case). We acknowledge the protocol so the device doesn't
retry, but discard the transcript without invoking the brain.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import TYPE_CHECKING, Callable

from aioesphomeapi import VoiceAssistantAudioSettings

from .protocol import VAEvent, MIC_RATE
from .tts import clean_for_voice, resample_pcm_to_16k
from .vad import VadVerdict

if TYPE_CHECKING:
    from aioesphomeapi import APIClient
    from .brain import Brain
    from .http_server import TTSServer
    from .stt import WhisperSTT
    from .tts import PiperTTS
    from .vad import SileroVad


def _default_vad_factory():
    """Lazy import so tests don't require pysilero-vad."""
    from .vad import SileroVad
    return SileroVad()


# Streaming TTS pacing. We send chunks of this duration to give the
# device's announcement_pipeline buffer time to drain. 60ms is the
# sweet spot — small enough to keep latency low, large enough that the
# i2s ring buffer doesn't underrun.
STREAM_CHUNK_MS = 60


class Pipeline:
    def __init__(
        self,
        client: APIClient,
        stt: WhisperSTT,
        brain: Brain,
        tts: PiperTTS,
        tts_server: TTSServer,
        streaming_tts: bool,
        vad_factory: Callable[[], "SileroVad"] | None = None,
    ):
        self.client = client
        self.stt = stt
        self.brain = brain
        self.tts = tts
        self.tts_server = tts_server
        self.streaming_tts = streaming_tts
        self._vad_factory = vad_factory or _default_vad_factory

        self._buf: list[bytes] = []
        self._active = False
        self._wake_phrase: str | None = None
        self._gated_phantom = False
        self._vad: "SileroVad | None" = None
        self._closing = False
        self._close_lock = asyncio.Lock()

    async def handle_start(
        self,
        conversation_id: str,
        flags: int,
        audio_settings: VoiceAssistantAudioSettings,
        wake_word_phrase: str | None,
    ) -> int | None:
        self._buf = []
        self._active = True
        self._closing = False
        self._wake_phrase = wake_word_phrase or ""
        self._gated_phantom = wake_word_phrase is None
        self._vad = self._vad_factory()

        if wake_word_phrase:
            print(f"\nwake: {self._wake_phrase!r} (conv={conversation_id})", flush=True)
        else:
            print("\n  phantom turn (no wake_word_phrase) — discarding", flush=True)

        await self._event(VAEvent.VOICE_ASSISTANT_RUN_START)
        await self._event(VAEvent.VOICE_ASSISTANT_STT_START)
        await self._event(VAEvent.VOICE_ASSISTANT_STT_VAD_START)
        # Returning a non-None port is required by aioesphomeapi even
        # when audio comes via the API path (a None return makes the
        # device abort with "Server could not be started").
        return 0

    async def handle_audio(self, data: bytes) -> None:
        if not self._active or self._vad is None:
            return
        self._buf.append(data)
        verdict = self._vad.process(data)
        if verdict is not VadVerdict.LISTENING and not self._closing:
            self._closing = True
            asyncio.create_task(self._close(verdict))

    async def handle_stop(self, server_side: bool) -> None:
        """Device-side stop — rare; close path normally driven by VAD."""
        if self._closing:
            return
        self._closing = True
        await self._close(VadVerdict.SILENCE_CLOSED)

    async def _close(self, verdict: VadVerdict) -> None:
        async with self._close_lock:
            if not self._active:
                return
            print(f"  vad: {verdict.value} — closing mic", flush=True)
            await self._event(VAEvent.VOICE_ASSISTANT_STT_VAD_END)
            await self._process()

    async def _process(self) -> None:
        if not self._active:
            return
        self._active = False
        pcm = b"".join(self._buf)
        self._buf = []
        seconds = (len(pcm) // 2) / MIC_RATE
        print(f"  audio: {seconds:.2f}s ({len(pcm)} bytes)", flush=True)

        if seconds < 0.3:
            print("  too short — skipping", flush=True)
            await self._end_run()
            return

        # STT
        t0 = time.monotonic()
        text = await self.stt.transcribe(pcm)
        print(f"  stt: {text!r} ({time.monotonic() - t0:.1f}s)", flush=True)
        await self._event(VAEvent.VOICE_ASSISTANT_STT_END, {"text": text})
        if not text:
            await self._end_run()
            return

        # Phantom-turn gate.
        if self._gated_phantom:
            print("  phantom turn — discarding stt, no brain call", flush=True)
            await self._end_run()
            return

        # Brain
        t0 = time.monotonic()
        await self._event(VAEvent.VOICE_ASSISTANT_INTENT_START)
        try:
            reply = await self.brain.respond(text)
        except Exception as e:
            print(f"  brain error: {e}", file=sys.stderr)
            reply = ""
        reply = clean_for_voice(reply)
        print(f"  brain: {reply!r} ({time.monotonic() - t0:.1f}s)", flush=True)
        await self._event(VAEvent.VOICE_ASSISTANT_INTENT_END,
                          {"conversation_id": "narada"})
        if not reply:
            await self._end_run()
            return

        # TTS
        t0 = time.monotonic()
        await self._event(VAEvent.VOICE_ASSISTANT_TTS_START, {"text": reply})
        if self.streaming_tts:
            await self._tts_streaming(reply)
        else:
            await self._tts_full(reply)
        print(f"  tts: done ({time.monotonic() - t0:.1f}s)", flush=True)
        await self._end_run()

    async def _tts_full(self, reply: str) -> None:
        """Synthesize one WAV, serve it, send TTS_END {url}."""
        wav_bytes = await self.tts.synthesize(reply)
        url = self.tts_server.write(wav_bytes, ext=".wav")
        await self._event(VAEvent.VOICE_ASSISTANT_TTS_END, {"url": url})

    async def _tts_streaming(self, reply: str) -> None:
        """Synthesize sentence-by-sentence, stream PCM via API audio.

        Each sentence becomes one or more `send_voice_assistant_audio`
        chunks; we resample to 16kHz mono so the device's announcement
        pipeline takes a uniform format regardless of voice rate.
        """
        await self._event(VAEvent.VOICE_ASSISTANT_TTS_STREAM_START)
        src_rate = self.tts.sample_rate
        chunk_samples_16k = int(16000 * STREAM_CHUNK_MS / 1000)
        chunk_bytes_16k = chunk_samples_16k * 2
        async for sentence_pcm in self.tts.synthesize_streaming(reply):
            pcm_16k = await asyncio.to_thread(
                resample_pcm_to_16k, sentence_pcm, src_rate
            )
            for i in range(0, len(pcm_16k), chunk_bytes_16k):
                self.client.send_voice_assistant_audio(pcm_16k[i:i + chunk_bytes_16k])
                await asyncio.sleep(STREAM_CHUNK_MS / 1000 * 0.95)
        await self._event(VAEvent.VOICE_ASSISTANT_TTS_STREAM_END)
        # TTS_END requires a non-empty URL for state transition. The
        # placeholder is fine here — playback already happened via the
        # streamed PCM path; the URL would only be fetched as a fallback.
        await self._event(VAEvent.VOICE_ASSISTANT_TTS_END,
                          {"url": "stream://narada"})

    async def _end_run(self) -> None:
        await self._event(VAEvent.VOICE_ASSISTANT_RUN_END)

    async def _event(self, event_type: VAEvent,
                     data: dict[str, str] | None = None) -> None:
        try:
            self.client.send_voice_assistant_event(event_type, data or {})
        except Exception as e:
            print(f"  event {event_type.name} failed: {e}", file=sys.stderr)


__all__ = ["Pipeline"]
