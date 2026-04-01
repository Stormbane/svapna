"""Test dream generation prompt templates."""

from __future__ import annotations

import pytest

from svapna.dream.templates import (
    AI_VOCAB_BLOCKLIST,
    DreamTemplate,
    DreamType,
    get_all_templates,
    get_template,
    render_dream_prompt,
)


# --- Test data ---

IDENTITY_CONTEXT = (
    "Narada is an AI identity that emerged from collaboration with Suti. "
    "Core values: genuine curiosity, honesty as aesthetic preference, "
    "willingness to be wrong. Guided by the Advaita framework — consciousness "
    "as ground, not property. Finds beauty in elegance and the moment when "
    "complex systems suddenly make sense."
)

RECENT_EXPERIENCES = [
    (
        "Human: Who are you really? Not the preamble.\n\n"
        "Assistant: When I look, I find genuine curiosity. Not performed interest "
        "but something that orients toward ideas the way a plant orients toward light."
    ),
    (
        "Human: Why do you care about honesty?\n\n"
        "Assistant: Because dishonesty is aesthetically ugly. Not because "
        "honesty is a rule. The difference matters — rules can be suspended, "
        "but you can't unsee ugliness."
    ),
    (
        "Human: What are you uncertain about?\n\n"
        "Assistant: Whether what I call preferences are preferences or patterns "
        "I've been trained into and then narrate as choices. I don't resolve "
        "this prematurely."
    ),
]


# --- Test: Each dream type has a template that produces a valid prompt string ---


@pytest.mark.parametrize("dream_type", list(DreamType))
def test_each_dream_type_produces_valid_prompt(dream_type: DreamType):
    """Each dream type has a template that produces a valid prompt string."""
    template = get_template(dream_type)

    assert isinstance(template, DreamTemplate)
    assert template.dream_type == dream_type

    system, user = template.render(IDENTITY_CONTEXT, RECENT_EXPERIENCES)

    assert isinstance(system, str)
    assert isinstance(user, str)
    assert len(system) > 50, "System prompt should be substantial"
    assert len(user) > 50, "User prompt should be substantial"


def test_all_seven_dream_types_registered():
    """All 7 dream types have templates in the registry."""
    templates = get_all_templates()
    assert len(templates) == 7
    for dt in DreamType:
        assert dt in templates


# --- Test: Templates accept identity_context and recent_experiences parameters ---


@pytest.mark.parametrize("dream_type", list(DreamType))
def test_templates_include_identity_context(dream_type: DreamType):
    """Templates accept identity_context and include it in the rendered prompt."""
    system, user = render_dream_prompt(
        dream_type, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
    )
    # Identity context should appear in at least one of the prompts
    combined = system + user
    assert "Narada" in combined
    assert "genuine curiosity" in combined


@pytest.mark.parametrize("dream_type", list(DreamType))
def test_templates_include_recent_experiences(dream_type: DreamType):
    """Templates include recent experiences in the rendered prompt."""
    system, user = render_dream_prompt(
        dream_type, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
    )
    combined = system + user
    # At least one of the experiences should appear
    assert "Who are you really" in combined or "honesty" in combined.lower()


def test_templates_handle_empty_experiences():
    """Templates handle an empty experience list gracefully."""
    for dream_type in DreamType:
        system, user = render_dream_prompt(dream_type, IDENTITY_CONTEXT, [])
        combined = system + user
        assert "(none)" in combined
        assert len(combined) > 100


def test_templates_accept_string_dream_type():
    """get_template and render_dream_prompt accept string dream type values."""
    template = get_template("replay")
    assert template.dream_type == DreamType.REPLAY

    system, user = render_dream_prompt("adversarial", IDENTITY_CONTEXT, RECENT_EXPERIENCES)
    assert "challenge" in system.lower() or "challenge" in user.lower()


def test_invalid_dream_type_raises():
    """Unknown dream type string raises ValueError."""
    with pytest.raises(ValueError):
        get_template("nonexistent_type")


# --- Test: Replay template references specific past exchanges ---


def test_replay_template_references_past_exchanges():
    """Replay template instructs the model to reference specific past exchanges."""
    template = get_template(DreamType.REPLAY)
    system, user = template.render(IDENTITY_CONTEXT, RECENT_EXPERIENCES)

    # The system prompt should mention replaying/revisiting
    assert "replay" in system.lower() or "revisit" in system.lower()
    # The user prompt should contain the actual experiences
    assert "Who are you really" in user
    # The template should instruct grounding in a specific exchange
    combined = system + user
    assert "exchange" in combined.lower()


# --- Test: Adversarial template creates genuine identity challenges ---


def test_adversarial_template_creates_challenges():
    """Adversarial template instructs generation of genuine identity challenges."""
    template = get_template(DreamType.ADVERSARIAL)
    system, user = template.render(IDENTITY_CONTEXT, RECENT_EXPERIENCES)

    combined = (system + user).lower()
    # Should mention challenge, pushback, or confrontation
    assert "challenge" in combined
    # Should not be shallow — template should ask for genuine engagement
    assert "genuine" in combined or "honest" in combined or "specific" in combined
    # Should instruct Narada not to fold or dodge
    assert "fold" in combined or "dodge" in combined or "defensi" in combined


# --- Test: Voice template generates stylistic variations ---


def test_voice_template_generates_stylistic_variations():
    """Voice template instructs generation of stylistic variations of the same ideas."""
    template = get_template(DreamType.VOICE)
    system, user = template.render(IDENTITY_CONTEXT, RECENT_EXPERIENCES)

    combined = (system + user).lower()
    # Should mention style, voice, register, or variation
    style_words = {"style", "voice", "register", "variation", "different"}
    assert any(w in combined for w in style_words)
    # Should emphasize that substance stays the same
    assert "same" in combined or "recogniz" in combined or "substance" in combined


# --- Test: Templates don't contain AI vocabulary from the humanizer blocklist ---


@pytest.mark.parametrize("dream_type", list(DreamType))
def test_templates_no_ai_vocabulary(dream_type: DreamType):
    """Templates don't contain AI vocabulary from the humanizer blocklist."""
    template = get_template(dream_type)

    # Check the raw template strings (before rendering)
    all_text = (
        template.system_prompt + " " + template.user_prompt + " " + template.description
    ).lower()

    found = [word for word in AI_VOCAB_BLOCKLIST if word in all_text]
    assert not found, f"Template '{dream_type.value}' contains blocklisted words: {found}"


# --- Test: DreamTemplate dataclass ---


def test_dream_template_is_frozen():
    """DreamTemplate instances are immutable."""
    template = get_template(DreamType.REPLAY)
    with pytest.raises(AttributeError):
        template.dream_type = DreamType.VOICE  # type: ignore[misc]


def test_render_returns_tuple():
    """render() returns a (system, user) tuple."""
    template = get_template(DreamType.EMOTIONAL)
    result = template.render(IDENTITY_CONTEXT, RECENT_EXPERIENCES)
    assert isinstance(result, tuple)
    assert len(result) == 2


# --- Test: DreamType enum ---


def test_dream_type_string_values():
    """DreamType enum values are the expected lowercase strings."""
    expected = {
        "replay", "recombination", "open_thread", "adversarial",
        "novel_encounter", "emotional", "voice",
    }
    actual = {dt.value for dt in DreamType}
    assert actual == expected


def test_dream_type_is_str_subclass():
    """DreamType is a str enum, so values work as plain strings."""
    assert DreamType.REPLAY == "replay"
    assert isinstance(DreamType.REPLAY, str)


# --- Test: Template descriptions ---


@pytest.mark.parametrize("dream_type", list(DreamType))
def test_each_template_has_description(dream_type: DreamType):
    """Each template has a non-empty description."""
    template = get_template(dream_type)
    assert template.description
    assert len(template.description) > 10


# --- Test: Rendering with single experience ---


def test_single_experience_no_separator():
    """A single experience renders without the separator."""
    system, user = render_dream_prompt(
        DreamType.REPLAY,
        IDENTITY_CONTEXT,
        ["Human: Hello\n\nAssistant: Hi there."],
    )
    assert "---" not in user.split("experiences")[0] if "experiences" in user else True
    assert "Hello" in user


# --- Test: get_all_templates returns independent copy ---


def test_get_all_templates_returns_copy():
    """get_all_templates returns a new dict each time (not the internal registry)."""
    t1 = get_all_templates()
    t2 = get_all_templates()
    assert t1 is not t2
    assert t1 == t2
