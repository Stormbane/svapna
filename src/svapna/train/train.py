"""LoRA fine-tuning for the identity core model.

Uses Unsloth for efficient QLoRA training on consumer GPUs.
Conservative settings for RTX 3090 with thermal concerns.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import yaml


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
    from trl import SFTTrainer
    from transformers import TrainingArguments

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

    # Format for training — use Qwen3 chat template
    # IMPORTANT: enable_thinking=False for Qwen3 personality training
    def format_example(example):
        conversations = example.get("conversations", [])
        # Use the tokenizer's chat template for correct Qwen3 formatting
        messages = []
        for msg in conversations:
            messages.append({"role": msg["role"], "content": msg["content"]})
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False,
                enable_thinking=False,
            )
        except TypeError:
            # Fallback if enable_thinking not supported
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False,
            )
        if not text.endswith(tokenizer.eos_token):
            text += tokenizer.eos_token
        return {"text": text}

    train_dataset = Dataset.from_list(train_data)
    train_dataset = train_dataset.map(format_example)
    val_dataset = Dataset.from_list(val_data)
    val_dataset = val_dataset.map(format_example)

    print(f"Training on {len(train_dataset)} examples (validating on {len(val_dataset)})")

    # Training arguments
    args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=training_config.get("per_device_train_batch_size", 1),
        gradient_accumulation_steps=training_config.get("gradient_accumulation_steps", 4),
        num_train_epochs=training_config.get("num_train_epochs", 2),
        learning_rate=training_config.get("learning_rate", 1e-4),
        lr_scheduler_type=training_config.get("lr_scheduler_type", "cosine"),
        warmup_ratio=training_config.get("warmup_ratio", 0.03),
        fp16=not training_config.get("bf16", True),
        bf16=training_config.get("bf16", True),
        logging_steps=training_config.get("logging_steps", 10),
        save_strategy=training_config.get("save_strategy", "epoch"),
        seed=training_config.get("seed", 42),
        optim=training_config.get("optim", "paged_adamw_8bit"),
        report_to="none",
    )

    # Add weight decay from config
    if training_config.get("weight_decay"):
        args.weight_decay = training_config["weight_decay"]

    # Trainer with validation for overfitting detection
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        args=args,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        tokenizer=tokenizer,
    )

    # Train
    print("\n=== Starting LoRA Training ===")
    start_time = time.time()

    trainer.train()

    elapsed = time.time() - start_time
    print(f"\nTraining complete in {elapsed / 60:.1f} minutes")

    # Save the LoRA adapter
    print(f"Saving LoRA adapter to {output_dir}")
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Update latest symlink
    latest_link = output_dir.parent / "latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_dir.name)

    # Save training metadata
    metadata = {
        "base_model": model_name,
        "training_data": str(training_data_path),
        "num_train_examples": len(train_dataset),
        "num_val_examples": len(val_dataset),
        "training_time_seconds": elapsed,
        "timestamp": datetime.now().isoformat(),
        "lora_config": {
            "r": lora_config.get("r", 32),
            "alpha": lora_config.get("alpha", 64),
            "dropout": lora_config.get("dropout", 0.1),
        },
        "training_config": {
            "epochs": training_config.get("num_train_epochs", 2),
            "learning_rate": training_config.get("learning_rate", 1e-4),
            "weight_decay": training_config.get("weight_decay", 0.01),
        },
        "gpu_temp_start": temp,
        "gpu_temp_end": get_gpu_temp(),
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Final GPU temp
    final_temp = get_gpu_temp()
    if final_temp:
        print(f"GPU temperature after training: {final_temp}°C")

    print(f"\nLoRA adapter saved to {output_dir}")
    print(f"Symlink 'latest' updated")
    return output_dir
