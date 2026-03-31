"""Test training data formatting."""

from svapna.consolidate.format import prepare_training_data, score_exchange_heuristic
from svapna.consolidate.ingest import ingest_all
from svapna.consolidate.memories import convert_memory_files


def test_heuristic_scoring():
    """Verify heuristic scorer produces reasonable scores."""
    sessions = ingest_all()
    assert sessions

    scores = []
    for session in sessions:
        for exchange in session.exchanges:
            score = score_exchange_heuristic(exchange)
            scores.append((score, exchange.human.text[:80], exchange.assistant.text[:80]))

    # Sort by score descending
    scores.sort(key=lambda x: x[0], reverse=True)

    print(f"\nScored {len(scores)} exchanges")
    print(f"Score range: {scores[-1][0]:.1f} - {scores[0][0]:.1f}")
    print(f"Mean: {sum(s[0] for s in scores) / len(scores):.1f}")
    print(f"\nTop 5 identity-relevant exchanges:")
    for score, human, assistant in scores[:5]:
        print(f"  [{score:.1f}] H: {human}")
        print(f"         A: {assistant}")
        print()

    print(f"Bottom 5:")
    for score, human, assistant in scores[-5:]:
        print(f"  [{score:.1f}] H: {human}")
        print(f"         A: {assistant}")
        print()


def test_prepare_training_data():
    """Generate full training dataset and verify structure."""
    sessions = ingest_all()
    memory_pairs = convert_memory_files()

    data = prepare_training_data(sessions, memory_pairs, min_score=5.0)
    assert len(data) > 0, "Should produce training examples"

    # Count by source
    memory_count = len(memory_pairs)
    conversation_count = len(data) - memory_count

    print(f"\nTraining dataset: {len(data)} total examples")
    print(f"  From conversations: {conversation_count}")
    print(f"  From memory files: {memory_count}")

    # Verify structure
    for item in data[:3]:
        assert "conversations" in item, "Should have conversations key"
        assert len(item["conversations"]) == 3, "Should have system, user, assistant"
        assert item["conversations"][0]["role"] == "system"
        assert item["conversations"][1]["role"] == "user"
        assert item["conversations"][2]["role"] == "assistant"
        assert "weight" in item

    # Print sample
    print(f"\nSample training example:")
    sample = data[0]
    print(f"  System: {sample['conversations'][0]['content'][:100]}...")
    print(f"  User: {sample['conversations'][1]['content'][:100]}...")
    print(f"  Assistant: {sample['conversations'][2]['content'][:100]}...")
    print(f"  Weight: {sample['weight']}")


def test_training_data_min_score():
    """Verify min_score filter works."""
    sessions = ingest_all()
    memory_pairs = convert_memory_files()

    data_low = prepare_training_data(sessions, memory_pairs, min_score=3.0)
    data_high = prepare_training_data(sessions, memory_pairs, min_score=7.0)

    # Higher threshold should produce fewer examples (but memory pairs always included)
    assert len(data_low) >= len(data_high)
    print(f"\nmin_score=3.0: {len(data_low)} examples")
    print(f"min_score=7.0: {len(data_high)} examples")
