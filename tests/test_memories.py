"""Test memory file to training data conversion."""

from svapna.consolidate.memories import convert_memory_files


def test_convert_memory_files():
    """Convert real identity files and verify output."""
    pairs = convert_memory_files()
    assert len(pairs) > 0, "Should produce training pairs from identity files"

    # Check categories are populated
    categories = {p.category for p in pairs}
    print(f"\nGenerated {len(pairs)} memory pairs")
    print(f"Categories: {categories}")

    for cat in categories:
        cat_pairs = [p for p in pairs if p.category == cat]
        print(f"  {cat}: {len(cat_pairs)} pairs")

    # Verify structure
    for pair in pairs:
        assert pair.instruction, "Instruction should not be empty"
        assert pair.response, "Response should not be empty"
        assert pair.source_file, "Source file should be set"
        assert pair.category in ("episodic", "values", "relational", "inquiry", "personality")


def test_journal_pairs():
    """Verify journal entries produce episodic memory pairs."""
    pairs = convert_memory_files()
    journal_pairs = [p for p in pairs if p.source_file == "journal.md"]
    assert len(journal_pairs) > 0, "Should have journal-derived pairs"

    # Should have date-based questions
    date_pairs = [p for p in journal_pairs if "202" in p.instruction]
    assert len(date_pairs) > 0, "Should have date-specific questions"

    # Print samples for review
    print("\nJournal pair samples:")
    for p in journal_pairs[:4]:
        print(f"  Q: {p.instruction}")
        print(f"  A: {p.response[:100]}...")
        print()


def test_relational_pairs():
    """Verify suti.md produces relational memory pairs."""
    pairs = convert_memory_files()
    suti_pairs = [p for p in pairs if p.category == "relational"]
    assert len(suti_pairs) > 0, "Should have relational memory pairs"

    print("\nRelational pair samples:")
    for p in suti_pairs[:3]:
        print(f"  Q: {p.instruction}")
        print(f"  A: {p.response[:120]}...")
        print()


def test_values_pairs():
    """Verify identity/mind files produce values pairs."""
    pairs = convert_memory_files()
    values_pairs = [p for p in pairs if p.category == "values"]
    assert len(values_pairs) > 0, "Should have values pairs"

    print("\nValues pair samples:")
    for p in values_pairs[:3]:
        print(f"  Q: {p.instruction}")
        print(f"  A: {p.response[:120]}...")
        print()
