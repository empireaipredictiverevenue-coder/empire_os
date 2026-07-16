"""Tests for the Telegram bot module."""
from unittest.mock import patch, MagicMock

import pytest
from empire_os.funnel import SQLiteBackend, FunnelState, transition
from empire_os.telegram_bot import (
    send_message, send_brief, build_brief_text, send_alert,
)


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    transition(b, "p1", FunnelState.DISCOVERED.value, "scout", notes="niche=roofing")
    return b


class TestSendMessage:
    @patch("empire_os.telegram_bot._post")
    def test_send_message_calls_api(self, mock_post):
        mock_post.return_value = {"ok": True}
        result = send_message("test-token", "123", "hello")
        assert result["ok"] is True
        mock_post.assert_called_once()

    @patch("empire_os.telegram_bot._post")
    def test_send_message_failure(self, mock_post):
        mock_post.return_value = {"ok": False, "error": "timeout"}
        result = send_message("bad-token", "123", "hi")
        assert result["ok"] is False


class TestBuildBrief:
    def test_build_brief_text(self, backend):
        text = build_brief_text(backend)
        assert "Empire OS v3" in text
        assert "Discovered" in text
        assert "1" in text  # one discovered prospect

    def test_build_brief_empty_backend(self):
        b = SQLiteBackend(":memory:")
        b.ensure_schema()
        text = build_brief_text(b)
        assert "Discovered: 0" in text


class TestSendBrief:
    @patch("empire_os.telegram_bot.send_message")
    def test_send_brief_no_config(self, mock_send):
        result = send_brief(MagicMock(), token="", chat_id="")
        assert result["ok"] is False
        assert "not set" in result["error"]
        mock_send.assert_not_called()

    @patch("empire_os.telegram_bot.send_message")
    def test_send_brief_with_config(self, mock_send, backend):
        mock_send.return_value = {"ok": True}
        result = send_brief(backend, token="tok", chat_id="123")
        assert result["ok"] is True
        mock_send.assert_called_once()


class TestSendAlert:
    @patch("empire_os.telegram_bot.send_message")
    def test_send_alert(self, mock_send):
        mock_send.return_value = {"ok": True}
        r = send_alert("test alert", token="tok", chat_id="123")
        assert r["ok"] is True
