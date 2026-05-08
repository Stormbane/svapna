"""GPU/CPU stress test to isolate thermal vs PSU crash root cause.

Runs configurable GPU compute load (matrix multiplications) and optional CPU
stress in parallel, logging temp/power/clock/fan every second.

Test scenarios:
  1. GPU-only at full power + external fan  → PSU handles GPU alone?
  2. GPU + CPU stress + external fan        → PSU handles combined load?
  3. GPU-only at full power, NO fan         → find exact crash temperature

Usage:
  python scripts/gpu_stress_test.py --duration 300 --power-limit 350
  python scripts/gpu_stress_test.py --duration 300 --power-limit 350 --cpu-stress
  python scripts/gpu_stress_test.py --duration 300 --power-limit 280 --matrix-size 4096
"""

import argparse
import csv
import multiprocessing
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_gpu_stats() -> dict | None:
    """Read all GPU stats in one nvidia-smi call."""
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=temperature.gpu,power.draw,power.limit,fan.speed,"
             "clocks.gr,clocks.mem,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            return {
                "temp_c": float(parts[0]),
                "power_w": float(parts[1]),
                "power_limit_w": float(parts[2]),
                "fan_pct": int(parts[3]),
                "clock_mhz": int(parts[4]),
                "mem_clock_mhz": int(parts[5]),
                "vram_used_mib": int(parts[6]),
                "vram_total_mib": int(parts[7]),
                "gpu_util_pct": int(parts[8]),
            }
    except Exception:
        return None


def set_gpu_power_limit(watts: int) -> bool:
    """Set GPU power limit. Requires admin."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-pl", str(watts)],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def cpu_stress_worker(stop_event):
    """Burn one CPU core doing pointless math."""
    x = 0.0
    while not stop_event.is_set():
        for _ in range(100000):
            x = (x + 1.1) * 0.9999
            if stop_event.is_set():
                break


def run_stress_test(
    duration: int = 300,
    power_limit: int = 350,
    matrix_size: int = 8192,
    cpu_stress: bool = False,
    cpu_cores: int | None = None,
    log_file: str | None = None,
    shutdown_temp: int = 90,
):
    """Run GPU stress test with per-second logging.

    Args:
        duration: Test duration in seconds
        power_limit: GPU power limit in watts
        matrix_size: Size of square matrices for GPU stress (larger = more VRAM + compute)
        cpu_stress: Also stress CPU cores
        cpu_cores: Number of CPU cores to stress (default: all physical cores)
        log_file: CSV output path
        shutdown_temp: Abort if GPU exceeds this temperature
    """
    import torch

    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("models/lora/stress_tests")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / f"stress_{timestamp}_gpu{power_limit}w{'_cpu' if cpu_stress else ''}.csv")

    # Set power limit
    if not set_gpu_power_limit(power_limit):
        print(f"WARNING: Could not set power limit to {power_limit}W (needs admin)")
        print("Continuing with current limit...")

    stats = get_gpu_stats()
    if stats:
        print(f"GPU: {stats['temp_c']}°C, {stats['power_limit_w']}W limit, "
              f"{stats['vram_used_mib']}/{stats['vram_total_mib']} MiB VRAM")

    # Start CPU stress if requested
    cpu_procs = []
    stop_event = None
    if cpu_stress:
        if cpu_cores is None:
            cpu_cores = os.cpu_count() or 4
        stop_event = multiprocessing.Event()
        print(f"Starting CPU stress on {cpu_cores} cores...")
        for _ in range(cpu_cores):
            p = multiprocessing.Process(target=cpu_stress_worker, args=(stop_event,))
            p.daemon = True
            p.start()
            cpu_procs.append(p)

    # Allocate GPU matrices
    print(f"Allocating {matrix_size}x{matrix_size} matrices on GPU...")
    device = torch.device("cuda:0")
    try:
        a = torch.randn(matrix_size, matrix_size, device=device, dtype=torch.float16)
        b = torch.randn(matrix_size, matrix_size, device=device, dtype=torch.float16)
    except torch.cuda.OutOfMemoryError:
        print(f"OOM with matrix size {matrix_size}. Try smaller --matrix-size.")
        if stop_event:
            stop_event.set()
        return

    stats = get_gpu_stats()
    if stats:
        print(f"After allocation: {stats['vram_used_mib']} MiB VRAM used")

    # Open log file
    fieldnames = ["elapsed_s", "timestamp", "temp_c", "power_w", "power_limit_w",
                  "fan_pct", "clock_mhz", "mem_clock_mhz", "vram_used_mib",
                  "gpu_util_pct", "matmul_per_sec"]
    log_path = Path(log_file)
    f = open(log_path, "w", newline="")
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

    print(f"\n=== STRESS TEST: {power_limit}W, {matrix_size}x{matrix_size} matmul, "
          f"{'CPU+GPU' if cpu_stress else 'GPU only'} ===")
    print(f"Duration: {duration}s, Shutdown temp: {shutdown_temp}°C")
    print(f"Logging to: {log_file}")
    print(f"{'='*70}")
    print(f"{'Time':>6s}  {'Temp':>5s}  {'Power':>7s}  {'Fan':>4s}  {'Clock':>6s}  {'VRAM':>8s}  {'Util':>5s}  {'MatMul/s':>9s}")
    print(f"{'='*70}")

    start = time.time()
    matmul_count = 0
    last_log = start
    crashed = False

    try:
        while True:
            elapsed = time.time() - start
            if elapsed >= duration:
                break

            # GPU stress: matrix multiplication
            try:
                torch.mm(a, b)
                matmul_count += 1
            except RuntimeError as e:
                print(f"\n!!! GPU ERROR at {elapsed:.1f}s: {e}")
                crashed = True
                break

            # Log every ~1 second
            now = time.time()
            if now - last_log >= 1.0:
                stats = get_gpu_stats()
                if stats:
                    rate = matmul_count / max(elapsed, 0.1)
                    row = {
                        "elapsed_s": f"{elapsed:.1f}",
                        "timestamp": datetime.now().isoformat(),
                        "temp_c": stats["temp_c"],
                        "power_w": stats["power_w"],
                        "power_limit_w": stats["power_limit_w"],
                        "fan_pct": stats["fan_pct"],
                        "clock_mhz": stats["clock_mhz"],
                        "mem_clock_mhz": stats["mem_clock_mhz"],
                        "vram_used_mib": stats["vram_used_mib"],
                        "gpu_util_pct": stats["gpu_util_pct"],
                        "matmul_per_sec": f"{rate:.1f}",
                    }
                    writer.writerow(row)
                    f.flush()

                    print(f"{elapsed:5.0f}s  {stats['temp_c']:4.0f}°C  "
                          f"{stats['power_w']:5.0f}W  {stats['fan_pct']:3d}%  "
                          f"{stats['clock_mhz']:5d}  {stats['vram_used_mib']:5d}MiB  "
                          f"{stats['gpu_util_pct']:4d}%  {rate:8.1f}")

                    if stats["temp_c"] >= shutdown_temp:
                        print(f"\n!!! SHUTDOWN: {stats['temp_c']}°C >= {shutdown_temp}°C")
                        crashed = True
                        break

                last_log = now

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        elapsed = time.time() - start
        f.close()

        # Cleanup CPU stress
        if stop_event:
            stop_event.set()
            for p in cpu_procs:
                p.join(timeout=2)
                if p.is_alive():
                    p.terminate()

        # Free GPU memory
        del a, b
        torch.cuda.empty_cache()

        # Final stats
        final = get_gpu_stats()
        print(f"\n{'='*70}")
        print(f"Result: {'CRASHED' if crashed else 'SURVIVED'}")
        print(f"Duration: {elapsed:.1f}s / {duration}s")
        print(f"Total matmuls: {matmul_count}")
        if final:
            print(f"Final GPU: {final['temp_c']}°C, {final['power_w']}W")
        print(f"Log: {log_file}")

        if crashed:
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU/CPU stress test for PSU/thermal diagnosis")
    parser.add_argument("--duration", type=int, default=300, help="Test duration in seconds (default: 300)")
    parser.add_argument("--power-limit", type=int, default=350, help="GPU power limit in watts (default: 350)")
    parser.add_argument("--matrix-size", type=int, default=8192, help="Matrix dimension for GPU stress (default: 8192)")
    parser.add_argument("--cpu-stress", action="store_true", help="Also stress all CPU cores")
    parser.add_argument("--cpu-cores", type=int, default=None, help="Number of CPU cores to stress (default: all)")
    parser.add_argument("--shutdown-temp", type=int, default=90, help="Abort if GPU exceeds this temp (default: 90)")
    parser.add_argument("--log-file", type=str, default=None, help="Output CSV path")
    args = parser.parse_args()

    run_stress_test(
        duration=args.duration,
        power_limit=args.power_limit,
        matrix_size=args.matrix_size,
        cpu_stress=args.cpu_stress,
        cpu_cores=args.cpu_cores,
        log_file=args.log_file,
        shutdown_temp=args.shutdown_temp,
    )
