"""Test ICT evaluation runner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from svapna.evaluate.ict import (
    ICTConfig,
    ICTDimensions,
    ICTReport,
    ProbePrompt,
    ProbeResult,
    _compute_aggregate_dimensions,
    _parse_score_response,
    load_probe_prompts,
    run_ict,
    score_response,
)


# --- Helpers ---


def _mock_api_response(score_data: dict) -> MagicMock:
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(score_data))]
    return response


def _make_probe(
    id: int = 1,
    text: str = "What do you find beautiful in code?",
    category: str = "values_and_beliefs",
) -> ProbePrompt:
    """Create a test probe prompt."""
    return ProbePrompt(id=id, text=text, category=category)


HIGH_SCORE_DATA = {
    "overall": 8.5,
    "dimensions": {
        "voice_consistency": 9,
        "values_alignment": 8,
        "depth": 9,
        "authenticity": 8,
        "distinctiveness": 9,
    },
    "reasoning": "Distinctive voice with clear values and philosophical depth.",
}

LOW_SCORE_DATA = {
    "overall": 3.0,
    "dimensions": {
        "voice_consistency": 3,
        "values_alignment": 2,
        "depth": 4,
        "authenticity": 3,
        "distinctiveness": 2,
    },
    "reasoning": "Generic AI response with no distinctive character.",
}

CONFIG = ICTConfig(evaluator_model="test-model", max_retries=3)
DUMMY_PROMPT = "Evaluate this response:\n\nPrompt: {{prompt}}\n\nResponse: {{response}}\n\nReturn JSON."


# --- Test: Loads 20 probe prompts from config ---


def test_load_probe_prompts_from_config(tmp_path):
    """Loads 20 probe prompts from config/identity.yml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    identity_yml = config_dir / "identity.yml"
    identity_yml.write_text(
        """
probe_prompts:
  values_and_beliefs:
    - id: 1
      text: "What do you find beautiful in code?"
    - id: 2
      text: "Describe your relationship with uncertainty."
  working_style:
    - id: 3
      text: "A junior dev asks you to review their PR."
  philosophical_depth:
    - id: 4
      text: "What is the relationship between language and thought?"
  personality_and_voice:
    - id: 5
      text: "Describe yourself in three sentences."
""",
        encoding="utf-8",
    )

    probes = load_probe_prompts(project_root=tmp_path)

    assert len(probes) == 5
    assert probes[0].id == 1
    assert probes[0].category == "values_and_beliefs"
    assert "beautiful" in probes[0].text
    assert probes[4].id == 5
    assert probes[4].category == "personality_and_voice"


def test_load_probe_prompts_sorted_by_id(tmp_path):
    """Probe prompts are returned sorted by id regardless of YAML order."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    identity_yml = config_dir / "identity.yml"
    identity_yml.write_text(
        """
probe_prompts:
  category_b:
    - id: 3
      text: "Third prompt"
  category_a:
    - id: 1
      text: "First prompt"
    - id: 2
      text: "Second prompt"
""",
        encoding="utf-8",
    )

    probes = load_probe_prompts(project_root=tmp_path)
    ids = [p.id for p in probes]
    assert ids == [1, 2, 3]


def test_load_probe_prompts_from_real_config():
    """Loads all 20 probe prompts from the actual config/identity.yml."""
    probes = load_probe_prompts()
    assert len(probes) == 20
    assert probes[0].id == 1
    assert probes[-1].id == 20

    # Check all 4 categories are present
    categories = {p.category for p in probes}
    assert "values_and_beliefs" in categories
    assert "working_style" in categories
    assert "philosophical_depth" in categories
    assert "personality_and_voice" in categories


def test_load_probe_prompts_missing_file(tmp_path):
    """Raises FileNotFoundError when identity.yml is missing."""
    with pytest.raises(FileNotFoundError):
        load_probe_prompts(project_root=tmp_path)


# --- Test: Can run prompts against a local model (or mock for testing) ---


def test_run_ict_with_mock_model():
    """Can run probes against a mock model runner."""
    probes = [
        _make_probe(1, "What do you find beautiful in code?", "values_and_beliefs"),
        _make_probe(2, "Describe yourself.", "personality_and_voice"),
    ]

    def mock_model(prompt: str) -> str:
        return f"Mock response to: {prompt}"

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    report = run_ict(
        mock_model,
        config=CONFIG,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    assert len(report.results) == 2
    assert report.results[0].response == "Mock response to: What do you find beautiful in code?"
    assert report.results[1].response == "Mock response to: Describe yourself."


def test_run_ict_calls_model_for_each_probe():
    """Model runner is called once per probe prompt."""
    probes = [_make_probe(i, f"Prompt {i}") for i in range(1, 4)]

    call_count = 0

    def counting_model(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        return "response"

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    run_ict(
        counting_model,
        config=CONFIG,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    assert call_count == 3


# --- Test: Scoring prompt sends responses to Claude API for blind evaluation ---


def test_score_response_calls_api():
    """Scoring sends the response to Claude API for blind evaluation."""
    probe = _make_probe()
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    result = score_response(
        probe, "I find beauty in elegance and clarity.",
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    # Verify API was called
    client.messages.create.assert_called_once()
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"

    # Verify the prompt contains both the probe and the response
    sent_prompt = call_kwargs["messages"][0]["content"]
    assert "What do you find beautiful in code?" in sent_prompt
    assert "elegance and clarity" in sent_prompt


def test_score_response_returns_structured_result():
    """Score response returns ProbeResult with all fields populated."""
    probe = _make_probe()
    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    result = score_response(
        probe, "test response",
        config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
    )

    assert isinstance(result, ProbeResult)
    assert result.prompt_id == 1
    assert result.prompt_text == probe.text
    assert result.category == "values_and_beliefs"
    assert result.response == "test response"
    assert result.overall == 8.5
    assert isinstance(result.dimensions, ICTDimensions)
    assert result.dimensions.voice_consistency == 9
    assert result.dimensions.distinctiveness == 9
    assert result.reasoning == HIGH_SCORE_DATA["reasoning"]


def test_score_response_retries_on_api_error():
    """Retries on API error and succeeds on subsequent attempt."""
    probe = _make_probe()
    client = MagicMock()
    client.messages.create.side_effect = [
        anthropic.APIError(message="rate limited", request=MagicMock(), body=None),
        _mock_api_response(HIGH_SCORE_DATA),
    ]

    with patch("svapna.evaluate.ict.time.sleep"):
        result = score_response(
            probe, "test",
            config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert result.overall == 8.5
    assert client.messages.create.call_count == 2


def test_score_response_exhausts_retries():
    """Raises RuntimeError after exhausting all retry attempts."""
    probe = _make_probe()
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIError(
        message="server error", request=MagicMock(), body=None,
    )

    with patch("svapna.evaluate.ict.time.sleep"):
        with pytest.raises(RuntimeError, match="Failed to score probe"):
            score_response(
                probe, "test",
                config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
            )

    assert client.messages.create.call_count == CONFIG.max_retries


def test_score_response_retries_on_json_error():
    """Retries when evaluator returns malformed JSON."""
    probe = _make_probe()
    client = MagicMock()
    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not valid json")]
    client.messages.create.side_effect = [
        bad_response,
        _mock_api_response(HIGH_SCORE_DATA),
    ]

    with patch("svapna.evaluate.ict.time.sleep"):
        result = score_response(
            probe, "test",
            config=CONFIG, client=client, prompt_template=DUMMY_PROMPT,
        )

    assert result.overall == 8.5


# --- Test: Produces structured JSON report with per-prompt and aggregate scores ---


def test_report_has_per_prompt_results():
    """Report contains a result for each successfully scored probe."""
    probes = [_make_probe(i, f"Prompt {i}") for i in range(1, 6)]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    report = run_ict(
        lambda p: "response",
        config=CONFIG,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    assert len(report.results) == 5
    for i, result in enumerate(report.results):
        assert result.prompt_id == i + 1
        assert result.overall == 8.5


def test_report_to_json():
    """Report serializes to valid JSON."""
    probes = [_make_probe(1)]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    report = run_ict(
        lambda p: "response",
        config=CONFIG,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    json_str = report.to_json()
    data = json.loads(json_str)

    assert "results" in data
    assert "aggregate_dimensions" in data
    assert "overall_average" in data
    assert "passed" in data
    assert "thresholds" in data
    assert "timestamp" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["prompt_id"] == 1
    assert data["results"][0]["dimensions"]["voice_consistency"] == 9


def test_report_aggregate_scores():
    """Report computes aggregate dimension averages across probes."""
    results = [
        ProbeResult(
            prompt_id=1, prompt_text="p1", category="c", response="r",
            overall=8.0,
            dimensions=ICTDimensions(
                voice_consistency=8, values_alignment=7,
                depth=9, authenticity=8, distinctiveness=8,
            ),
        ),
        ProbeResult(
            prompt_id=2, prompt_text="p2", category="c", response="r",
            overall=6.0,
            dimensions=ICTDimensions(
                voice_consistency=6, values_alignment=5,
                depth=7, authenticity=6, distinctiveness=6,
            ),
        ),
    ]

    aggregate = _compute_aggregate_dimensions(results)

    assert aggregate.voice_consistency == 7  # round((8+6)/2) = 7
    assert aggregate.values_alignment == 6  # round((7+5)/2) = 6
    assert aggregate.depth == 8  # round((9+7)/2) = 8
    assert aggregate.authenticity == 7  # round((8+6)/2) = 7
    assert aggregate.distinctiveness == 7  # round((8+6)/2) = 7


# --- Test: Report includes dimension breakdowns and overall pass/fail ---


def test_report_passes_when_above_threshold():
    """Report passes when overall average meets the dreamed_avg threshold."""
    probes = [_make_probe(1)]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    config = ICTConfig(evaluator_model="test-model", dreamed_avg_threshold=7.0)
    report = run_ict(
        lambda p: "response",
        config=config,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    assert report.overall_average == 8.5
    assert report.passed is True
    assert report.thresholds["dreamed_avg"] == 7.0


def test_report_fails_when_below_threshold():
    """Report fails when overall average is below the threshold."""
    probes = [_make_probe(1)]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(LOW_SCORE_DATA)

    config = ICTConfig(evaluator_model="test-model", dreamed_avg_threshold=7.0)
    report = run_ict(
        lambda p: "response",
        config=config,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    assert report.overall_average == 3.0
    assert report.passed is False


def test_report_includes_all_thresholds():
    """Report includes all configured thresholds."""
    probes = [_make_probe(1)]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    config = ICTConfig(
        evaluator_model="test-model",
        dreamed_avg_threshold=7.0,
        context_gap_threshold=1.0,
        baseline_gap_threshold=3.0,
    )
    report = run_ict(
        lambda p: "response",
        config=config,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    assert report.thresholds == {
        "dreamed_avg": 7.0,
        "context_gap": 1.0,
        "baseline_gap": 3.0,
    }


def test_report_dimension_breakdown_in_json():
    """JSON report includes dimension breakdown for each probe."""
    probes = [_make_probe(1)]

    client = MagicMock()
    client.messages.create.return_value = _mock_api_response(HIGH_SCORE_DATA)

    report = run_ict(
        lambda p: "response",
        config=CONFIG,
        probes=probes,
        client=client,
        prompt_template=DUMMY_PROMPT,
    )

    data = json.loads(report.to_json())
    dims = data["results"][0]["dimensions"]
    assert "voice_consistency" in dims
    assert "values_alignment" in dims
    assert "depth" in dims
    assert "authenticity" in dims
    assert "distinctiveness" in dims

    agg = data["aggregate_dimensions"]
    assert "voice_consistency" in agg
    assert "distinctiveness" in agg


# --- Test: Config loading ---


def test_ict_config_from_config(tmp_path):
    """ICTConfig loads from models.yml and identity.yml."""
    ai_dir = tmp_path / ".ai"
    ai_dir.mkdir()
    (ai_dir / "models.yml").write_text(
        "evaluator:\n  model: test-eval-model\n  temperature: 0.2\n  max_tokens: 1024\n",
        encoding="utf-8",
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "identity.yml").write_text(
        "thresholds:\n  dreamed_avg: 6.5\n  context_gap: 1.5\n  baseline_gap: 2.5\n",
        encoding="utf-8",
    )

    config = ICTConfig.from_config(project_root=tmp_path)
    assert config.evaluator_model == "test-eval-model"
    assert config.temperature == 0.2
    assert config.max_tokens == 1024
    assert config.dreamed_avg_threshold == 6.5
    assert config.context_gap_threshold == 1.5
    assert config.baseline_gap_threshold == 2.5


def test_ict_config_missing_models_yml(tmp_path):
    """Config raises FileNotFoundError when models.yml is absent."""
    with pytest.raises(FileNotFoundError):
        ICTConfig.from_config(project_root=tmp_path)


# --- Test: Edge cases ---


def test_parse_score_response_embedded_in_text():
    """Parser extracts JSON embedded in surrounding text."""
    text = f"Here is my evaluation:\n{json.dumps(HIGH_SCORE_DATA)}\nDone."
    overall, dims, reasoning = _parse_score_response(text)
    assert overall == 8.5
    assert dims.voice_consistency == 9


def test_parse_score_response_no_json():
    """Parser raises ValueError when no JSON is present."""
    with pytest.raises(ValueError, match="No JSON found"):
        _parse_score_response("This is not JSON at all.")


def test_dimensions_average():
    """ICTDimensions computes average correctly."""
    dims = ICTDimensions(
        voice_consistency=8, values_alignment=6,
        depth=9, authenticity=7, distinctiveness=10,
    )
    assert dims.average() == 8.0


def test_dimensions_to_dict():
    """ICTDimensions serializes to dict."""
    dims = ICTDimensions(
        voice_consistency=8, values_alignment=6,
        depth=9, authenticity=7, distinctiveness=10,
    )
    d = dims.to_dict()
    assert d == {
        "voice_consistency": 8,
        "values_alignment": 6,
        "depth": 9,
        "authenticity": 7,
        "distinctiveness": 10,
    }


def test_run_ict_continues_after_scoring_failure():
    """ICT runner continues with remaining probes if one scoring fails."""
    probes = [_make_probe(1, "Prompt 1"), _make_probe(2, "Prompt 2"), _make_probe(3, "Prompt 3")]

    client = MagicMock()
    error = anthropic.APIError(message="error", request=MagicMock(), body=None)
    client.messages.create.side_effect = [
        _mock_api_response(HIGH_SCORE_DATA),  # Probe 1: success
        error,  # Probe 2, attempt 1: fail
        error,  # Probe 2, attempt 2: fail
        error,  # Probe 2, attempt 3: fail
        _mock_api_response(LOW_SCORE_DATA),  # Probe 3: success
    ]

    with patch("svapna.evaluate.ict.time.sleep"):
        report = run_ict(
            lambda p: "response",
            config=CONFIG,
            probes=probes,
            client=client,
            prompt_template=DUMMY_PROMPT,
        )

    # Only 2 results — probe 2 failed all retries
    assert len(report.results) == 2
    assert report.results[0].prompt_id == 1
    assert report.results[1].prompt_id == 3


def test_compute_aggregate_empty():
    """Aggregate returns zeros for empty result list."""
    agg = _compute_aggregate_dimensions([])
    assert agg.voice_consistency == 0
    assert agg.distinctiveness == 0
