"""HTTP server for serving TTS audio to the device's media_player.

The device's announcement_pipeline fetches via http_request when we send
TTS_END {url: ...}. We serve WAV (Piper's native format) directly — the
pipeline resamples to 48kHz internally.
"""

from __future__ import annotations

import socket
import tempfile
import uuid
from pathlib import Path

from aiohttp import web


def local_ip(target_ip: str) -> str:
    """Find the laptop IP that the target device can reach."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip, 1))
        return s.getsockname()[0]
    finally:
        s.close()


class TTSServer:
    """Serve TTS audio files at http://host:port/tts/{name}.

    Files are written to a temp dir and served via aiohttp.FileResponse
    (zero-copy sendfile when the OS supports it). Names are uuid hex so
    the device can't accidentally hit a stale file from a prior turn.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.dir = Path(tempfile.gettempdir()) / "narada-tts"
        self.dir.mkdir(exist_ok=True)
        self.app = web.Application()
        self.app.router.add_get("/tts/{name}", self._serve)
        self.runner: web.AppRunner | None = None

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()

    async def _serve(self, req: web.Request) -> web.Response:
        name = req.match_info["name"]
        path = self.dir / name
        if not path.exists():
            return web.Response(status=404, text="not found")
        ext = path.suffix.lower()
        ctype = {
            ".wav": "audio/wav",
            ".flac": "audio/flac",
            ".mp3": "audio/mpeg",
        }.get(ext, "application/octet-stream")
        return web.FileResponse(
            path,
            headers={"Content-Type": ctype, "Cache-Control": "no-store"},
        )

    def write(self, audio_bytes: bytes, ext: str = ".wav") -> str:
        """Save audio bytes and return the URL the device can fetch."""
        name = f"{uuid.uuid4().hex}{ext}"
        (self.dir / name).write_bytes(audio_bytes)
        return f"http://{self.host}:{self.port}/tts/{name}"


__all__ = ["TTSServer", "local_ip"]
