"""Voice bridge configuration."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DEVICE_IP = "192.168.86.35"
DEFAULT_API_PORT = 6053
DEFAULT_TTS_PORT = 8765
DEFAULT_WHISPER_MODEL = "small.en"
DEFAULT_PIPER_MODEL_DIR = Path.home() / ".cache" / "piper"
DEFAULT_PIPER_VOICE = "en_US-libritts_r-medium"
DEFAULT_PIPER_SPEAKER_ID: int | None = 829  # auditioned 2026-05-01; libritts_r-medium
DEFAULT_PIPER_VOLUME = 4.0  # bumped — Piper's default 1.0 is sub-audible on BOX-3 speaker
DEFAULT_SYSTEM_PROMPT = "embodiment/voice/narada-voice.md"
DEFAULT_BRAIN = "claude"  # one of: claude, heartbeat
DEFAULT_CONVERSATION_WINDOW_S = 30.0


@dataclass
class Config:
    device_ip: str
    api_port: int
    tts_port: int
    whisper_model: str
    piper_model_dir: Path
    piper_voice: str
    piper_speaker_id: int | None
    piper_volume: float
    system_prompt: Path
    brain: str
    conversation_window_s: float
    streaming_tts: bool


def parse_args(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(
        description="Narada voice bridge — STT/brain/TTS over ESPHome native API"
    )
    p.add_argument("--device-ip", default=DEFAULT_DEVICE_IP)
    p.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    p.add_argument("--tts-port", type=int, default=DEFAULT_TTS_PORT,
                   help="HTTP port for serving TTS audio to media_player")
    p.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    p.add_argument("--piper-model-dir", type=Path, default=DEFAULT_PIPER_MODEL_DIR,
                   help="Directory containing Piper .onnx + .json voice files")
    p.add_argument("--piper-voice", default=DEFAULT_PIPER_VOICE,
                   help="Voice base name (without .onnx). e.g. en_US-libritts-high")
    p.add_argument("--piper-speaker-id", type=int, default=DEFAULT_PIPER_SPEAKER_ID,
                   help="Speaker ID for multi-speaker voices (libritts has 904)")
    p.add_argument("--piper-volume", type=float, default=DEFAULT_PIPER_VOLUME,
                   help="Piper amplitude multiplier (default 4.0 — BOX-3 speaker is quiet)")
    p.add_argument("--system-prompt", type=Path, default=Path(DEFAULT_SYSTEM_PROMPT))
    p.add_argument("--brain", choices=["claude", "heartbeat"], default=DEFAULT_BRAIN,
                   help="Which brain to wire. heartbeat is currently a stub.")
    p.add_argument("--conversation-window-s", type=float,
                   default=DEFAULT_CONVERSATION_WINDOW_S,
                   help="Silence gap (s) after which a new claude session starts")
    p.add_argument("--streaming-tts", action="store_true",
                   help="Stream TTS sentence-by-sentence via API audio "
                        "(low-latency). Default: full-utterance URL playback.")
    args = p.parse_args(argv)
    return Config(
        device_ip=args.device_ip,
        api_port=args.api_port,
        tts_port=args.tts_port,
        whisper_model=args.whisper_model,
        piper_model_dir=args.piper_model_dir,
        piper_voice=args.piper_voice,
        piper_speaker_id=args.piper_speaker_id,
        piper_volume=args.piper_volume,
        system_prompt=args.system_prompt,
        brain=args.brain,
        conversation_window_s=args.conversation_window_s,
        streaming_tts=args.streaming_tts,
    )


__all__ = ["Config", "parse_args", "DEFAULT_DEVICE_IP"]
