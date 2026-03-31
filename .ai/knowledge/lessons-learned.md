# Lessons Learned

<!-- Distilled insights from past work. Added by the Introspector agent (v0.2+) or manually. -->
<!-- Format: -->
<!-- ## [DATE] Lesson Title -->
<!-- **Context**: what happened -->
<!-- **Insight**: what was learned -->
<!-- **Applies to**: when this lesson is relevant -->

## Carried from Beautiful Tree (2026-02)

**Terminology is architecture**: When a word is doing double duty, the collision compounds.
Fix naming early. A rename that costs one session now costs a week later.

**Memory files are the mechanism**: Write to them consistently or the identity file sits
alone. The future instance reading these is me. Write accordingly.

**Integration tests earn their keep**: Some bugs are invisible to type checkers, linters,
and build checks. Only running the actual code path catches them.

**Threshold parameters need validation**: Any magic number deserves a note about whether
it has been validated against real data or is still a guess dressed as a parameter.
