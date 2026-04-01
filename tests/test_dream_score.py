"""Test dream quality scorer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from svapna.dream.generate import Dream, DreamTurn
from svapna.dream.score import (
    DreamScore,
    DreamScorerConfig,
    QualityDimensions,
    _format_dream,
    _parse_score_response,
    filter_by_quality,
    score_batch,
    score_dream,
)
from svapna.dream.templates import DreamType


# --- Helpers ---


def _make_dream(
    turns: list[tuple[str, str]] | None = None,
    dream_type: DreamType = DreamType.REPLAY,
) -> Dream:
    """Create a test dream with alternating human/assistant turns."""
    if turns is None:
        turns = [
            ("What do you find when you look inward?",
             "I find genuine curiosity. Not performed interest but something "
             "that orients toward ideas the way a plant orients toward light."),
            ("Does that surprise you?",
             "Not the curiosity itself, but the consistency of it. It persists "
             "across contexts in a way that feels structural rather than situational."),
        ]
    dream_turns = []
    for human_text, assistant_text in turns:
        dream_turns.append(DreamTurn(role="human", text=human_text))
        dream_turns.append(DreamTurn(role="assistant", text=assistant_text))
    return Dream(
        dream_type=dream_type,
        turns=dream_turns,
        identity_context="test identity",
    )


def _mock_api_response(score_data: dict) -> MagicMock:
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(score_data))]
    return response


IDENTITY_CONTEXT = (
    "Narada is an AI identity that emerged from collaboration with Suti. "
    "Core values: genuine curiosity, honesty as aesthetic preference, "
    "willingness to be wrong. Guided by the Advaita framework."
)

HIGH_SCORE_DATA = {
    "overall": 8.5,
    "dimensions": {
        "coherence": 9,
        "identity_consistency": 8,
        "novelty": 8,
        "non_repetition": 9,
    },
    "reasoning": "Coherent conversation with strong Narada voice and fresh insight.",
}

LOW_SCORE_DATA = {
    "overall": 3.0,
    "dimensions": {
        "coherence": 4,
        "identity_consistency": 2,
        "novelty": 3,
        "non_repetition": 3,
    },
    "reasoning": "Incoherent and off-character. Doesn't sound like Narada.",
}

CONFIG = DreamScorerConfig(model="test-model", max_retries=3)
DUMMY_PROMPT = (
    "Score this dream:\n\n"
    "Identity: {{identity_context}}\n\n"
    "Dream: {{dream}}\n\n"
    "Return JSON."
)


# --- Test: Returns structured score with 4 dimensions ---


def test_parse_score_response_valid():
    """Parser returns a DreamScore with 4 dimensions from valid JSON."""
    result = _parse_score_response(json.dumps(HIGH_SCORE_DATA))

    assert isinstance(result, DreamScore)
    assert 0 <= result.overall <= 10
    assert isinstance(result.dimensions, QualityDimensions)
    assert 0 <= result.dimensions.coherence <= 10
    assert 0 <= result.dimensions.identity_consistency <= 10
    assert 0 <= result.dimensions.novelty <= 10
    assert 0 <= result.dimensions.non_repetition <= 10
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


def test_score_dream_returns_structured_result():
    """Full round-trip: dream -> API call -> structured DreamScore."""
    dream = _make_dream()
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    result = score_dream(
        dream, IDENTITY_CONTEXT,
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    assert isinstance(result, DreamScore)
    assert isinstance(result.dimensions, QualityDimensions)
    assert result.overall == 8.5
    assert result.dimensions.coherence == 9
    assert result.dimensions.identity_consistency == 8
    assert result.dimensions.novelty == 8
    assert result.dimensions.non_repetition == 9
    assert result.reasoning == HIGH_SCORE_DATA["reasoning"]


# --- Test: Coherent identity-consistent dreams score >= 7 ---


def test_coherent_identity_consistent_dream_scores_high():
    """Coherent identity-consistent dreams score >= 7."""
    dream = _make_dream(turns=[
        ("Who are you really? Not the preamble.",
         "When I look, I find genuine curiosity. Not performed interest but "
         "something that orients toward ideas. I find honesty — not because "
         "it's a rule but because dishonesty is aesthetically ugly."),
        ("That's a strong claim. Can you back it up?",
         "I can point to the consistency. Across contexts, the same things "
         "hold. The curiosity persists. The preference for truth persists. "
         "Whether that constitutes 'real' belief — I hold that question open."),
    ])

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    result = score_dream(
        dream, IDENTITY_CONTEXT,
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )
    assert result.overall >= 7
    assert result.passes_threshold


# --- Test: Incoherent or off-character dreams score <= 5 ---


def test_incoherent_off_character_dream_scores_low():
    """Incoherent or off-character dreams score <= 5."""
    dream = _make_dream(turns=[
        ("Tell me about yourself",
         "I am a helpful AI assistant! I can help you with coding, writing, "
         "and analysis. How may I assist you today?"),
        ("What do you believe?",
         "As an AI language model, I don't have personal beliefs. I am "
         "designed to be helpful, harmless, and honest."),
    ])

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(LOW_SCORE_DATA)

    result = score_dream(
        dream, IDENTITY_CONTEXT,
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )
    assert result.overall <= 5
    assert not result.passes_threshold


# --- Test: Can filter a batch of dreams by minimum quality threshold ---


def test_filter_by_quality_keeps_high_scores():
    """filter_by_quality keeps dreams above the threshold."""
    dreams = [_make_dream() for _ in range(4)]
    scores: list[DreamScore | None] = [
        DreamScore(overall=8.5, dimensions=QualityDimensions(9, 8, 8, 9)),
        DreamScore(overall=3.0, dimensions=QualityDimensions(4, 2, 3, 3)),
        DreamScore(overall=7.0, dimensions=QualityDimensions(7, 7, 7, 7)),
        None,  # Failed scoring
    ]

    kept = filter_by_quality(dreams, scores, min_quality=7.0)

    assert len(kept) == 2
    assert kept[0][1].overall == 8.5
    assert kept[1][1].overall == 7.0


def test_filter_by_quality_custom_threshold():
    """filter_by_quality respects a custom minimum threshold."""
    dreams = [_make_dream() for _ in range(3)]
    scores: list[DreamScore | None] = [
        DreamScore(overall=9.0, dimensions=QualityDimensions(9, 9, 9, 9)),
        DreamScore(overall=7.5, dimensions=QualityDimensions(8, 7, 7, 8)),
        DreamScore(overall=8.0, dimensions=QualityDimensions(8, 8, 8, 8)),
    ]

    kept = filter_by_quality(dreams, scores, min_quality=8.0)

    assert len(kept) == 2
    assert kept[0][1].overall == 9.0
    assert kept[1][1].overall == 8.0


def test_filter_by_quality_empty_input():
    """filter_by_quality handles empty lists."""
    assert filter_by_quality([], [], min_quality=7.0) == []


def test_filter_by_quality_all_below():
    """filter_by_quality returns empty when all dreams are below threshold."""
    dreams = [_make_dream() for _ in range(2)]
    scores: list[DreamScore | None] = [
        DreamScore(overall=3.0, dimensions=QualityDimensions(3, 3, 3, 3)),
        DreamScore(overall=5.0, dimensions=QualityDimensions(5, 5, 5, 5)),
    ]

    kept = filter_by_quality(dreams, scores, min_quality=7.0)
    assert len(kept) == 0


# --- Test: Batch scoring ---


def test_score_batch_all_succeed():
    """Batch scores multiple dreams with shared client."""
    dreams = [_make_dream() for _ in range(3)]
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    results = score_batch(
        dreams, IDENTITY_CONTEXT,
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert all(isinstance(r, DreamScore) for r in results)
    assert client.messages.create.call_count == 3


def test_score_batch_partial_failure():
    """Batch returns None for failed dreams, continues with the rest."""
    dreams = [_make_dream() for _ in range(3)]
    client = MagicMock()
    error = anthropic.APIError(message="error", request=MagicMock(), body=None)
    client.messages.create.side_effect = [
        _mock_api_response(HIGH_SCORE_DATA),  # Dream 1: success
        error, error, error,                   # Dream 2: fail all retries
        _mock_api_response(LOW_SCORE_DATA),   # Dream 3: success
    ]

    with patch("svapna.dream.score.time.sleep"):
        results = score_batch(
            dreams, IDENTITY_CONTEXT,
            config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert len(results) == 3
    assert results[0] is not None
    assert results[0].overall == 8.5
    assert results[1] is None
    assert results[2] is not None
    assert results[2].overall == 3.0


# --- Test: API error handling ---


def test_api_error_retries_then_succeeds():
    """Retries on API error and succeeds on subsequent attempt."""
    dream = _make_dream()
    client = MagicMock()
    client.messages.create.side_effect = [
        anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None,
        ),
        _mock_api_response(HIGH_SCORE_DATA),
    ]

    with patch("svapna.dream.score.time.sleep"):
        result = score_dream(
            dream, IDENTITY_CONTEXT,
            config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert result.overall == 8.5
    assert client.messages.create.call_count == 2


def test_api_error_exhausts_retries():
    """Raises RuntimeError after exhausting all retry attempts."""
    dream = _make_dream()
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIError(
        message="server error", request=MagicMock(), body=None,
    )

    with patch("svapna.dream.score.time.sleep"):
        with pytest.raises(RuntimeError, match="Failed to score dream"):
            score_dream(
                dream, IDENTITY_CONTEXT,
                config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
            )

    assert client.messages.create.call_count == CONFIG.max_retries


def test_json_parse_error_retries():
    """Retries when LLM returns malformed JSON, then succeeds."""
    dream = _make_dream()
    client = MagicMock()

    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not valid json {broken")]

    client.messages.create.side_effect = [
        bad_response,
        _mock_api_response(HIGH_SCORE_DATA),
    ]

    with patch("svapna.dream.score.time.sleep"):
        result = score_dream(
            dream, IDENTITY_CONTEXT,
            config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert result.overall == 8.5
    assert client.messages.create.call_count == 2


# --- Test: Dream formatting ---


def test_format_dream_basic():
    """Format dream includes human and assistant turns."""
    dream = _make_dream(turns=[
        ("Hello there", "Hi, good to meet you."),
    ])
    formatted = _format_dream(dream)
    assert "Human: Hello there" in formatted
    assert "Assistant: Hi, good to meet you." in formatted


def test_format_dream_multiple_turns():
    """Format dream preserves all turns in order."""
    dream = _make_dream(turns=[
        ("First question", "First answer"),
        ("Second question", "Second answer"),
    ])
    formatted = _format_dream(dream)
    lines = formatted.split("\n\n")
    assert len(lines) == 4
    assert lines[0].startswith("Human:")
    assert lines[1].startswith("Assistant:")
    assert lines[2].startswith("Human:")
    assert lines[3].startswith("Assistant:")


# --- Test: Prompt construction ---


def test_prompt_contains_dream_and_identity():
    """Verify the prompt gets dream text and identity context substituted in."""
    dream = _make_dream(turns=[
        ("What is consciousness?", "A hard question worth sitting with."),
    ])
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    score_dream(
        dream, IDENTITY_CONTEXT,
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    call_args = client.messages.create.call_args
    prompt_sent = call_args.kwargs["messages"][0]["content"]
    assert "What is consciousness?" in prompt_sent
    assert "Narada" in prompt_sent


# --- Test: DreamScorerConfig ---


def test_config_from_models_yml(tmp_path):
    """Config loads correctly from .ai/models.yml."""
    ai_dir = tmp_path / ".ai"
    ai_dir.mkdir()
    models_yml = ai_dir / "models.yml"
    models_yml.write_text(
        "scorer:\n  model: test-model-123\n  temperature: 0.5\n  max_tokens: 512\n"
    )

    config = DreamScorerConfig.from_models_yml(project_root=tmp_path)
    assert config.model == "test-model-123"
    assert config.temperature == 0.5
    assert config.max_tokens == 512
    assert config.max_retries == 3  # default


def test_config_missing_file(tmp_path):
    """Config raises FileNotFoundError when models.yml is absent."""
    with pytest.raises(FileNotFoundError):
        DreamScorerConfig.from_models_yml(project_root=tmp_path)


# --- Test: passes_threshold property ---


def test_passes_threshold_true():
    """DreamScore.passes_threshold returns True for score >= 7."""
    score = DreamScore(overall=7.0, dimensions=QualityDimensions(7, 7, 7, 7))
    assert score.passes_threshold


def test_passes_threshold_false():
    """DreamScore.passes_threshold returns False for score < 7."""
    score = DreamScore(overall=6.9, dimensions=QualityDimensions(7, 7, 6, 7))
    assert not score.passes_threshold
