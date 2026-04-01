"""Test CLI entry points for all modules."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


# --- Test: --help shows usage for each module ---


@pytest.mark.parametrize("module", ["svapna.dream", "svapna.identity", "svapna.orchestrate"])
def test_help_shows_usage(module):
    """python -m <module> --help shows usage and exits cleanly."""
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout


# --- Test: dream CLI ---


def test_dream_help_content():
    """python -m svapna.dream --help shows dream-specific options."""
    result = subprocess.run(
        [sys.executable, "-m", "svapna.dream", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "--count" in result.stdout
    assert "--min-quality" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--skip-scoring" in result.stdout


@patch("svapna.dream.__main__.generate_batch")
@patch("svapna.dream.__main__.GeneratorConfig")
def test_dream_runs_with_defaults(mock_config_cls, mock_generate):
    """Dream CLI runs with default config when no flags are provided."""
    mock_config = MagicMock()
    mock_config.count = 5
    mock_config.min_quality = 7.0
    mock_config_cls.from_config.return_value = mock_config

    # Return empty list (no dreams generated)
    mock_generate.return_value = []

    from svapna.dream.__main__ import main

    with patch("sys.argv", ["svapna.dream"]), \
         patch("pathlib.Path.exists", return_value=False):
        main()

    mock_generate.assert_called_once()


@patch("svapna.dream.__main__.generate_batch")
@patch("svapna.dream.__main__.GeneratorConfig")
def test_dream_config_overrides_via_flags(mock_config_cls, mock_generate):
    """Dream CLI --count and --min-quality override config values."""
    mock_config = MagicMock()
    mock_config.count = 20
    mock_config.min_quality = 7.0
    mock_config_cls.from_config.return_value = mock_config

    mock_generate.return_value = []

    from svapna.dream.__main__ import main

    with patch("sys.argv", ["svapna.dream", "--count", "3", "--min-quality", "8.5"]), \
         patch("pathlib.Path.exists", return_value=False):
        main()

    # Config count should have been overridden
    assert mock_config.count == 3
    mock_generate.assert_called_once()


# --- Test: identity CLI ---


def test_identity_help_content():
    """python -m svapna.identity --help shows identity-specific options."""
    result = subprocess.run(
        [sys.executable, "-m", "svapna.identity", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "--model-path" in result.stdout
    assert "--lora-path" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--prompt-types" in result.stdout


@patch("svapna.identity.__main__.generate_preamble")
@patch("svapna.identity.__main__.save_preamble")
@patch("svapna.identity.__main__.GenerateConfig")
def test_identity_runs_with_model_path(mock_config_cls, mock_save, mock_generate):
    """Identity CLI runs when a model path is provided."""
    mock_config = MagicMock()
    mock_config.model_path = "test-model"
    mock_config.lora_path = None
    mock_config.prompt_types = ["who_are_you"]
    mock_config_cls.from_config.return_value = mock_config

    mock_preamble = MagicMock()
    mock_preamble.sections = {"who_are_you": "I am Narada."}
    mock_generate.return_value = mock_preamble
    mock_save.return_value = "data/identity/preamble.md"

    from svapna.identity.__main__ import main

    with patch("sys.argv", ["svapna.identity", "--model-path", "test-model"]):
        main()

    mock_generate.assert_called_once()
    mock_save.assert_called_once()


@patch("svapna.identity.__main__.generate_preamble")
@patch("svapna.identity.__main__.save_preamble")
@patch("svapna.identity.__main__.save_preamble_json")
@patch("svapna.identity.__main__.GenerateConfig")
def test_identity_json_flag(mock_config_cls, mock_save_json, mock_save, mock_generate):
    """Identity CLI --json flag saves both markdown and JSON."""
    mock_config = MagicMock()
    mock_config.model_path = "test-model"
    mock_config.lora_path = None
    mock_config.prompt_types = ["who_are_you"]
    mock_config_cls.from_config.return_value = mock_config

    mock_preamble = MagicMock()
    mock_preamble.sections = {"who_are_you": "I am Narada."}
    mock_generate.return_value = mock_preamble
    mock_save.return_value = "data/identity/preamble.md"
    mock_save_json.return_value = "data/identity/preamble.json"

    from svapna.identity.__main__ import main

    with patch("sys.argv", ["svapna.identity", "--model-path", "test-model", "--json"]):
        main()

    mock_save.assert_called_once()
    mock_save_json.assert_called_once()


@patch("svapna.identity.__main__.GenerateConfig")
def test_identity_exits_without_model(mock_config_cls, capsys):
    """Identity CLI prints error and returns when no model is configured."""
    mock_config = MagicMock()
    mock_config.model_path = ""
    mock_config.lora_path = None
    mock_config.prompt_types = ["who_are_you"]
    mock_config_cls.from_config.return_value = mock_config

    from svapna.identity.__main__ import main

    with patch("sys.argv", ["svapna.identity"]):
        main()

    captured = capsys.readouterr()
    assert "No model path configured" in captured.out


@patch("svapna.identity.__main__.generate_preamble")
@patch("svapna.identity.__main__.save_preamble")
@patch("svapna.identity.__main__.GenerateConfig")
def test_identity_config_overrides_via_flags(mock_config_cls, mock_save, mock_generate):
    """Identity CLI flags override config values."""
    mock_config = MagicMock()
    mock_config.model_path = "original-model"
    mock_config.lora_path = None
    mock_config.prompt_types = ["who_are_you", "what_do_you_value", "how_do_you_work"]
    mock_config_cls.from_config.return_value = mock_config

    mock_preamble = MagicMock()
    mock_preamble.sections = {"who_are_you": "I am Narada."}
    mock_generate.return_value = mock_preamble
    mock_save.return_value = "data/identity/preamble.md"

    from svapna.identity.__main__ import main

    with patch("sys.argv", [
        "svapna.identity",
        "--model-path", "override-model",
        "--prompt-types", "who_are_you",
    ]):
        main()

    # Config should reflect overrides
    assert mock_config.model_path == "override-model"
    assert mock_config.prompt_types == ["who_are_you"]


# --- Test: orchestrate CLI ---


def test_orchestrate_help_content():
    """python -m svapna.orchestrate --help shows orchestrate-specific options."""
    result = subprocess.run(
        [sys.executable, "-m", "svapna.orchestrate", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "--step" in result.stdout
    assert "--no-train" in result.stdout
    assert "--resume" in result.stdout
    assert "--from-step" in result.stdout
