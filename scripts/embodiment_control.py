#!/usr/bin/env python
"""Driver for narada-embodiment.yaml — Phase 2 firmware control.

Until the state machine + bridge integration land, this script is how
we drive scenes by hand:

    python scripts/embodiment_control.py mood neutral
    python scripts/embodiment_control.py mood curious
    python scripts/embodiment_control.py glyph on 280 30
    python scripts/embodiment_control.py glyph off
    python scripts/embodiment_control.py face <el> <er> <m> <b>
    python scripts/embodiment_control.py clear

Frame IDs (test_atlas, sorted alphabetically):

    0  body_idle
    1  eye_left
    2  eye_right
    3  glyph_dot
    4  mood_curious
    5  mood_focused
    6  mood_neutral
    7  mouth_neutral

(See `embodiment/firmware/include/atlas_test_atlas.h` enum for the
canonical list. The order is alphabetical; build_atlas.py sorts.)

Set HOST=<ip> if mDNS doesn't resolve (we have mdns disabled).
"""
from __future__ import annotations

import asyncio
import os
import sys

import aioesphomeapi

HOST = os.environ.get("HOST", "narada-embodiment.local")
PORT = int(os.environ.get("PORT", "6053"))

MOOD_FRAME = {"neutral": 0, "curious": 1, "focused": 2}


async def get_services(api: aioesphomeapi.APIClient) -> dict:
    _entities, services = await api.list_entities_services()
    return {s.name: s for s in services}


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]

    print(f"connecting to {HOST}:{PORT} ...", flush=True)
    api = aioesphomeapi.APIClient(HOST, PORT, None)
    try:
        await asyncio.wait_for(api.connect(login=True), timeout=8.0)
    except (asyncio.TimeoutError, Exception) as exc:
        print(f"connect failed: {exc!r}")
        sys.exit(2)
    print("  connected.", flush=True)

    try:
        svc = await get_services(api)

        if cmd == "mood":
            name = sys.argv[2] if len(sys.argv) > 2 else "neutral"
            n = MOOD_FRAME.get(name)
            if n is None:
                print(f"unknown mood: {name}; one of {list(MOOD_FRAME)}")
                sys.exit(1)
            await api.execute_service(svc["set_mood"], {"mood": n})
            print(f"mood -> {name}")

        elif cmd == "glyph":
            sub = sys.argv[2] if len(sys.argv) > 2 else "on"
            x = int(sys.argv[3]) if len(sys.argv) > 3 else 280
            y = int(sys.argv[4]) if len(sys.argv) > 4 else 30
            await api.execute_service(
                svc["set_glyph"],
                {"visible": sub == "on", "x": x, "y": y},
            )
            print(f"glyph {sub} at ({x},{y})")

        elif cmd == "face":
            if len(sys.argv) < 6:
                print("usage: face <eye_l> <eye_r> <mouth> <body>")
                sys.exit(1)
            args = {
                "eye_l": int(sys.argv[2]),
                "eye_r": int(sys.argv[3]),
                "mouth": int(sys.argv[4]),
                "body": int(sys.argv[5]),
            }
            await api.execute_service(svc["set_face"], args)
            print(f"face -> {args}")

        elif cmd == "layer":
            if len(sys.argv) < 6:
                print("usage: layer <id> <frame> <x> <y>")
                sys.exit(1)
            args = {
                "layer": int(sys.argv[2]),
                "frame": int(sys.argv[3]),
                "x": int(sys.argv[4]),
                "y": int(sys.argv[5]),
            }
            await api.execute_service(svc["set_layer"], args)
            print(f"layer -> {args}")

        elif cmd == "clear":
            await api.execute_service(svc["clear_face"], {})
            print("cleared")

        elif cmd == "demo":
            # Cycle moods + glyph to show the compositor working.
            for m in ("neutral", "curious", "focused", "neutral"):
                await api.execute_service(
                    svc["set_mood"], {"mood": MOOD_FRAME[m]}
                )
                print(f"mood -> {m}")
                await asyncio.sleep(1.5)
            await api.execute_service(
                svc["set_glyph"], {"visible": True, "x": 280, "y": 30}
            )
            print("glyph on")
            await asyncio.sleep(1.5)
            await api.execute_service(
                svc["set_glyph"], {"visible": False, "x": 0, "y": 0}
            )
            print("glyph off")

        else:
            print(f"unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    finally:
        await api.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
