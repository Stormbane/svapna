"""Narada's body — ESP32-S3-BOX-3 introspection, build, and deploy.

The body is the physical hardware. The heartbeat is the cognition cycle that
runs on top of it. They are separate concerns. This package owns:

- Querying live device state (what's on screen, sensors, network)
- Compiling and deploying firmware (handles the Windows/MSYS env mess)
- Tailing device logs

Usage:
    python -m svapna.body status
    python -m svapna.body ping
    python -m svapna.body build
    python -m svapna.body deploy
    python -m svapna.body logs
"""

from svapna.body.client import BodyClient, BodyState

__all__ = ["BodyClient", "BodyState"]
