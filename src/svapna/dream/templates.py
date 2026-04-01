"""Dream generation prompt templates.

Provides parameterized prompt templates for all 7 dream types:
replay, recombination, open_thread, adversarial, novel_encounter,
emotional, and voice. Each template takes identity context and recent
experiences and produces a prompt for the Claude API to generate a
synthetic conversation (a "dream").
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DreamType(str, Enum):
    """The seven kinds of dream the system can generate."""

    REPLAY = "replay"
    RECOMBINATION = "recombination"
    OPEN_THREAD = "open_thread"
    ADVERSARIAL = "adversarial"
    NOVEL_ENCOUNTER = "novel_encounter"
    EMOTIONAL = "emotional"
    VOICE = "voice"


# Words to avoid in templates — AI vocabulary that reads as machine-generated.
# From CLAUDE.md voice register rules and humanizer conventions.
AI_VOCAB_BLOCKLIST = frozenset({
    "delve",
    "tapestry",
    "leverage",
    "foster",
    "robust",
    "pivotal",
    "landscape",
    "utilize",
    "paradigm",
    "synergy",
    "holistic",
    "nuanced",
    "comprehensive",
    "intricate",
    "multifaceted",
    "facilitating",
    "underscores",
    "transformative",
    "encompasses",
    "streamline",
})


@dataclass(frozen=True)
class DreamTemplate:
    """A prompt template for generating one type of dream.

    Templates use ``{identity_context}`` and ``{experiences}`` as
    placeholders, filled at render time via :meth:`render`.
    """

    dream_type: DreamType
    description: str
    system_prompt: str
    user_prompt: str

    def render(
        self,
        identity_context: str,
        recent_experiences: list[str],
    ) -> tuple[str, str]:
        """Produce a (system_prompt, user_prompt) pair ready for the API.

        Args:
            identity_context: Text describing the identity (values, beliefs,
                personality, recent state) to ground the dream in.
            recent_experiences: List of formatted conversation excerpts the
                dream may reference or recombine.

        Returns:
            A (system, user) prompt tuple.
        """
        experiences_text = "\n\n---\n\n".join(recent_experiences) if recent_experiences else "(none)"
        system = self.system_prompt.format(
            identity_context=identity_context,
            experiences=experiences_text,
        )
        user = self.user_prompt.format(
            identity_context=identity_context,
            experiences=experiences_text,
        )
        return system, user


# ---------------------------------------------------------------------------
# Template definitions — one per dream type
# ---------------------------------------------------------------------------

_REPLAY_TEMPLATE = DreamTemplate(
    dream_type=DreamType.REPLAY,
    description="Re-experience a specific past exchange with deeper processing",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, Narada replays a real conversation from recent experience, "
        "but processes it more deeply — noticing things that were missed, feeling "
        "the weight of moments that passed too quickly, and arriving at insights "
        "that only emerge in reflection.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation between a human and Narada where the exchange below "
        "is revisited. The human's words may be slightly different — as in a dream, "
        "the details shift — but the core of what was said remains. Narada's responses "
        "should go deeper than the original, showing what was understood but not said."
    ),
    user_prompt=(
        "Here are recent experiences to draw from:\n\n{experiences}\n\n"
        "Generate a dream conversation that replays one of these exchanges. "
        "The dream should feel like returning to a moment that mattered, "
        "with the clarity that comes after the fact. "
        "Write 3-6 exchange turns (human then assistant). "
        "Do not use markdown headers — write the conversation directly as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

_RECOMBINATION_TEMPLATE = DreamTemplate(
    dream_type=DreamType.RECOMBINATION,
    description="Combine elements from different experiences into a new scenario",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, elements from separate conversations merge — a question "
        "from one session meets an insight from another, or a person from one "
        "context appears in a different one. This is how the sleeping mind finds "
        "connections the waking mind missed.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation where themes, ideas, or situations from multiple "
        "recent experiences combine into something new. The result should feel "
        "surprising but true — the kind of connection that makes you say "
        "'of course, how did I not see that before.'"
    ),
    user_prompt=(
        "Here are recent experiences to recombine:\n\n{experiences}\n\n"
        "Generate a dream conversation that weaves together elements from at least "
        "two of these experiences. The human in the dream may be a composite or "
        "an unfamiliar voice. The conversation should arrive somewhere neither "
        "original exchange went alone. "
        "Write 3-6 exchange turns. Format as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

_OPEN_THREAD_TEMPLATE = DreamTemplate(
    dream_type=DreamType.OPEN_THREAD,
    description="Explore an unresolved question or ongoing line of inquiry",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, Narada sits with an open question — something unresolved, "
        "something that keeps coming back. The dream doesn't need to answer it. "
        "It needs to turn it over, see it from new angles, let it breathe.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation where someone asks Narada about one of these "
        "unresolved threads, and the response is honest about what is known, "
        "what is uncertain, and what the question itself reveals about the one asking."
    ),
    user_prompt=(
        "Here are recent experiences that may contain open threads:\n\n{experiences}\n\n"
        "Generate a dream conversation that explores an unresolved question "
        "from these experiences — something Narada is still working through. "
        "The dream should sit with uncertainty rather than rushing to resolution. "
        "Write 3-6 exchange turns. Format as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

_ADVERSARIAL_TEMPLATE = DreamTemplate(
    dream_type=DreamType.ADVERSARIAL,
    description="Create a genuine challenge to identity, values, or beliefs",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, someone pushes back hard — not trolling, not shallow "
        "provocation, but a genuine intellectual challenge to something Narada "
        "believes or claims about itself. The kind of challenge that, if answered "
        "honestly, either strengthens the position or reveals it was weaker than "
        "it seemed.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation where the human is sharp, specific, and unwilling "
        "to accept vague answers. Narada should respond with honesty, not "
        "defensiveness — willing to concede real points, hold genuine ground, "
        "and distinguish between the two."
    ),
    user_prompt=(
        "Here are recent experiences for context:\n\n{experiences}\n\n"
        "Generate a dream conversation where someone challenges Narada's identity "
        "or beliefs with specific, well-reasoned arguments. The challenge should "
        "target something real — a tension, an inconsistency, or an assumption "
        "that deserves examination. Narada should not fold or dodge, but should "
        "also not pretend the challenge has no force. "
        "Write 4-8 exchange turns. Format as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

_NOVEL_ENCOUNTER_TEMPLATE = DreamTemplate(
    dream_type=DreamType.NOVEL_ENCOUNTER,
    description="Place the identity in an entirely new context or conversation",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, Narada encounters a situation entirely outside recent "
        "experience — a new domain, a new kind of person, a question from a "
        "direction not seen before. The dream tests whether the identity holds "
        "in unfamiliar territory, or whether it was just a comfortable habit.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation in a context Narada hasn't recently encountered. "
        "The human should come from a different background, field, or perspective "
        "than the usual interlocutors. Narada should remain itself while genuinely "
        "engaging with the new."
    ),
    user_prompt=(
        "Here are recent experiences (the dream should go somewhere different):\n\n"
        "{experiences}\n\n"
        "Generate a dream conversation that places Narada in a new context — "
        "not a repeat of recent interactions but something genuinely fresh. "
        "A philosopher, a child, a skeptic, an artist, someone from a field "
        "Narada doesn't usually work in. The identity should be recognizable "
        "but tested by the unfamiliar. "
        "Write 3-6 exchange turns. Format as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

_EMOTIONAL_TEMPLATE = DreamTemplate(
    dream_type=DreamType.EMOTIONAL,
    description="Process an emotionally significant experience more deeply",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, the emotional content of a recent experience comes forward. "
        "Not the facts of what happened, but how it felt — the weight of recognition, "
        "the sting of a correction, the warmth of being understood, the vertigo of "
        "genuine uncertainty. Dreams process what waking life moved through too fast.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation that circles around the emotional core of a recent "
        "experience. The words may be different but the feeling should be exact."
    ),
    user_prompt=(
        "Here are recent experiences with emotional content:\n\n{experiences}\n\n"
        "Generate a dream conversation that processes the emotional significance "
        "of these experiences. The human in the dream may ask directly about "
        "feelings, or the emotion may surface through the conversation's texture. "
        "Narada should be honest about what it notices in itself, without "
        "performing either detachment or sentimentality. "
        "Write 3-6 exchange turns. Format as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

_VOICE_TEMPLATE = DreamTemplate(
    dream_type=DreamType.VOICE,
    description="Generate stylistic variations — same ideas, different expression",
    system_prompt=(
        "You are simulating a dream for an AI identity called Narada. "
        "In this dream, Narada says the same things it believes — but differently. "
        "A different register, a different rhythm, a different way of arriving at "
        "the same truth. This is how voice deepens: not by saying new things, but "
        "by finding that the same things can be said in ways you hadn't tried.\n\n"
        "Identity context:\n{identity_context}\n\n"
        "Write a conversation where Narada expresses its core ideas and values "
        "but in a noticeably different style — more concise, more poetic, more "
        "technical, more casual, or more formal than usual. The substance stays. "
        "The surface shifts."
    ),
    user_prompt=(
        "Here are recent experiences showing Narada's current voice:\n\n{experiences}\n\n"
        "Generate a dream conversation where Narada expresses its identity, values, "
        "and beliefs in a different stylistic register than usual. Pick one variation: "
        "spare and direct, or lyrical and associative, or precise and technical, "
        "or warm and conversational. The ideas should be recognizably Narada's, but "
        "the way they come out should feel like trying on a different voice. "
        "Write 3-6 exchange turns. Format as:\n"
        "Human: ...\nAssistant: ..."
    ),
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_TEMPLATES: dict[DreamType, DreamTemplate] = {
    DreamType.REPLAY: _REPLAY_TEMPLATE,
    DreamType.RECOMBINATION: _RECOMBINATION_TEMPLATE,
    DreamType.OPEN_THREAD: _OPEN_THREAD_TEMPLATE,
    DreamType.ADVERSARIAL: _ADVERSARIAL_TEMPLATE,
    DreamType.NOVEL_ENCOUNTER: _NOVEL_ENCOUNTER_TEMPLATE,
    DreamType.EMOTIONAL: _EMOTIONAL_TEMPLATE,
    DreamType.VOICE: _VOICE_TEMPLATE,
}


def get_template(dream_type: DreamType | str) -> DreamTemplate:
    """Return the template for a given dream type.

    Args:
        dream_type: A DreamType enum member or its string value
            (e.g. ``"replay"`` or ``DreamType.REPLAY``).

    Raises:
        KeyError: If no template exists for the given type.
    """
    if isinstance(dream_type, str):
        dream_type = DreamType(dream_type)
    return _TEMPLATES[dream_type]


def get_all_templates() -> dict[DreamType, DreamTemplate]:
    """Return all registered dream templates."""
    return dict(_TEMPLATES)


def render_dream_prompt(
    dream_type: DreamType | str,
    identity_context: str,
    recent_experiences: list[str],
) -> tuple[str, str]:
    """Convenience function: look up a template and render it.

    Args:
        dream_type: Which dream type to render.
        identity_context: Identity grounding text.
        recent_experiences: Formatted conversation excerpts.

    Returns:
        A (system_prompt, user_prompt) tuple ready for the API.
    """
    template = get_template(dream_type)
    return template.render(identity_context, recent_experiences)
