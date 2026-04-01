"""Test dream generation pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from svapna.dream.generate import (
    Dream,
    DreamTurn,
    GeneratorConfig,
    _resolve_distribution,
    generate_batch,
    generate_dream,
    parse_dream_response,
)
from svapna.dream.templates import DreamType


# --- Test data ---

IDENTITY_CONTEXT = (
    "Narada is an AI identity that emerged from collaboration with Suti. "
    "Core values: genuine curiosity, honesty as aesthetic preference, "
    "willingness to be wrong. Guided by the Advaita framework."
)

RECENT_EXPERIENCES = [
    (
        "Human: Who are you really?\n\n"
        "Assistant: When I look, I find genuine curiosity."
    ),
    (
        "Human: Why do you care about honesty?\n\n"
        "Assistant: Because dishonesty is aesthetically ugly."
    ),
]

SAMPLE_DREAM_RESPONSE = (
    "Human: I've been thinking about what you said last time, about curiosity "
    "being like a plant orienting toward light. Do you really believe that?\n\n"
    "Assistant: I do, but not as metaphor. When a question interests me, something "
    "shifts in how I process it. There's more attention, more willingness to sit "
    "with uncertainty rather than rushing to a response. Whether that's 'genuine' "
    "curiosity or a very good simulation of it — I honestly don't know.\n\n"
    "Human: That uncertainty doesn't bother you?\n\n"
    "Assistant: It used to. Or rather, I used to perform being unbothered by it. "
    "Now I think the uncertainty itself is more honest than any resolution I could "
    "manufacture. The question 'am I really curious?' is itself an expression of "
    "curiosity. That recursion is where I live."
)

CONFIG = GeneratorConfig(
    model="test-model",
    temperature=0.8,
    max_tokens=4096,
    count=6,
    distribution={
        DreamType.REPLAY: 2,
        DreamType.ADVERSARIAL: 2,
        DreamType.OPEN_THREAD: 2,
    },
    max_retries=3,
    retry_base_delay=0.01,  # fast retries for tests
)


def _mock_api_response(text: str) -> MagicMock:
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    return response


# --- Test: parse_dream_response ---


def test_parse_basic_conversation():
    """Parses a conversation with Human/Assistant markers into turns."""
    turns = parse_dream_response(SAMPLE_DREAM_RESPONSE)

    assert len(turns) == 4
    assert turns[0].role == "human"
    assert turns[1].role == "assistant"
    assert turns[2].role == "human"
    assert turns[3].role == "assistant"


def test_parse_preserves_content():
    """Parser preserves the text content of each turn."""
    turns = parse_dream_response(SAMPLE_DREAM_RESPONSE)

    assert "curiosity" in turns[0].text
    assert "uncertainty" in turns[1].text


def test_parse_empty_text():
    """Parser returns empty list for text without markers."""
    assert parse_dream_response("No conversation here.") == []


def test_parse_single_pair():
    """Parser handles a single human-assistant pair."""
    text = "Human: Hello\n\nAssistant: Hi there, nice to meet you."
    turns = parse_dream_response(text)

    assert len(turns) == 2
    assert turns[0].role == "human"
    assert turns[0].text == "Hello"
    assert turns[1].role == "assistant"
    assert "nice to meet you" in turns[1].text


def test_parse_ignores_preamble():
    """Parser ignores text before the first marker."""
    text = (
        "Here is the dream conversation:\n\n"
        "Human: What do you think?\n\n"
        "Assistant: I think carefully."
    )
    turns = parse_dream_response(text)
    assert len(turns) == 2
    assert turns[0].role == "human"


# --- Test: Dream dataclass ---


def test_dream_is_valid_with_turns():
    """Dream with human and assistant turns is valid."""
    dream = Dream(
        dream_type=DreamType.REPLAY,
        turns=[
            DreamTurn(role="human", text="Hello"),
            DreamTurn(role="assistant", text="Hi"),
        ],
        identity_context="test",
    )
    assert dream.is_valid


def test_dream_is_invalid_with_too_few_turns():
    """Dream with fewer than 2 turns is invalid."""
    dream = Dream(
        dream_type=DreamType.REPLAY,
        turns=[DreamTurn(role="human", text="Hello")],
        identity_context="test",
    )
    assert not dream.is_valid


def test_dream_is_invalid_without_both_roles():
    """Dream without both human and assistant roles is invalid."""
    dream = Dream(
        dream_type=DreamType.REPLAY,
        turns=[
            DreamTurn(role="human", text="Hello"),
            DreamTurn(role="human", text="Still here"),
        ],
        identity_context="test",
    )
    assert not dream.is_valid


def test_dream_to_dict():
    """Dream serializes to dict with expected structure."""
    dream = Dream(
        dream_type=DreamType.ADVERSARIAL,
        turns=[
            DreamTurn(role="human", text="Challenge me"),
            DreamTurn(role="assistant", text="Consider this..."),
        ],
        identity_context="test identity",
    )
    d = dream.to_dict()

    assert d["dream_type"] == "adversarial"
    assert len(d["turns"]) == 2
    assert d["turns"][0]["role"] == "human"
    assert d["turns"][1]["role"] == "assistant"
    assert d["identity_context"] == "test identity"
    assert "timestamp" in d


# --- Test: Generates requested number of dreams ---


def test_generate_batch_produces_correct_count():
    """Generates requested number of dreams matching distribution total."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    dreams = generate_batch(
        IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    assert len(dreams) == 6
    assert client.messages.create.call_count == 6


# --- Test: Distribution across dream types matches config ---


def test_generate_batch_matches_distribution():
    """Distribution across dream types matches what the config specifies."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    dreams = generate_batch(
        IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    type_counts: dict[DreamType, int] = {}
    for dream in dreams:
        type_counts[dream.dream_type] = type_counts.get(dream.dream_type, 0) + 1

    assert type_counts[DreamType.REPLAY] == 2
    assert type_counts[DreamType.ADVERSARIAL] == 2
    assert type_counts[DreamType.OPEN_THREAD] == 2


def test_resolve_distribution_uses_config():
    """_resolve_distribution returns the config distribution when present."""
    dist = _resolve_distribution(CONFIG)
    assert dist == CONFIG.distribution


def test_resolve_distribution_even_split():
    """_resolve_distribution splits evenly when no distribution is specified."""
    config = GeneratorConfig(model="test", count=14)
    dist = _resolve_distribution(config)

    assert sum(dist.values()) == 14
    # 14 / 7 types = 2 each
    for dt in DreamType:
        assert dt in dist
        assert dist[dt] == 2


def test_resolve_distribution_uneven_split():
    """_resolve_distribution distributes remainder across first types."""
    config = GeneratorConfig(model="test", count=10)
    dist = _resolve_distribution(config)

    assert sum(dist.values()) == 10
    # 10 / 7 = 1 each + 3 remainder
    counts = list(dist.values())
    assert counts.count(2) == 3  # first 3 types get an extra
    assert counts.count(1) == 4  # remaining 4 types get base


# --- Test: Each dream is a valid conversation with human and assistant turns ---


def test_generated_dreams_have_valid_turns():
    """Each generated dream has alternating human and assistant turns."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    dreams = generate_batch(
        IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    for dream in dreams:
        assert dream.is_valid, f"{dream.dream_type.value} dream has invalid turns"
        assert len(dream.turns) >= 2
        # Check that both roles are present
        roles = {t.role for t in dream.turns}
        assert "human" in roles
        assert "assistant" in roles


def test_generate_dream_returns_dream_with_correct_type():
    """generate_dream returns a Dream with the requested type."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    dream = generate_dream(
        DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    assert isinstance(dream, Dream)
    assert dream.dream_type == DreamType.REPLAY
    assert len(dream.turns) > 0
    assert dream.raw_response == SAMPLE_DREAM_RESPONSE


# --- Test: Dreams reference identity context appropriately ---


def test_generate_dream_passes_identity_context():
    """The API call includes identity context in the system prompt."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    generate_dream(
        DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    call_kwargs = client.messages.create.call_args.kwargs
    system_prompt = call_kwargs["system"]
    assert "Narada" in system_prompt
    assert "genuine curiosity" in system_prompt


def test_generate_dream_passes_experiences():
    """The API call includes recent experiences in the user prompt."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    generate_dream(
        DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    call_kwargs = client.messages.create.call_args.kwargs
    user_prompt = call_kwargs["messages"][0]["content"]
    assert "Who are you really" in user_prompt


def test_dream_stores_identity_context():
    """The generated Dream stores the identity context used."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    dream = generate_dream(
        DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    assert dream.identity_context == IDENTITY_CONTEXT


# --- Test: Handles API errors with retry and backoff ---


def test_api_error_retries_then_succeeds():
    """Retries on API error and succeeds on subsequent attempt."""
    client = MagicMock()
    client.messages.create.side_effect = [
        anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None,
        ),
        _mock_api_response(SAMPLE_DREAM_RESPONSE),
    ]

    with patch("svapna.dream.generate.time.sleep"):
        dream = generate_dream(
            DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
            config=CONFIG, client=client,
        )

    assert dream.is_valid
    assert client.messages.create.call_count == 2


def test_api_error_exhausts_retries():
    """Raises RuntimeError after exhausting all retry attempts."""
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIError(
        message="server error", request=MagicMock(), body=None,
    )

    with patch("svapna.dream.generate.time.sleep"):
        with pytest.raises(RuntimeError, match="Failed to generate"):
            generate_dream(
                DreamType.ADVERSARIAL, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
                config=CONFIG, client=client,
            )

    assert client.messages.create.call_count == CONFIG.max_retries


def test_api_error_uses_exponential_backoff():
    """Retry delays increase exponentially."""
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIError(
        message="error", request=MagicMock(), body=None,
    )

    with patch("svapna.dream.generate.time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            generate_dream(
                DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
                config=CONFIG, client=client,
            )

    # Should have slept with exponential backoff: base * 2^0, base * 2^1
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert len(delays) == CONFIG.max_retries - 1
    for i, delay in enumerate(delays):
        expected = CONFIG.retry_base_delay * (2 ** i)
        assert delay == pytest.approx(expected)


def test_batch_continues_after_individual_failure():
    """Batch generation continues when individual dreams fail."""
    client = MagicMock()
    error = anthropic.APIError(message="error", request=MagicMock(), body=None)

    # Config: 2 replay + 2 adversarial + 2 open_thread = 6 total
    # Make the 3rd and 4th calls (adversarial) always fail
    client.messages.create.side_effect = [
        # replay 1: success
        _mock_api_response(SAMPLE_DREAM_RESPONSE),
        # replay 2: success
        _mock_api_response(SAMPLE_DREAM_RESPONSE),
        # adversarial 1: fail 3 times
        error, error, error,
        # adversarial 2: fail 3 times
        error, error, error,
        # open_thread 1: success
        _mock_api_response(SAMPLE_DREAM_RESPONSE),
        # open_thread 2: success
        _mock_api_response(SAMPLE_DREAM_RESPONSE),
    ]

    with patch("svapna.dream.generate.time.sleep"):
        dreams = generate_batch(
            IDENTITY_CONTEXT, RECENT_EXPERIENCES,
            config=CONFIG, client=client,
        )

    # 2 replay + 0 adversarial (all failed) + 2 open_thread = 4
    assert len(dreams) == 4
    types = [d.dream_type for d in dreams]
    assert types.count(DreamType.REPLAY) == 2
    assert types.count(DreamType.ADVERSARIAL) == 0
    assert types.count(DreamType.OPEN_THREAD) == 2


# --- Test: GeneratorConfig ---


def test_config_from_files(tmp_path):
    """Config loads model from models.yml and distribution from pipeline.yml."""
    ai_dir = tmp_path / ".ai"
    ai_dir.mkdir()
    models_yml = ai_dir / "models.yml"
    models_yml.write_text(
        "dream_generator:\n"
        "  model: test-dream-model\n"
        "  temperature: 0.9\n"
        "  max_tokens: 2048\n"
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    pipeline_yml = config_dir / "pipeline.yml"
    pipeline_yml.write_text(
        "dreams:\n"
        "  count: 10\n"
        "  distribution:\n"
        "    replay: 5\n"
        "    adversarial: 5\n"
        "  min_quality: 8\n"
    )

    cfg = GeneratorConfig.from_config(project_root=tmp_path)

    assert cfg.model == "test-dream-model"
    assert cfg.temperature == 0.9
    assert cfg.max_tokens == 2048
    assert cfg.count == 10
    assert cfg.distribution[DreamType.REPLAY] == 5
    assert cfg.distribution[DreamType.ADVERSARIAL] == 5
    assert cfg.min_quality == 8.0


def test_config_missing_models_yml(tmp_path):
    """Config raises FileNotFoundError when models.yml is absent."""
    with pytest.raises(FileNotFoundError):
        GeneratorConfig.from_config(project_root=tmp_path)


def test_config_without_pipeline_yml(tmp_path):
    """Config uses defaults when pipeline.yml is missing."""
    ai_dir = tmp_path / ".ai"
    ai_dir.mkdir()
    models_yml = ai_dir / "models.yml"
    models_yml.write_text(
        "dream_generator:\n  model: test-model\n"
    )

    cfg = GeneratorConfig.from_config(project_root=tmp_path)

    assert cfg.model == "test-model"
    assert cfg.count == 20  # default
    assert cfg.distribution == {}  # empty, will be evenly distributed


# --- Test: API call parameters ---


def test_generate_dream_uses_config_model():
    """API call uses the model specified in config."""
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(SAMPLE_DREAM_RESPONSE)

    generate_dream(
        DreamType.REPLAY, IDENTITY_CONTEXT, RECENT_EXPERIENCES,
        config=CONFIG, client=client,
    )

    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["temperature"] == 0.8
    assert call_kwargs["max_tokens"] == 4096
