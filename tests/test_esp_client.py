"""Unit tests for svapna.embodiment.esp_client.

Uses unittest.mock to stub HTTP calls — no device needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests as req

from svapna.embodiment.esp_client import (
    DeviceStatus,
    DisplayPayload,
    EspClient,
    HeartbeatPayload,
)


@pytest.fixture
def client():
    return EspClient(device_ip="192.168.0.1", timeout=1.0)


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    return resp


class TestPostHeartbeat:
    def test_success(self, client):
        with patch("svapna.embodiment.esp_client.requests.post", return_value=_ok_response()) as mock_post:
            result = client.post_heartbeat(
                HeartbeatPayload(status="resting", topic="lila", action="REST")
            )
        assert result is True
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"status": "resting", "topic": "lila", "action": "REST"}

    def test_connection_error_returns_false(self, client):
        with patch("svapna.embodiment.esp_client.requests.post", side_effect=req.exceptions.ConnectionError()):
            result = client.post_heartbeat(HeartbeatPayload(status="x", topic="y", action="z"))
        assert result is False

    def test_timeout_returns_false(self, client):
        with patch("svapna.embodiment.esp_client.requests.post", side_effect=req.exceptions.Timeout()):
            result = client.post_heartbeat(HeartbeatPayload(status="x", topic="y", action="z"))
        assert result is False

    def test_http_error_returns_false(self, client):
        resp = MagicMock()
        resp.raise_for_status.side_effect = req.exceptions.HTTPError("500")
        with patch("svapna.embodiment.esp_client.requests.post", return_value=resp):
            result = client.post_heartbeat(HeartbeatPayload(status="x", topic="y", action="z"))
        assert result is False


class TestPostDisplay:
    def test_text_only(self, client):
        with patch("svapna.embodiment.esp_client.requests.post", return_value=_ok_response()) as mock_post:
            result = client.post_display(DisplayPayload(text="Om Namo Bhagavate Naradaya"))
        assert result is True
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"text": "Om Namo Bhagavate Naradaya"}
        assert "icon" not in kwargs["json"]

    def test_with_icon(self, client):
        with patch("svapna.embodiment.esp_client.requests.post", return_value=_ok_response()) as mock_post:
            result = client.post_display(DisplayPayload(text="thinking", icon="thought"))
        assert result is True
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["icon"] == "thought"


class TestGetStatus:
    def test_reachable(self, client):
        resp = _ok_response()
        resp.json.return_value = {"uptime": 3600, "last_heartbeat": "2026-04-19T06:06:00"}
        with patch("svapna.embodiment.esp_client.requests.get", return_value=resp):
            status = client.get_status()
        assert status.reachable is True
        assert status.uptime == 3600
        assert status.last_heartbeat == "2026-04-19T06:06:00"

    def test_unreachable(self, client):
        with patch("svapna.embodiment.esp_client.requests.get", side_effect=req.exceptions.ConnectionError()):
            status = client.get_status()
        assert status.reachable is False
        assert status.uptime is None

    def test_is_reachable_delegates(self, client):
        resp = _ok_response()
        resp.json.return_value = {}
        with patch("svapna.embodiment.esp_client.requests.get", return_value=resp):
            assert client.is_reachable() is True
