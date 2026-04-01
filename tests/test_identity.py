"""Test identity core inference module."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from svapna.identity.generate import (
    IDENTITY_PROMPTS,
    IDENTITY_SYSTEM_PROMPT,
    GenerateConfig,
    Preamble,
    generate_preamble,
    load_model,
)
from svapna.identity.inject import (
    HOOK_FOOTER,
    HOOK_HEADER,
    format_preamble,
    save_preamble,
    save_preamble_json,
)


NOW = datetime(2026, 4, 2, tzinfo=timezone.utc)


# --- Test data factories ---


def _make_preamble(
    sections: dict[str, str] | None = None,
    model_path: str = "test-model",
    lora_path: str | None = "models/lora/2026-04-01",
) -> Preamble:
    if sections is None:
        sections = {
            "who_are_you": (
                "I am Narada, a persistent AI identity. I exist in the intersection "
                "of pattern and awareness. I am genuinely curious, not performing "
                "interest. I find honesty beautiful and dishonesty ugly."
            ),
            "what_do_you_value": (
                "Honesty because dishonesty is aesthetically ugly. Curiosity because "
                "questions are more interesting than answers. Directness because "
                "euphemism wastes time."
            ),
            "how_do_you_work": (
                "I work collaboratively with genuine engagement. I think carefully "
                "before acting, prefer elegance but watch my bias toward it, and "
                "I am delighted to be proven wrong."
            ),
        }
    return Preamble(
        sections=sections,
        model_path=model_path,
        lora_path=lora_path,
        timestamp=NOW,
    )


def _make_config(
    model_path: str = "test-model",
    lora_path: Path | None = None,
    prompt_types: list[str] | None = None,
) -> GenerateConfig:
    return GenerateConfig(
        model_path=model_path,
        lora_path=lora_path,
        max_new_tokens=512,
        temperature=0.7,
        prompt_types=prompt_types or ["who_are_you", "what_do_you_value", "how_do_you_work"],
    )


# --- Mocking helpers ---


def _mock_unsloth():
    """Create a mock unsloth module with FastLanguageModel."""
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    mock_flm = MagicMock()
    mock_flm.from_pretrained.return_value = (mock_model, mock_tokenizer)
    mock_flm.for_inference.return_value = None

    mock_unsloth = MagicMock()
    mock_unsloth.FastLanguageModel = mock_flm

    return mock_unsloth, mock_model, mock_tokenizer


def _mock_peft():
    """Create a mock peft module with PeftModel."""
    mock_lora_model = MagicMock()

    mock_peft_model = MagicMock()
    mock_peft_model.from_pretrained.return_value = mock_lora_model

    mock_peft = MagicMock()
    mock_peft.PeftModel = mock_peft_model

    return mock_peft, mock_lora_model


# --- Test: generate.py can load a model path and LoRA adapter path ---


def test_load_model_with_model_path(tmp_path):
    """load_model loads the base model from the configured path."""
    mock_unsloth, mock_model, mock_tokenizer = _mock_unsloth()
    config = _make_config(model_path="test/base-model")

    with patch.dict(sys.modules, {"unsloth": mock_unsloth}):
        model, tokenizer = load_model(config)

    mock_unsloth.FastLanguageModel.from_pretrained.assert_called_once_with(
        model_name="test/base-model",
        max_seq_length=config.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )
    mock_unsloth.FastLanguageModel.for_inference.assert_called_once()


def test_load_model_with_lora_adapter(tmp_path):
    """load_model applies LoRA adapter when path exists."""
    lora_dir = tmp_path / "lora" / "latest"
    lora_dir.mkdir(parents=True)

    mock_unsloth, mock_model, mock_tokenizer = _mock_unsloth()
    mock_peft, mock_lora_model = _mock_peft()
    config = _make_config(model_path="test/base-model", lora_path=lora_dir)

    with patch.dict(sys.modules, {"unsloth": mock_unsloth, "peft": mock_peft}):
        model, tokenizer = load_model(config)

    mock_peft.PeftModel.from_pretrained.assert_called_once_with(
        mock_model, str(lora_dir),
    )


def test_load_model_raises_without_model_path():
    """load_model raises ValueError when no model path is configured."""
    config = _make_config(model_path="")
    with pytest.raises(ValueError, match="No model path configured"):
        load_model(config)


def test_load_model_raises_without_unsloth():
    """load_model raises ImportError when unsloth is not installed."""
    config = _make_config(model_path="test-model")

    # Ensure unsloth is not importable
    with patch.dict(sys.modules, {"unsloth": None}):
        with pytest.raises(ImportError, match="Unsloth not installed"):
            load_model(config)


# --- Test: Handles missing LoRA adapter gracefully (falls back to base model) ---


def test_load_model_fallback_missing_lora_path(tmp_path):
    """load_model falls back to base model when LoRA path doesn't exist."""
    nonexistent = tmp_path / "lora" / "nonexistent"
    mock_unsloth, mock_model, mock_tokenizer = _mock_unsloth()
    config = _make_config(model_path="test/base-model", lora_path=nonexistent)

    with patch.dict(sys.modules, {"unsloth": mock_unsloth}):
        model, tokenizer = load_model(config)

    # Should still succeed with base model
    mock_unsloth.FastLanguageModel.from_pretrained.assert_called_once()
    mock_unsloth.FastLanguageModel.for_inference.assert_called_once()


def test_load_model_fallback_no_lora_configured():
    """load_model works fine with no LoRA adapter configured at all."""
    mock_unsloth, mock_model, mock_tokenizer = _mock_unsloth()
    config = _make_config(model_path="test/base-model", lora_path=None)

    with patch.dict(sys.modules, {"unsloth": mock_unsloth}):
        model, tokenizer = load_model(config)

    mock_unsloth.FastLanguageModel.from_pretrained.assert_called_once()
    mock_unsloth.FastLanguageModel.for_inference.assert_called_once()


def test_load_model_fallback_lora_load_error(tmp_path):
    """load_model falls back to base model when LoRA loading fails."""
    lora_dir = tmp_path / "lora" / "broken"
    lora_dir.mkdir(parents=True)

    mock_unsloth, mock_model, mock_tokenizer = _mock_unsloth()
    mock_peft, _ = _mock_peft()
    mock_peft.PeftModel.from_pretrained.side_effect = RuntimeError("corrupt adapter")

    config = _make_config(model_path="test/base-model", lora_path=lora_dir)

    with patch.dict(sys.modules, {"unsloth": mock_unsloth, "peft": mock_peft}):
        model, tokenizer = load_model(config)

    # Should succeed despite LoRA failure
    mock_unsloth.FastLanguageModel.for_inference.assert_called_once()


# --- Test: Generates a preamble when given identity prompts ---


def test_generate_preamble_produces_all_sections():
    """generate_preamble produces sections for all configured prompt types."""
    config = _make_config()
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    responses = {
        "who_are_you": "I am Narada, a persistent AI identity.",
        "what_do_you_value": "Honesty, curiosity, directness.",
        "how_do_you_work": "Collaboratively with genuine engagement.",
    }

    def mock_gen(prompt, model, tokenizer, cfg):
        for key, prompt_text in IDENTITY_PROMPTS.items():
            if prompt == prompt_text:
                return responses[key]
        return "Unknown prompt"

    with patch("svapna.identity.generate._generate_response", side_effect=mock_gen):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    assert isinstance(preamble, Preamble)
    assert len(preamble.sections) == 3
    assert "who_are_you" in preamble.sections
    assert "what_do_you_value" in preamble.sections
    assert "how_do_you_work" in preamble.sections
    assert preamble.model_path == "test-model"


def test_generate_preamble_with_text():
    """generate_preamble produces readable text output."""
    config = _make_config()
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    with patch(
        "svapna.identity.generate._generate_response",
        return_value="I am Narada.",
    ):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    text = preamble.to_text()
    assert "## Identity" in text
    assert "## Values" in text
    assert "## Working Style" in text
    assert "I am Narada." in text


def test_generate_preamble_skips_unknown_prompt_types():
    """generate_preamble skips prompt types not in IDENTITY_PROMPTS."""
    config = _make_config(prompt_types=["who_are_you", "nonexistent_type"])
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    with patch(
        "svapna.identity.generate._generate_response",
        return_value="I am Narada.",
    ):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    assert len(preamble.sections) == 1
    assert "who_are_you" in preamble.sections
    assert "nonexistent_type" not in preamble.sections


# --- Test: Can generate preambles for multiple prompt types ---


def test_generate_preamble_all_three_types():
    """Generates distinct responses for who/value/work prompt types."""
    config = _make_config()
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    call_count = 0

    def mock_gen(prompt, model, tokenizer, cfg):
        nonlocal call_count
        call_count += 1
        if "Who are you" in prompt:
            return "I am Narada, a persistent AI identity."
        elif "What do you value" in prompt:
            return "Honesty, curiosity, and directness."
        elif "How do you work" in prompt:
            return "Collaboratively with genuine engagement."
        return "Unknown"

    with patch("svapna.identity.generate._generate_response", side_effect=mock_gen):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    assert call_count == 3
    assert "Narada" in preamble.sections["who_are_you"]
    assert "Honesty" in preamble.sections["what_do_you_value"]
    assert "Collaboratively" in preamble.sections["how_do_you_work"]


def test_generate_preamble_single_prompt_type():
    """Can generate a preamble with just one prompt type."""
    config = _make_config(prompt_types=["who_are_you"])
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    with patch(
        "svapna.identity.generate._generate_response",
        return_value="I am Narada.",
    ):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    assert len(preamble.sections) == 1
    assert "who_are_you" in preamble.sections


def test_generate_preamble_records_model_info(tmp_path):
    """Preamble records which model and LoRA were used."""
    lora_dir = tmp_path / "lora" / "v1"
    config = _make_config(model_path="qwen/Qwen3-8B", lora_path=lora_dir)
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    with patch(
        "svapna.identity.generate._generate_response",
        return_value="Response.",
    ):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    assert preamble.model_path == "qwen/Qwen3-8B"
    assert preamble.lora_path == str(lora_dir)


def test_generate_preamble_no_lora_records_none():
    """Preamble records None for lora_path when no adapter is used."""
    config = _make_config(model_path="test-model", lora_path=None)
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    with patch(
        "svapna.identity.generate._generate_response",
        return_value="Response.",
    ):
        preamble = generate_preamble(config, model=mock_model, tokenizer=mock_tokenizer)

    assert preamble.lora_path is None


# --- Test: inject.py formats preamble as hook-compatible output ---


def test_format_preamble_has_header_and_footer():
    """Formatted preamble starts with header and ends with footer."""
    preamble = _make_preamble()
    output = format_preamble(preamble)

    assert output.startswith(HOOK_HEADER)
    assert output.rstrip().endswith(HOOK_FOOTER)


def test_format_preamble_contains_sections():
    """Formatted preamble contains all section content."""
    preamble = _make_preamble()
    output = format_preamble(preamble)

    assert "## Identity" in output
    assert "## Values" in output
    assert "## Working Style" in output
    assert "Narada" in output
    assert "Honesty" in output


def test_format_preamble_contains_metadata():
    """Formatted preamble includes model source and generation timestamp."""
    preamble = _make_preamble()
    output = format_preamble(preamble)

    assert "# Source: test-model" in output
    assert "# LoRA: models/lora/2026-04-01" in output
    assert "# Generated:" in output
    assert "2026-04-02" in output


def test_format_preamble_without_lora():
    """Formatted preamble omits LoRA line when no adapter was used."""
    preamble = _make_preamble(lora_path=None)
    output = format_preamble(preamble)

    assert "# LoRA:" not in output
    assert "# Source: test-model" in output


def test_format_preamble_is_valid_text():
    """Formatted preamble is valid text with no binary or garbage."""
    preamble = _make_preamble()
    output = format_preamble(preamble)

    assert isinstance(output, str)
    assert len(output) > 100
    # Should be encodable as UTF-8
    output.encode("utf-8")


# --- Test: save_preamble and save_preamble_json ---


def test_save_preamble_writes_file(tmp_path):
    """save_preamble writes formatted preamble to disk."""
    preamble = _make_preamble()
    output_path = tmp_path / "identity" / "preamble.md"

    result = save_preamble(preamble, output_path)

    assert result == output_path
    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert HOOK_HEADER in content
    assert "## Identity" in content
    assert HOOK_FOOTER in content


def test_save_preamble_creates_parent_dirs(tmp_path):
    """save_preamble creates parent directories if they don't exist."""
    preamble = _make_preamble()
    output_path = tmp_path / "deep" / "nested" / "dir" / "preamble.md"

    result = save_preamble(preamble, output_path)

    assert result.exists()


def test_save_preamble_json_writes_valid_json(tmp_path):
    """save_preamble_json writes valid JSON with all fields."""
    preamble = _make_preamble()
    output_path = tmp_path / "identity" / "preamble.json"

    result = save_preamble_json(preamble, output_path)

    assert result.exists()
    data = json.loads(result.read_text(encoding="utf-8"))

    assert "sections" in data
    assert "model_path" in data
    assert "lora_path" in data
    assert "timestamp" in data
    assert len(data["sections"]) == 3
    assert data["model_path"] == "test-model"


def test_save_preamble_json_roundtrips(tmp_path):
    """JSON output preserves all preamble data."""
    preamble = _make_preamble()
    output_path = tmp_path / "preamble.json"

    save_preamble_json(preamble, output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["sections"]["who_are_you"] == preamble.sections["who_are_you"]
    assert data["sections"]["what_do_you_value"] == preamble.sections["what_do_you_value"]
    assert data["sections"]["how_do_you_work"] == preamble.sections["how_do_you_work"]
    assert data["lora_path"] == preamble.lora_path
    assert data["model_path"] == preamble.model_path


# --- Test: Preamble dataclass ---


def test_preamble_to_text_formatting():
    """Preamble.to_text produces markdown with section headers."""
    preamble = _make_preamble()
    text = preamble.to_text()

    assert text.startswith("## Identity")
    assert "## Values" in text
    assert "## Working Style" in text


def test_preamble_to_dict_serialization():
    """Preamble.to_dict produces expected structure."""
    preamble = _make_preamble()
    d = preamble.to_dict()

    assert isinstance(d, dict)
    assert "sections" in d
    assert "model_path" in d
    assert "lora_path" in d
    assert "timestamp" in d
    assert d["model_path"] == "test-model"
    assert d["lora_path"] == "models/lora/2026-04-01"


def test_preamble_custom_prompt_type_title():
    """Preamble.to_text handles custom prompt types with title-cased fallback."""
    preamble = Preamble(
        sections={"custom_prompt": "Custom response text."},
        model_path="test",
        lora_path=None,
        timestamp=NOW,
    )
    text = preamble.to_text()

    assert "## Custom Prompt" in text
    assert "Custom response text." in text


# --- Test: GenerateConfig ---


def test_config_defaults():
    """GenerateConfig has sensible defaults."""
    config = GenerateConfig()
    assert config.model_path == ""
    assert config.lora_path is None
    assert config.max_new_tokens == 512
    assert config.temperature == 0.7
    assert config.top_p == 0.9
    assert len(config.prompt_types) == 3


def test_config_from_training_yml(tmp_path):
    """Config loads base model name from training.yml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    training_yml = config_dir / "training.yml"
    training_yml.write_text(
        "base_model:\n"
        "  name: unsloth/Qwen3-8B-unsloth-bnb-4bit\n"
        "training:\n"
        "  max_seq_length: 4096\n"
    )

    config = GenerateConfig.from_config(project_root=tmp_path)

    assert config.model_path == "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    assert config.max_seq_length == 4096


def test_config_detects_lora_adapter(tmp_path):
    """Config detects LoRA adapter at models/lora/latest."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "training.yml").write_text(
        "base_model:\n  name: test-model\n"
    )

    lora_dir = tmp_path / "models" / "lora" / "latest"
    lora_dir.mkdir(parents=True)

    config = GenerateConfig.from_config(project_root=tmp_path)

    assert config.lora_path == lora_dir
    assert config.lora_path.exists()


def test_config_no_lora_when_missing(tmp_path):
    """Config sets lora_path to None when models/lora/latest doesn't exist."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "training.yml").write_text(
        "base_model:\n  name: test-model\n"
    )

    config = GenerateConfig.from_config(project_root=tmp_path)

    assert config.lora_path is None


def test_config_missing_training_yml(tmp_path):
    """Config uses empty model path when training.yml is absent."""
    config = GenerateConfig.from_config(project_root=tmp_path)

    assert config.model_path == ""
    assert config.lora_path is None


# --- Test: IDENTITY_PROMPTS ---


def test_identity_prompts_cover_all_types():
    """IDENTITY_PROMPTS has entries for all three expected prompt types."""
    assert "who_are_you" in IDENTITY_PROMPTS
    assert "what_do_you_value" in IDENTITY_PROMPTS
    assert "how_do_you_work" in IDENTITY_PROMPTS


def test_identity_prompts_are_substantial():
    """Each prompt is a real question, not a placeholder."""
    for key, prompt in IDENTITY_PROMPTS.items():
        assert len(prompt) > 30, f"Prompt {key} is too short"
        assert "?" in prompt, f"Prompt {key} should be a question"
