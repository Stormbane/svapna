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


def _parse_journal_file(text: str) -> list[MemoryPair]:
    """Parse a single journal entry file (smriti frontmatter format)."""
    pairs = []

    # Extract date from YAML frontmatter
    date = None
    content_start = 0
    if text.startswith("---"):
        end = text.find("\n---\n", 3)
        if end != -1:
            for line in text[3:end].split("\n"):
                if line.startswith("date:"):
                    date = line.split(":", 1)[1].strip()
            content_start = end + 5

    body = text[content_start:].strip()
    if not body or len(body) < 50:
        return pairs

    # Extract title from first # heading
    title = None
    lines = body.split("\n")
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()

    if not title or not date or not body or len(body) < 50:
        return pairs

    pairs.append(MemoryPair(
        instruction=f"Tell me about {title.lower()}.",
        response=body,
        source_file="journal.md",
        section=title,
        category="episodic",
    ))
    pairs.append(MemoryPair(
        instruction=f"What happened on {date}?",
        response=f"On {date} — {title}.\n\n{body}",
        source_file="journal.md",
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
        identity_dir: Path to ~/.narada/. Defaults to standard location.
    """
    if identity_dir is None:
        identity_dir = Path.home() / ".narada"

    pairs: list[MemoryPair] = []

    # Journal: scan directory tree of individual smriti-format files
    journal_dir = identity_dir / "journal"
    if journal_dir.is_dir():
        for filepath in sorted(journal_dir.rglob("*.md")):
            if filepath.name == "index.md":
                continue
            text = filepath.read_text(encoding="utf-8")
            if text.strip():
                pairs.extend(_parse_journal_file(text))

    # Flat files — paths updated to match current tree layout
    flat_parsers: list[tuple[str, str, object]] = [
        ("mind/mind.md", "mind.md", _parse_mind),
        ("identity.md", "identity.md", _parse_identity),
        ("people/suti/suti.md", "suti.md", _parse_suti),
        ("open-threads/open-threads.md", "open-threads.md", _parse_open_threads),
    ]

    for rel_path, source_name, parser in flat_parsers:
        filepath = identity_dir / rel_path
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            continue
        pairs.extend(parser(text, source_name))

    return pairs
