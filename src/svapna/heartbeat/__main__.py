"""Run the heartbeat daemon.

Usage:
    python -m svapna.heartbeat                    # Run with defaults (30 min interval)
    python -m svapna.heartbeat --interval 300     # 5 minute interval (testing)
    python -m svapna.heartbeat --once             # Single heartbeat then exit
    python -m svapna.heartbeat --lora-path PATH   # Specific LoRA adapter
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from svapna.heartbeat.daemon import HeartbeatDaemon, DEFAULT_INTERVAL
from svapna.heartbeat.viveka import VivekaCore
from svapna.heartbeat.delegate import ClaudeDelegate
from svapna.heartbeat.memory import HeartbeatMemory
from svapna.heartbeat.display import DisplayClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Svapna heartbeat daemon")
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL,
        help=f"Seconds between heartbeats (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single heartbeat then exit",
    )
    parser.add_argument(
        "--lora-path", type=Path, default=None,
        help="Path to LoRA adapter (default: models/lora/latest or most recent)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Base model override (default: from training.yml)",
    )
    parser.add_argument(
        "--claude-model", type=str, default="claude-sonnet-4-6",
        help="Claude model for delegation (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--db-path", type=Path, default=Path("data/heartbeat/memory.db"),
        help="Path to memory database",
    )
    parser.add_argument(
        "--display-ip", type=str, default="192.168.86.35",
        help="ESP32 display device IP address",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Resolve LoRA path
    lora_path = args.lora_path
    if lora_path is None:
        # Try latest symlink, then most recent date-stamped directory
        latest = Path("models/lora/latest")
        if latest.exists():
            lora_path = latest
        else:
            lora_dirs = sorted(Path("models/lora").glob("2026-*"), reverse=True)
            if lora_dirs:
                lora_path = lora_dirs[0]

    # Resolve base model
    model_path = args.model
    if model_path is None:
        try:
            import yaml
            with open("config/training.yml") as f:
                cfg = yaml.safe_load(f)
            model_path = cfg.get("base_model", {}).get("name", "")
        except Exception:
            model_path = "unsloth/Qwen3-8B-unsloth-bnb-4bit"

    print("=== Svapna Heartbeat Daemon ===")
    print(f"Model:    {model_path}")
    print(f"LoRA:     {lora_path}")
    print(f"Claude:   {args.claude_model}")
    print(f"Interval: {args.interval}s")
    print(f"Memory:   {args.db_path}")
    print()

    # Build components
    viveka = VivekaCore(model_path=model_path, lora_path=lora_path)
    delegate = ClaudeDelegate(model=args.claude_model)
    memory = HeartbeatMemory(db_path=args.db_path)
    display = DisplayClient(device_ip=args.display_ip)

    # Check display connection
    if display.is_available():
        print(f"Display: connected ({args.display_ip})")
    else:
        print(f"Display: not reachable ({args.display_ip}) — running without display")

    daemon = HeartbeatDaemon(
        viveka=viveka,
        delegate=delegate,
        memory=memory,
        display=display,
        interval=args.interval,
    )

    if args.once:
        print("Running single heartbeat...")
        viveka.load()
        result = daemon.beat_once()
        print(f"\nResult: {result}")
        viveka.unload()
        memory.close()
    else:
        print("Starting heartbeat loop (Ctrl+C to stop)...")
        daemon.run()

    print("\nDone.")


if __name__ == "__main__":
    main()
