#!/usr/bin/env python
"""Phase 1 sprite test driver.

Switch scenarios on narada-sprite-test and/or trigger a sandhi sweep.

Usage:
    python scripts/sprite_test_control.py scenario 0   # solid bg
    python scripts/sprite_test_control.py scenario 1   # host bhumi
    python scripts/sprite_test_control.py scenario 2   # full composite (default)
    python scripts/sprite_test_control.py sandhi       # fire 60-frame swap
    python scripts/sprite_test_control.py sweep        # auto: 0,1,2 then sandhi

Requires the device reachable by mDNS (narada-sprite-test.local) or pass
HOST=<ip> in env. API has no auth, no encryption — same as narada-body.
"""
from __future__ import annotations

import asyncio
import os
import sys

import aioesphomeapi

HOST = os.environ.get("HOST", "narada-sprite-test.local")
PORT = int(os.environ.get("PORT", "6053"))


async def get_services(api: aioesphomeapi.APIClient) -> dict:
    a, b = await api.list_entities_services()
    # Be liberal about which slot is services — UserService has .key + .name + .args
    cand_services = [x for x in (a, b) if x and hasattr(x[0], "args")]
    services = cand_services[0] if cand_services else []
    print(f"  services advertised: {[s.name for s in services]}", flush=True)
    return {s.name: s for s in services}


async def set_scenario(api: aioesphomeapi.APIClient, n: int) -> None:
    svc = await get_services(api)
    await api.execute_service(svc["set_scenario"], {"s": n})
    print(f"scenario set to {n}")


async def trigger_sandhi(api: aioesphomeapi.APIClient) -> None:
    svc = await get_services(api)
    await api.execute_service(svc["trigger_sandhi"], {})
    print("sandhi triggered")


async def sweep(api: aioesphomeapi.APIClient) -> None:
    """Walk through 0 -> 1 -> 2, holding each ~6 s so two log batches print
    per scenario, then fire a sandhi and wait for it to complete."""
    for n in (0, 1, 2):
        await set_scenario(api, n)
        print(f"  holding scenario={n} for 6 s, watch the serial log...")
        await asyncio.sleep(6.0)
    print("firing sandhi...")
    await trigger_sandhi(api)
    await asyncio.sleep(3.0)


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]

    print(f"connecting to {HOST}:{PORT} ...", flush=True)
    api = aioesphomeapi.APIClient(HOST, PORT, None)
    try:
        await asyncio.wait_for(api.connect(login=True), timeout=8.0)
    except asyncio.TimeoutError:
        print(f"  TIMEOUT after 8 s. Device not reachable at {HOST}.")
        print("  Try: HOST=<ip> python scripts/sprite_test_control.py ...")
        print("  Find IP via your router, or check the serial log for")
        print("  'wifi:' INFO line right after boot showing the IP.")
        sys.exit(2)
    except Exception as exc:
        print(f"  connect failed: {exc!r}")
        sys.exit(2)
    print("  connected.", flush=True)
    try:
        if cmd == "scenario":
            if len(sys.argv) < 3:
                print("usage: scenario <0|1|2|3>")
                sys.exit(1)
            await set_scenario(api, int(sys.argv[2]))
        elif cmd == "sandhi":
            await trigger_sandhi(api)
        elif cmd == "sweep":
            await sweep(api)
        else:
            print(f"unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    finally:
        await api.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
