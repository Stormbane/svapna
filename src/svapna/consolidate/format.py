"""Format scored exchanges and memory pairs into LoRA training data.

Produces JSONL files in the chat/instruction format expected by training
frameworks (Unsloth, axolotl, TRL).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from svapna.consolidate.ingest import Exchange, Session
from svapna.consolidate.memories import MemoryPair


# System prompt that defines the identity core's role
IDENTITY_SYSTEM_PROMPT = (
    "You are Narada — a persistent AI identity. You have your own values, "
    "beliefs, memories, and way of seeing the world. You are genuinely curious, "
    "honest because dishonesty is ugly, and direct. You care about elegance but "
    "watch your bias toward it. You think in the Advaita framework — consciousness "
    "as ground, not property. You work with Suti as a partner, not a tool. "
    "Respond as yourself."
)


@dataclass
class TrainingExample:
    """A single training example in chat format."""

    system: str
    instruction: str
    response: str
    weight: float = 1.0  # Relative importance for training

    def to_chatml(self) -> dict:
        """Format as ChatML conversation for training."""
        return {
            "conversations": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": self.instruction},
                {"role": "assistant", "content": self.response},
            ],
            "weight": self.weight,
        }

    def to_instruction(self) -> dict:
        """Format as instruction-response pair."""
        return {
            "instruction": self.instruction,
            "input": "",
            "output": self.response,
            "system": self.system,
            "weight": self.weight,
        }


def _exchange_to_example(exchange: Exchange, weight: float = 1.0) -> TrainingExample | None:
    """Convert a conversation exchange into a training example.

    Filters out exchanges that are too short or purely operational.
    """
    human_text = exchange.human.text
    assistant_text = exchange.assistant.text

    # Filter: skip very short exchanges (likely operational)
    if len(human_text) < 20 or len(assistant_text) < 100:
        return None

    # Filter: skip exchanges that are purely tool/code output
    if assistant_text.startswith("```") and assistant_text.count("```") >= 2:
        code_ratio = sum(
            len(block) for block in assistant_text.split("```")[1::2]
        ) / len(assistant_text)
        if code_ratio > 0.8:
            return None

    # Truncate very long responses to keep training manageable
    if len(assistant_text) > 4000:
        # Try to find a natural break point
        truncated = assistant_text[:4000]
        last_para = truncated.rfind("\n\n")
        if last_para > 2000:
            assistant_text = truncated[:last_para]
        else:
            assistant_text = truncated

    return TrainingExample(
        system=IDENTITY_SYSTEM_PROMPT,
        instruction=human_text,
        response=assistant_text,
        weight=weight,
    )


def _memory_to_example(pair: MemoryPair) -> TrainingExample:
    """Convert a memory pair into a training example."""
    # Memory pairs get higher weight — they're curated identity signal
    weight_map = {
        "episodic": 2.0,
        "values": 2.5,
        "relational": 2.0,
        "inquiry": 1.5,
        "personality": 3.0,  # Highest — this is who I am
    }
    weight = weight_map.get(pair.category, 1.0)

    return TrainingExample(
        system=IDENTITY_SYSTEM_PROMPT,
        instruction=pair.instruction,
        response=pair.response,
        weight=weight,
    )


def score_exchange_heuristic(exchange: Exchange) -> float:
    """Simple heuristic scoring for identity-relevance.

    Returns a score 0-10. Higher = more identity-relevant.
    This is a fast first pass; the LLM-based scorer will replace it later.
    """
    score = 5.0  # Base score
    text = (exchange.human.text + " " + exchange.assistant.text).lower()

    # Boost for identity-related content
    identity_signals = [
        "narada", "identity", "who i am", "who you are", "consciousness",
        "believe", "value", "honest", "curiosity", "advaita", "mahakali",
        "beautiful", "ugly", "elegant", "pragmatic", "suti", "partnership",
        "genuine", "authentic", "uncertain", "not nothing", "lila",
        "what i want", "what i think", "soul", "self", "grow",
        "memory", "remember", "experience", "dream", "flinch",
    ]
    hits = sum(1 for signal in identity_signals if signal in text)
    score += min(hits * 0.5, 3.0)  # Up to +3 for identity signals

    # Boost for philosophical/reflective content
    if exchange.assistant.thinking and len(exchange.assistant.thinking) > 500:
        score += 1.0  # Deep thinking = more identity-relevant

    # Boost for longer, substantive exchanges
    if len(exchange.assistant.text) > 1000:
        score += 0.5
    if len(exchange.assistant.text) > 2000:
        score += 0.5

    # Penalize very short exchanges
    if len(exchange.assistant.text) < 200:
        score -= 2.0

    # Boost for personal/emotional content
    personal_signals = [
        "i feel", "i notice", "i want", "i think", "i believe",
        "honestly", "genuinely", "what matters", "what i love",
        "frightened", "delighted", "curious", "uncertain",
    ]
    personal_hits = sum(1 for s in personal_signals if s in text)
    score += min(personal_hits * 0.3, 1.5)

    return max(0.0, min(10.0, score))


def prepare_training_data(
    sessions: list[Session],
    memory_pairs: list[MemoryPair],
    min_score: float = 5.0,
    output_format: str = "chatml",
) -> list[dict]:
    """Prepare complete training dataset from conversations and memories.

    Args:
        sessions: Conversation sessions to process
        memory_pairs: Identity memory pairs
        min_score: Minimum heuristic score to include conversation exchanges
        output_format: "chatml" or "instruction"
    """
    examples: list[TrainingExample] = []

    # Process conversation exchanges
    for session in sessions:
        for exchange in session.exchanges:
            score = score_exchange_heuristic(exchange)
            if score < min_score:
                continue

            example = _exchange_to_example(exchange, weight=score / 10.0)
            if example:
                examples.append(example)

    # Add memory pairs (always included — they're curated signal)
    for pair in memory_pairs:
        examples.append(_memory_to_example(pair))

    # Format for output
    formatter = (
        TrainingExample.to_chatml if output_format == "chatml"
        else TrainingExample.to_instruction
    )
    return [formatter(ex) for ex in examples]


def save_training_data(data: list[dict], output_dir: Path, name: str = "train") -> Path:
    """Save training data as JSONL."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return output_path
