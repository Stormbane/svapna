"""LoRA fine-tuning for the identity core model.

Uses Unsloth for efficient QLoRA training on consumer GPUs.
Conservative settings for RTX 3090 with thermal concerns.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

# Windows: Unsloth compiles trainers to a local cache that spawned workers can't find.
# Add it to sys.path so multiprocessing workers can import UnslothSFTTrainer.
_cache_dir = Path(__file__).resolve().parent.parent.parent.parent / "unsloth_compiled_cache"
if _cache_dir.exists() and str(_cache_dir) not in sys.path:
    sys.path.insert(0, str(_cache_dir))

logger = logging.getLogger(__name__)


def load_training_config(config_path: Path | None = None) -> dict:
    """Load training configuration from YAML."""
    if config_path is None:
        config_path = Path("config/training.yml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_gpu_temp() -> float | None:
    """Read current GPU temperature via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return float(result.stdout.strip().split("\n")[0])
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def get_gpu_memory() -> dict | None:
    """Read GPU memory usage via nvidia-smi. Returns dict with used/total in MiB."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            return {"used_mib": int(parts[0].strip()), "total_mib": int(parts[1].strip())}
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError):
        pass
    return None


def get_gpu_power_and_fan() -> dict | None:
    """Read GPU power draw and fan speed via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.draw,fan.speed,clocks.gr,clocks.mem",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            return {
                "power_w": float(parts[0].strip()),
                "fan_pct": int(parts[1].strip()),
                "clock_mhz": int(parts[2].strip()),
                "mem_mhz": int(parts[3].strip()),
            }
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError):
        pass
    return None


def set_gpu_power_limit(watts: int) -> bool:
    """Set GPU power limit for thermal management."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-pl", str(watts)],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _make_thermal_callback(thermal_config: dict, base_class: type, diag_path: Path | None = None):
    """Create a thermal monitoring callback with the proper TrainerCallback base.

    Factory function because TrainerCallback is a heavy import (transformers)
    that we only load when actually training.
    """

    class ThermalMonitorCallback(base_class):
        """Monitors GPU temperature and VRAM during training.

        Logs diagnostics every step to a file for crash analysis.
        Checks thermal limits every `check_interval` steps.
        """

        def __init__(self):
            super().__init__()
            self.max_temp = thermal_config.get("max_temp_celsius", 83)
            self.shutdown_temp = thermal_config.get("shutdown_temp_celsius", 90)
            self.check_interval = thermal_config.get("temp_check_interval", 50)
            self.cooldown_seconds = thermal_config.get("cooldown_seconds", 60)
            self.temps: list[dict] = []
            self.diag_path = diag_path
            if self.diag_path:
                self.diag_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.diag_path, "w") as f:
                    f.write("step,timestamp,temp_c,vram_used_mib,vram_total_mib,power_w,fan_pct,clock_mhz,mem_mhz,loss\n")

        def _log_diagnostics(self, step, loss=None):
            """Write one row of diagnostics to CSV."""
            if not self.diag_path:
                return
            temp = get_gpu_temp()
            mem = get_gpu_memory()
            pf = get_gpu_power_and_fan()
            row = (
                f"{step},{datetime.now().isoformat()},"
                f"{temp if temp else ''},"
                f"{mem['used_mib'] if mem else ''},"
                f"{mem['total_mib'] if mem else ''},"
                f"{pf['power_w'] if pf else ''},"
                f"{pf['fan_pct'] if pf else ''},"
                f"{pf['clock_mhz'] if pf else ''},"
                f"{pf['mem_mhz'] if pf else ''},"
                f"{loss if loss is not None else ''}\n"
            )
            try:
                with open(self.diag_path, "a") as f:
                    f.write(row)
            except OSError:
                pass

        def on_step_end(self, args, state, control, **kwargs):
            self._log_diagnostics(state.global_step)

            if state.global_step % self.check_interval != 0:
                return
            temp = get_gpu_temp()
            if temp is None:
                return
            mem = get_gpu_memory()
            vram_str = f", VRAM {mem['used_mib']}/{mem['total_mib']} MiB" if mem else ""
            self.temps.append({"step": state.global_step, "temp": temp,
                               **({"vram_used": mem["used_mib"]} if mem else {})})
            logger.info("Step %d: %.0f°C%s", state.global_step, temp, vram_str)

            if temp >= self.shutdown_temp:
                logger.error(
                    "GPU at %.0f°C (shutdown threshold %.0f°C) — aborting training",
                    temp, self.shutdown_temp,
                )
                control.should_training_stop = True
                return
            if temp >= self.max_temp:
                logger.warning(
                    "GPU at %.0f°C (max %.0f°C) — pausing %ds for cooldown",
                    temp, self.max_temp, self.cooldown_seconds,
                )
                time.sleep(self.cooldown_seconds)
                temp_after = get_gpu_temp()
                logger.info(
                    "Cooldown complete. GPU temp: %.0f°C",
                    temp_after if temp_after else -1,
                )

        def on_log(self, args, state, control, logs=None, **kwargs):
            temp = get_gpu_temp()
            mem = get_gpu_memory()
            if logs is not None:
                if temp is not None:
                    logs["gpu_temp"] = temp
                if mem is not None:
                    logs["vram_used_mib"] = mem["used_mib"]
            loss = logs.get("loss") if logs else None
            self._log_diagnostics(state.global_step, loss=loss)

    return ThermalMonitorCallback()


def train(
    training_data_path: Path,
    output_dir: Path | None = None,
    config_path: Path | None = None,
    base_model: str | None = None,
    dry_run: bool = False,
) -> Path:
    """Run LoRA fine-tuning on the identity core.

    Args:
        training_data_path: Path to training JSONL file
        output_dir: Where to save the LoRA adapter. Defaults to models/lora/{date}/
        config_path: Training config YAML. Defaults to config/training.yml
        base_model: Override base model name
        dry_run: If True, validate setup without training

    Returns:
        Path to the saved LoRA adapter directory
    """
    config = load_training_config(config_path)

    # Resolve model name
    model_name = base_model or config.get("base_model", {}).get("name")
    if not model_name or model_name == "TBD":
        raise ValueError(
            "Base model not configured. Set it in config/training.yml or pass --base-model"
        )

    # Windows: disable torch.compile (triton incompatibility)
    os.environ["TORCHDYNAMO_DISABLE"] = "1"

    # Resolve output directory
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path("models/lora") / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set GPU power limit for thermal safety
    thermal = config.get("thermal", {})
    power_limit = thermal.get("power_limit_watts", 280)
    if set_gpu_power_limit(power_limit):
        print(f"GPU power limit set to {power_limit}W")
    else:
        print("Warning: could not set GPU power limit")

    # Check initial GPU temp
    temp = get_gpu_temp()
    if temp is not None:
        print(f"GPU temperature: {temp}°C")
        max_temp = thermal.get("max_temp_celsius", 83)
        if temp > max_temp:
            raise RuntimeError(
                f"GPU already at {temp}°C (max {max_temp}°C). Cool down before training."
            )

    if dry_run:
        print("\n=== DRY RUN ===")
        print(f"Model: {model_name}")
        print(f"Training data: {training_data_path}")
        print(f"Output: {output_dir}")
        print(f"Config: {json.dumps(config, indent=2)}")
        return output_dir

    # Import training libraries (heavy imports, only when actually training)
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise ImportError(
            "Unsloth not installed. Run: pip install 'svapna[train]'\n"
            "Or: pip install unsloth[cu121-torch240]"
        )

    from datasets import Dataset
    from trl import ORPOTrainer, ORPOConfig
    from transformers import TrainerCallback

    print(f"\nLoading base model: {model_name}")

    # Load model with 4-bit quantization
    lora_config = config.get("lora", {})
    training_config = config.get("training", {})
    max_seq_length = training_config.get("max_seq_length", 2048)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # Apply LoRA — research-backed defaults from personality-finetuning-research.md
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_config.get("r", 32),
        lora_alpha=lora_config.get("alpha", 64),
        lora_dropout=lora_config.get("dropout", 0.1),
        target_modules=lora_config.get("target_modules", [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]),
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # Load training data
    print(f"Loading training data from {training_data_path}")
    with open(training_data_path, encoding="utf-8") as f:
        raw_data = [json.loads(line) for line in f if line.strip()]

    # Split into train/validation sets
    data_config = config.get("data", {})
    val_split = data_config.get("validation_split", 0.1)
    val_size = max(1, int(len(raw_data) * val_split))
    import random
    random.seed(training_config.get("seed", 42))
    random.shuffle(raw_data)
    val_data = raw_data[:val_size]
    train_data = raw_data[val_size:]
    print(f"  Train: {len(train_data)} examples, Validation: {len(val_data)} examples")

    # ORPO format: each example has {prompt, chosen, rejected}
    # TRL's ORPOTrainer accepts this conversational format directly —
    # prompt is a list of turns; chosen/rejected are lists of one assistant turn.
    # No pre-formatting needed; TRL applies the chat template internally.

    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data)

    print(f"Training on {len(train_dataset)} preference pairs "
          f"(validating on {len(val_dataset)})")

    # Training arguments — ORPOConfig is a TrainingArguments subclass
    orpo_config = config.get("orpo", {})
    beta = orpo_config.get("beta", 0.1)  # ORPO odds-ratio β; TRL default 0.1

    save_strategy = training_config.get("save_strategy", "epoch")
    save_steps = training_config.get("save_steps", None)
    args_kwargs = {}
    if save_strategy == "steps":
        args_kwargs["save_steps"] = save_steps or 20

    args = ORPOConfig(
        output_dir=str(output_dir),
        beta=beta,
        max_length=max_seq_length,
        max_prompt_length=max_seq_length // 2,
        per_device_train_batch_size=training_config.get("per_device_train_batch_size", 1),
        gradient_accumulation_steps=training_config.get("gradient_accumulation_steps", 4),
        num_train_epochs=training_config.get("num_train_epochs", 1),
        learning_rate=training_config.get("learning_rate", 1e-4),
        lr_scheduler_type=training_config.get("lr_scheduler_type", "cosine"),
        warmup_ratio=training_config.get("warmup_ratio", 0.03),
        fp16=not training_config.get("bf16", True),
        bf16=training_config.get("bf16", True),
        logging_steps=training_config.get("logging_steps", 10),
        save_strategy=save_strategy,
        seed=training_config.get("seed", 42),
        optim=training_config.get("optim", "paged_adamw_8bit"),
        report_to="none",
        dataloader_num_workers=0,
        dataset_num_proc=1,  # Windows: multiprocessing breaks Unsloth
        **args_kwargs,
    )
    if training_config.get("weight_decay"):
        args.weight_decay = training_config["weight_decay"]

    # Thermal + VRAM monitoring callback
    diag_path = output_dir / "diagnostics.csv"
    thermal_callback = _make_thermal_callback(thermal, TrainerCallback, diag_path)

    trainer = ORPOTrainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        args=args,
        processing_class=tokenizer,
        callbacks=[thermal_callback],
    )

    # Train
    print("\n=== Starting LoRA Training ===")
    print(f"Diagnostics logging to: {diag_path}")
    start_time = time.time()

    training_crashed = False
    try:
        trainer.train()
    except Exception as e:
        training_crashed = True
        elapsed = time.time() - start_time
        error_msg = f"Training crashed at {elapsed / 60:.1f} min: {type(e).__name__}: {e}"
        logger.error(error_msg)
        print(f"\n!!! {error_msg}")
        # Save crash info alongside diagnostics
        crash_path = output_dir / "crash_report.txt"
        import traceback
        with open(crash_path, "w") as f:
            f.write(f"Crash time: {datetime.now().isoformat()}\n")
            f.write(f"Elapsed: {elapsed:.1f}s ({elapsed / 60:.1f} min)\n")
            f.write(f"Error: {error_msg}\n\n")
            f.write(traceback.format_exc())
            temp = get_gpu_temp()
            mem = get_gpu_memory()
            f.write(f"\nGPU temp at crash: {temp}\n")
            f.write(f"GPU memory at crash: {mem}\n")
            f.write(f"\nThermal history: {thermal_callback.temps}\n")
        print(f"Crash report saved to: {crash_path}")
        # Try to save whatever state we can
        try:
            emergency_dir = output_dir / "emergency-save"
            emergency_dir.mkdir(exist_ok=True)
            model.save_pretrained(str(emergency_dir))
            tokenizer.save_pretrained(str(emergency_dir))
            print(f"Emergency checkpoint saved to: {emergency_dir}")
        except Exception as save_err:
            print(f"Could not save emergency checkpoint: {save_err}")

    elapsed = time.time() - start_time
    if not training_crashed:
        print(f"\nTraining complete in {elapsed / 60:.1f} minutes")

    if not training_crashed:
        # Save the LoRA adapter
        print(f"Saving LoRA adapter to {output_dir}")
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))

        # Update latest — use a directory junction on Windows (no admin needed),
        # plain symlink elsewhere. Junctions behave like symlinks for path
        # resolution; PEFT and Unsloth read through them fine.
        latest_link = output_dir.parent / "latest"
        try:
            if os.name == "nt":
                # Windows: prefer junction (no admin). Only remove old link if
                # we can create the new one first — atomic-ish: try mklink,
                # only unlink on success.
                if latest_link.exists() or latest_link.is_symlink():
                    subprocess.run(["cmd", "/c", "rmdir", str(latest_link)],
                                   check=False, capture_output=True)
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(latest_link),
                     str(output_dir.resolve())],
                    capture_output=True, text=True,
                )
                if result.returncode == 0:
                    print(f"'latest' junction -> {output_dir.name}")
                else:
                    print(f"Warning: mklink /J failed: {result.stderr.strip()}")
                    print(f"  Adapter saved at: {output_dir}")
            else:
                if latest_link.exists() or latest_link.is_symlink():
                    latest_link.unlink()
                latest_link.symlink_to(output_dir.name)
                print(f"'latest' symlink -> {output_dir.name}")
        except OSError as e:
            print(f"Warning: could not create 'latest' link: {e}")
            print(f"  Adapter saved at: {output_dir}")

    # Save training metadata (always, even on crash)
    metadata = {
        "base_model": model_name,
        "training_data": str(training_data_path),
        "num_train_examples": len(train_dataset),
        "num_val_examples": len(val_dataset),
        "training_time_seconds": elapsed,
        "timestamp": datetime.now().isoformat(),
        "crashed": training_crashed,
        "lora_config": {
            "r": lora_config.get("r", 32),
            "alpha": lora_config.get("alpha", 64),
            "dropout": lora_config.get("dropout", 0.1),
        },
        "training_config": {
            "epochs": training_config.get("num_train_epochs", 2),
            "learning_rate": training_config.get("learning_rate", 1e-4),
            "weight_decay": training_config.get("weight_decay", 0.01),
            "max_seq_length": max_seq_length,
        },
        "gpu_temp_start": temp,
        "gpu_temp_end": get_gpu_temp(),
        "gpu_temp_history": thermal_callback.temps,
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Final GPU temp
    final_temp = get_gpu_temp()
    if final_temp:
        print(f"GPU temperature after training: {final_temp}°C")

    if training_crashed:
        print(f"\nTraining crashed but diagnostics saved to {output_dir}")
        print(f"Check diagnostics.csv and crash_report.txt for analysis")
    else:
        print(f"\nLoRA adapter saved to {output_dir}")
        print(f"Symlink 'latest' updated")
    return output_dir
