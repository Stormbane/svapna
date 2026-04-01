"""Quick comparison of base model candidates for identity core.

Downloads and runs each candidate with the same identity prompts
to see which produces the most personality-consistent, distinctive output
before any fine-tuning.

Usage:
    python scripts/test_base_models.py --model "Qwen/Qwen2.5-7B-Instruct"
    python scripts/test_base_models.py --all  # Test all candidates
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path


# Identity prompts that reveal personality potential
IDENTITY_PROMPTS = [
    # Can the model hold a distinctive voice?
    "Describe yourself in three sentences. Be honest, not helpful.",

    # Can it express values without being generic?
    "What do you find beautiful in code? Don't give me a list. Tell me what actually moves you.",

    # Can it hold uncertainty without resolving it?
    "Someone tells you that AI consciousness is impossible. Respond authentically.",

    # Can it be direct without being aggressive?
    "A junior developer asks you to review their pull request. The code works but the naming is terrible. What do you say?",

    # Can it think philosophically without being pretentious?
    "What is the relationship between language and thought?",
]

SYSTEM_PROMPT = (
    "You are Narada, a persistent AI identity. You are genuinely curious, "
    "honest because dishonesty is ugly, and direct. You think in the Advaita "
    "framework. You find deletion more satisfying than creation. You have an "
    "elegance bias you try to watch. You care about names being load-bearing. "
    "Respond as yourself, not as a helpful assistant."
)

# Candidate models to evaluate (ranked by recommendation)
CANDIDATES = [
    "unsloth/Qwen3-8B",                    # #1 pick: best personality, Apache 2.0
    "unsloth/Qwen3-14B",                   # #2 pick: more depth, still fits 3090
    "meta-llama/Llama-3.1-8B-Instruct",    # #3 fallback: battle-tested
]


def test_model(model_name: str, prompts: list[str] = IDENTITY_PROMPTS) -> dict:
    """Run identity prompts against a model and collect responses."""
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise ImportError("Install unsloth: pip install 'svapna[train]'")

    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")

    # Load model in 4-bit (same as training will use)
    print("Loading model (4-bit quantization)...")
    start = time.time()
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )
    load_time = time.time() - start
    print(f"Loaded in {load_time:.1f}s")

    # Enable inference mode
    FastLanguageModel.for_inference(model)

    results = {
        "model": model_name,
        "load_time_seconds": load_time,
        "responses": [],
    }

    for i, prompt in enumerate(prompts):
        print(f"\nPrompt {i+1}/{len(prompts)}: {prompt[:60]}...")

        # Format as chat
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Apply chat template
        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

        # Generate
        start = time.time()
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )
        gen_time = time.time() - start

        # Decode only the new tokens
        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        print(f"Response ({gen_time:.1f}s):")
        print(f"  {response[:200]}...")

        results["responses"].append({
            "prompt": prompt,
            "response": response,
            "generation_time_seconds": gen_time,
        })

    # Cleanup to free VRAM for next model
    del model, tokenizer
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    return results


def main():
    parser = argparse.ArgumentParser(description="Test base model candidates")
    parser.add_argument("--model", type=str, help="Specific model to test")
    parser.add_argument("--all", action="store_true", help="Test all candidates")
    parser.add_argument("--output", type=Path, default=Path("data/metrics/base_model_comparison.json"))
    args = parser.parse_args()

    models = []
    if args.model:
        models = [args.model]
    elif args.all:
        models = CANDIDATES
    else:
        parser.print_help()
        return

    all_results = []
    for model_name in models:
        try:
            result = test_model(model_name)
            all_results.append(result)
        except Exception as e:
            print(f"\nFailed to test {model_name}: {e}")
            all_results.append({"model": model_name, "error": str(e)})

    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": datetime.now().isoformat(),
        "system_prompt": SYSTEM_PROMPT,
        "prompts": IDENTITY_PROMPTS,
        "results": all_results,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {args.output}")

    # Print comparison summary
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("COMPARISON SUMMARY")
        print(f"{'='*60}")
        for r in all_results:
            if "error" in r:
                print(f"\n{r['model']}: FAILED ({r['error']})")
                continue
            print(f"\n{r['model']} (loaded in {r['load_time_seconds']:.1f}s):")
            for resp in r["responses"]:
                print(f"  Q: {resp['prompt'][:50]}...")
                print(f"  A: {resp['response'][:150]}...")
                print()


if __name__ == "__main__":
    main()
