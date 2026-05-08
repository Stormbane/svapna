#!/usr/bin/env python
"""Loudness bisect: bypass voice_assistant, drive media_player directly.

Generates a known-loud 48 kHz mono WAV (sine, half-amplitude, 3s),
serves it via a one-shot HTTP server, and triggers
media_player.play_media on the device. If this is loud, the audio
chain is fine and the voice_assistant pipeline is the bottleneck.
If still faint, the audio chain itself (DAC, amp, speaker config)
is the limit.

Usage:  python scripts/test_play_media.py [--device-ip 192.168.86.35]
"""
from __future__ import annotations

import argparse
import asyncio
import io
import math
import socket
import struct
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aioesphomeapi


SR = 48000
DURATION_S = 3.0
FREQ_HZ = 440.0
AMPLITUDE = 0.95  # near-full scale; minor clipping headroom at the WAV level


def generate_wav() -> bytes:
    n = int(SR * DURATION_S)
    samples = [
        int(AMPLITUDE * 32767 * math.sin(2 * math.pi * FREQ_HZ * i / SR))
        for i in range(n)
    ]
    pcm = struct.pack(f"<{n}h", *samples)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return buf.getvalue()


WAV_BYTES = generate_wav()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(WAV_BYTES)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(WAV_BYTES)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt, *args):
        return


def local_ip(target: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 1))
        return s.getsockname()[0]
    finally:
        s.close()


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--device-ip", default="192.168.86.35")
    p.add_argument("--port", type=int, default=8766)
    args = p.parse_args()

    httpd = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host = local_ip(args.device_ip)
    url = f"http://{host}:{args.port}/test.wav"
    print(f"serving {len(WAV_BYTES)} bytes at {url}")

    print(f"connecting to {args.device_ip}:6053...")
    api = aioesphomeapi.APIClient(args.device_ip, 6053, password="")
    await asyncio.wait_for(api.connect(login=True), timeout=8.0)
    print("  connected")

    entities, _services = await api.list_entities_services()
    print("  entity types:", sorted({type(e).__name__ for e in entities}))
    media_players = [
        e for e in entities
        if "mediaplayer" in type(e).__name__.lower()
        or "media_player" in type(e).__name__.lower()
    ]
    if not media_players:
        print("no media_player entity found in:")
        for e in entities:
            print(f"   - {type(e).__name__}: {getattr(e, 'name', '?')!r}")
        return
    mp = media_players[0]
    print(f"  media_player key={mp.key} name={mp.name!r}")

    print("setting media_player volume to 1.0")
    api.media_player_command(mp.key, volume=1.0)
    await asyncio.sleep(0.3)
    print(f"sending media_player.play_media url={url}")
    api.media_player_command(mp.key, media_url=url, announcement=True)

    # Hold the HTTP server alive long enough for fetch + playback.
    print("waiting 8 s for playback...")
    await asyncio.sleep(8.0)
    await api.disconnect()
    httpd.shutdown()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
