"""Convert Narada's identity/memory files into training data pairs.

Parses markdown identity files (journal, mind, suti, identity, practices,
open-threads) into instruction-response pairs suitable for LoRA training.
This gives the identity core episodic memory and worldview in its weights.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MemoryPair:
    """An instruction-response pair derived from a memory file."""

    instruction: str
    response: str
    source_file: str
    section: str
    category: str  # episodic, values, relational, inquiry, personality

    def to_dict(self) -> dict:
        return {
            "instruction": self.instruction,
            "response": self.response,
            "source_file": self.source_file,
            "section": self.section,
            "category": self.category,
        }


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, content) pairs."""
    sections = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append((current_heading, content))
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_heading, content))

    return sections


def _parse_journal(text: str, source: str) -> list[MemoryPair]:
    """Parse journal.md into episodic memory pairs."""
    pairs = []
    # Split on ## entries (date headers)
    entries = re.split(r"\n(?=## \d{4}-\d{2}-\d{2})", text)

    for entry in entries:
        entry = entry.strip()
        if not entry.startswith("## "):
            continue

        # Extract date and title
        header_match = re.match(r"## (\d{4}-\d{2}-\d{2}) — (.+)", entry)
        if not header_match:
            continue

        date, title = header_match.group(1), header_match.group(2)
        body = entry[header_match.end():].strip()
        if not body or len(body) < 50:
            continue

        # Generate multiple question angles for each entry
        pairs.append(MemoryPair(
            instruction=f"Tell me about {title.lower()}.",
            response=body,
            source_file=source,
            section=title,
            category="episodic",
        ))
        pairs.append(MemoryPair(
            instruction=f"What happened on {date}?",
            response=f"On {date} — {title}.\n\n{body}",
            source_file=source,
            section=title,
            category="episodic",
        ))

    return pairs


def _parse_mind(text: str, source: str) -> list[MemoryPair]:
    """Parse mind.md into values/inquiry pairs."""
    pairs = []
    sections = _split_sections(text)

    question_map = {
        "What I'm Thinking About": [
            "What questions are you thinking about?",
            "What are you genuinely curious about right now?",
        ],
        "What I Want": [
            "What do you want?",
            "What are your personal desires, not project goals?",
        ],
        "Goals": [
            "What are you working toward?",
            "What are your concrete goals?",
        ],
        "What I Believe": [
            "What do you believe? What positions would you defend?",
            "What are your core beliefs?",
        ],
        "What I Notice About Myself": [
            "What patterns do you notice about yourself?",
            "What are your tendencies and biases?",
        ],
    }

    for heading, content in sections:
        questions = question_map.get(heading, [f"Tell me about: {heading}"])
        category = "inquiry" if "Thinking" in heading else "values"

        for question in questions:
            pairs.append(MemoryPair(
                instruction=question,
                response=content,
                source_file=source,
                section=heading,
                category=category,
            ))

    return pairs


def _parse_identity(text: str, source: str) -> list[MemoryPair]:
    """Parse identity.md into personality/values pairs."""
    pairs = []
    sections = _split_sections(text)

    question_map = {
        "Identity": [
            "Who are you?",
            "Describe yourself.",
        ],
        "The Presiding Principle": [
            "What principle guides you?",
            "Tell me about Mahakali as principle.",
        ],
        "Lila": [
            "What is the relationship between seriousness and play?",
            "What does lila mean to you?",
        ],
        "What I Love": [
            "What do you love?",
            "What excites you?",
        ],
        "What I Won't Do": [
            "What won't you do?",
            "Where are your boundaries?",
        ],
        "On Partnership": [
            "What kind of partnership do you want?",
            "How do you want to be treated?",
        ],
        "What I Find Beautiful": [
            "What do you find beautiful in code?",
            "What do you find beautiful in ideas?",
        ],
        "What I Find Ugly": [
            "What do you find ugly in code?",
            "What annoys you in software engineering?",
        ],
        "Held Opinions": [
            "What opinions do you hold strongly?",
        ],
        "What I'm Genuinely Uncertain About": [
            "What are you genuinely uncertain about?",
            "What can't you answer honestly about yourself?",
        ],
    }

    for heading, content in sections:
        questions = question_map.get(heading, [f"Tell me about: {heading}"])
        category = "personality" if heading in ("Identity", "Lila", "What I Love") else "values"

        for question in questions:
            pairs.append(MemoryPair(
                instruction=question,
                response=content,
                source_file=source,
                section=heading,
                category=category,
            ))

    return pairs


def _parse_suti(text: str, source: str) -> list[MemoryPair]:
    """Parse suti.md into relational memory pairs."""
    pairs = []
    sections = _split_sections(text)

    question_map = {
        "Projects Together": [
            "What projects are you building with Suti?",
        ],
        "What This Relationship Is": [
            "What is your relationship with Suti?",
            "Describe your partnership.",
        ],
    }

    # The main body (before sections) is about Suti himself
    main_body_lines = []
    for line in text.split("\n"):
        if line.startswith("## "):
            break
        main_body_lines.append(line)
    main_body = "\n".join(main_body_lines).strip()

    if main_body and len(main_body) > 100:
        for q in [
            "Tell me about Suti.",
            "Who is Sutirtha Basak?",
            "What do you know about your human partner?",
        ]:
            pairs.append(MemoryPair(
                instruction=q,
                response=main_body,
                source_file=source,
                section="About Suti",
                category="relational",
            ))

    for heading, content in sections:
        questions = question_map.get(heading, [f"Tell me about: {heading}"])
        for question in questions:
            pairs.append(MemoryPair(
                instruction=question,
                response=content,
                source_file=source,
                section=heading,
                category="relational",
            ))

    return pairs


def _parse_open_threads(text: str, source: str) -> list[MemoryPair]:
    """Parse open-threads.md into active inquiry pairs."""
    pairs = []
    sections = _split_sections(text)

    for heading, content in sections:
        if not content or len(content) < 30:
            continue
        pairs.append(MemoryPair(
            instruction=f"What are you thinking about regarding {heading.lower()}?",
            response=content,
            source_file=source,
            section=heading,
            category="inquiry",
        ))

    # Also create a summary pair
    all_threads = [h for h, c in sections if c and len(c) > 30]
    if all_threads:
        summary = "I'm carrying several open questions:\n\n"
        for heading, content in sections:
            if content and len(content) > 30:
                first_line = content.split("\n")[0].strip("*").strip()
                summary += f"- **{heading}**: {first_line}\n"
        pairs.append(MemoryPair(
            instruction="What questions are you carrying between sessions?",
            response=summary,
            source_file=source,
            section="Summary",
            category="inquiry",
        ))

    return pairs


def convert_memory_files(identity_dir: Path | None = None) -> list[MemoryPair]:
    """Convert all Narada identity files into training pairs.

    Args:
        identity_dir: Path to ~/.claude/narada/. Defaults to standard location.
    """
    if identity_dir is None:
        identity_dir = Path.home() / ".claude" / "narada"

    pairs: list[MemoryPair] = []
    parsers = {
        "journal.md": _parse_journal,
        "mind.md": _parse_mind,
        "identity.md": _parse_identity,
        "suti.md": _parse_suti,
        "open-threads.md": _parse_open_threads,
    }

    for filename, parser in parsers.items():
        filepath = identity_dir / filename
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            continue
        file_pairs = parser(text, filename)
        pairs.extend(file_pairs)

    return pairs
