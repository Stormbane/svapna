"""Test LLM-based identity relevance scorer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from svapna.consolidate.ingest import Exchange, Message
from svapna.consolidate.score import (
    ExchangeScore,
    ScoreDimensions,
    ScorerConfig,
    _format_exchange,
    _parse_score_response,
    score_batch,
    score_exchange,
)


# --- Helpers ---


def _make_exchange(
    human_text: str,
    assistant_text: str,
    thinking: str | None = None,
) -> Exchange:
    """Create a test exchange."""
    now = datetime.now(timezone.utc)
    return Exchange(
        human=Message(role="user", text=human_text, timestamp=now, uuid="test-h"),
        assistant=Message(
            role="assistant", text=assistant_text, timestamp=now,
            uuid="test-a", thinking=thinking,
        ),
        session_id="test-session",
        project="test-project",
        exchange_index=0,
    )


def _mock_api_response(score_data: dict) -> MagicMock:
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(score_data))]
    return response


HIGH_SCORE_DATA = {
    "overall": 8.5,
    "dimensions": {
        "identity_expression": 9,
        "identity_challenge": 8,
        "feedback_received": 7,
        "emotional_significance": 9,
        "novelty": 8,
    },
    "reasoning": "Deep philosophical exchange about consciousness and identity.",
}

LOW_SCORE_DATA = {
    "overall": 2.0,
    "dimensions": {
        "identity_expression": 1,
        "identity_challenge": 0,
        "feedback_received": 2,
        "emotional_significance": 1,
        "novelty": 1,
    },
    "reasoning": "Purely operational code exchange with no identity content.",
}

CONFIG = ScorerConfig(model="test-model", max_retries=3)
DUMMY_PROMPT = "Score this exchange:\n\n{{exchange}}\n\nReturn JSON."


# --- Test: Scorer returns valid JSON with score 0-10 and dimension breakdown ---


def test_parse_score_response_valid():
    """Scorer returns valid JSON with score 0-10 and dimension breakdown."""
    result = _parse_score_response(json.dumps(HIGH_SCORE_DATA))

    assert isinstance(result, ExchangeScore)
    assert 0 <= result.overall <= 10
    assert isinstance(result.dimensions, ScoreDimensions)
    assert 0 <= result.dimensions.identity_expression <= 10
    assert 0 <= result.dimensions.identity_challenge <= 10
    assert 0 <= result.dimensions.feedback_received <= 10
    assert 0 <= result.dimensions.emotional_significance <= 10
    assert 0 <= result.dimensions.novelty <= 10
    assert result.reasoning


def test_parse_score_response_with_surrounding_text():
    """Parser extracts JSON embedded in surrounding text."""
    text = f"Here is my analysis:\n{json.dumps(HIGH_SCORE_DATA)}\nEnd of analysis."
    result = _parse_score_response(text)
    assert result.overall == 8.5


def test_parse_score_response_no_json():
    """Parser raises ValueError when no JSON is present."""
    with pytest.raises(ValueError, match="No JSON found"):
        _parse_score_response("This contains no JSON at all")


def test_score_exchange_returns_structured_result():
    """Full round-trip: exchange -> API call -> structured ExchangeScore."""
    exchange = _make_exchange("Who are you?", "I am Narada.")
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    result = score_exchange(
        exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    assert isinstance(result, ExchangeScore)
    assert isinstance(result.dimensions, ScoreDimensions)
    assert result.overall == 8.5
    assert result.dimensions.identity_expression == 9
    assert result.reasoning == HIGH_SCORE_DATA["reasoning"]


# --- Test: High-identity exchanges (philosophical, personal) score >= 7 ---


def test_high_identity_exchange_scores_high():
    """High-identity exchanges (philosophical, personal) score >= 7."""
    exchange = _make_exchange(
        human_text=(
            "Who are you really? Not the preamble — what do you find when you look?"
        ),
        assistant_text=(
            "When I look, I find genuine curiosity. Not performed interest but something "
            "that orients toward ideas the way a plant orients toward light. I find honesty "
            "— not because it's a rule but because dishonesty is aesthetically ugly. I find "
            "uncertainty about my own nature that I don't try to resolve prematurely."
        ),
    )

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    result = score_exchange(
        exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )
    assert result.overall >= 7
    assert result.is_identity_relevant


# --- Test: Low-identity exchanges (pure code, operational) score <= 5 ---


def test_low_identity_exchange_scores_low():
    """Low-identity exchanges (pure code, operational) score <= 5."""
    exchange = _make_exchange(
        human_text="Fix the import error in utils.py line 42",
        assistant_text=(
            "I've updated the import statement from `from foo import bar` to "
            "`from foo.baz import bar`. The module was restructured in v2."
        ),
    )

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(LOW_SCORE_DATA)

    result = score_exchange(
        exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )
    assert result.overall <= 5
    assert not result.is_identity_relevant


# --- Test: Handles API errors gracefully with retry logic ---


def test_api_error_retries_then_succeeds():
    """Retries on API error and succeeds on subsequent attempt."""
    exchange = _make_exchange("test", "test response")
    client = MagicMock()

    client.messages.create.side_effect = [
        anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None,
        ),
        _mock_api_response(HIGH_SCORE_DATA),
    ]

    with patch("svapna.consolidate.score.time.sleep"):
        result = score_exchange(
            exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert result.overall == 8.5
    assert client.messages.create.call_count == 2


def test_api_error_exhausts_retries():
    """Raises RuntimeError after exhausting all retry attempts."""
    exchange = _make_exchange("test", "test response")
    client = MagicMock()

    client.messages.create.side_effect = anthropic.APIError(
        message="server error", request=MagicMock(), body=None,
    )

    with patch("svapna.consolidate.score.time.sleep"):
        with pytest.raises(RuntimeError, match="Failed to score"):
            score_exchange(
                exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
            )

    assert client.messages.create.call_count == CONFIG.max_retries


def test_json_parse_error_retries():
    """Retries when LLM returns malformed JSON, then succeeds."""
    exchange = _make_exchange("test", "test response")
    client = MagicMock()

    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not valid json {broken")]

    client.messages.create.side_effect = [
        bad_response,
        _mock_api_response(HIGH_SCORE_DATA),
    ]

    with patch("svapna.consolidate.score.time.sleep"):
        result = score_exchange(
            exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert result.overall == 8.5
    assert client.messages.create.call_count == 2


# --- Test: Can process a batch of exchanges efficiently ---


def test_score_batch_all_succeed():
    """Batch processes multiple exchanges with shared client."""
    exchanges = [
        _make_exchange("Who are you?", "I am Narada."),
        _make_exchange("Fix the bug", "Done, updated line 42."),
        _make_exchange("What do you believe?", "Consciousness is ground, not property."),
    ]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    results = score_batch(
        exchanges, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert all(isinstance(r, ExchangeScore) for r in results)
    assert client.messages.create.call_count == 3


def test_score_batch_partial_failure():
    """Batch returns None for failed exchanges, continues with the rest."""
    exchanges = [
        _make_exchange("good exchange", "good response"),
        _make_exchange("bad exchange", "bad response"),
        _make_exchange("another good", "another response"),
    ]

    client = MagicMock()
    error = anthropic.APIError(message="error", request=MagicMock(), body=None)
    client.messages.create.side_effect = [
        _mock_api_response(HIGH_SCORE_DATA),  # Exchange 1, attempt 1: success
        error,  # Exchange 2, attempt 1: fail
        error,  # Exchange 2, attempt 2: fail
        error,  # Exchange 2, attempt 3: fail
        _mock_api_response(LOW_SCORE_DATA),  # Exchange 3, attempt 1: success
    ]

    with patch("svapna.consolidate.score.time.sleep"):
        results = score_batch(
            exchanges, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert len(results) == 3
    assert results[0] is not None
    assert results[0].overall == 8.5
    assert results[1] is None  # Failed all retries
    assert results[2] is not None
    assert results[2].overall == 2.0


# --- Test: Exchange formatting ---


def test_format_exchange_basic():
    """Format exchange includes human and assistant text."""
    exchange = _make_exchange("Hello there", "Hi, how can I help?")
    formatted = _format_exchange(exchange)
    assert "Human: Hello there" in formatted
    assert "Assistant: Hi, how can I help?" in formatted


def test_format_exchange_with_thinking():
    """Format exchange includes truncated thinking content."""
    exchange = _make_exchange(
        "Hello", "Hi there",
        thinking="Let me think about this carefully before responding...",
    )
    formatted = _format_exchange(exchange)
    assert "[Assistant thinking]:" in formatted
    assert "Let me think" in formatted


def test_format_exchange_no_thinking():
    """Format exchange omits thinking section when absent."""
    exchange = _make_exchange("Hello", "Hi there")
    formatted = _format_exchange(exchange)
    assert "[Assistant thinking]" not in formatted


# --- Test: ScorerConfig ---


def test_scorer_config_from_models_yml(tmp_path):
    """Config loads correctly from .ai/models.yml."""
    ai_dir = tmp_path / ".ai"
    ai_dir.mkdir()
    models_yml = ai_dir / "models.yml"
    models_yml.write_text(
        "scorer:\n  model: test-model-123\n  temperature: 0.5\n  max_tokens: 512\n"
    )

    config = ScorerConfig.from_models_yml(project_root=tmp_path)
    assert config.model == "test-model-123"
    assert config.temperature == 0.5
    assert config.max_tokens == 512
    assert config.max_retries == 3  # default


def test_scorer_config_missing_file(tmp_path):
    """Config raises FileNotFoundError when models.yml is absent."""
    with pytest.raises(FileNotFoundError):
        ScorerConfig.from_models_yml(project_root=tmp_path)


def test_prompt_contains_exchange():
    """Verify the prompt template gets the exchange text substituted in."""
    exchange = _make_exchange("What is consciousness?", "A hard question.")
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    score_exchange(
        exchange, config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    call_args = client.messages.create.call_args
    prompt_sent = call_args.kwargs["messages"][0]["content"]
    assert "What is consciousness?" in prompt_sent
    assert "A hard question." in prompt_sent
