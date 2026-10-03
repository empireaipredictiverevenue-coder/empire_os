from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from empire_os.digital_avatar_presence_api import PresenceBrowserRegistry
from empire_os.digital_avatar_presence_service import (
    _speech_ticket_path,
    create_presence_service_app,
)
from empire_os.digital_avatar_presence_spool import FilePresenceTranscriptSpool
from empire_os.digital_avatar_presence_token import issue_avatar_presence_token


NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)
SECRET = "presence-secret-" + ("x" * 32)


def app(tmp_path, secret=SECRET, audio_secret=""):
    return create_presence_service_app(
        secret_provider=lambda: secret,
        audio_push_secret_provider=lambda: audio_secret,
        speech_ticket_root=tmp_path / "tickets",
        spool=FilePresenceTranscriptSpool(tmp_path / "fast"),
        registry=PresenceBrowserRegistry(),
    )


def token():
    return issue_avatar_presence_token(
        secret=SECRET,
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        now=NOW,
        ttl_seconds=300,
        nonce="presence-service-test",
    ).token


def test_presence_service_health_is_fail_closed_without_secret(tmp_path):
    response = TestClient(
        app(tmp_path, secret=""),
        base_url="https://presence.empire.test",
    ).get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["presence_signing_configured"] is False
    assert body["canonical_truth_written"] is False
    assert body["speech_execution"] is False
    assert body["execution_authority"] == "none"


def test_presence_service_health_reports_prepared_not_live_execution(tmp_path):
    response = TestClient(
        app(tmp_path),
        base_url="https://presence.empire.test",
    ).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "COPILOT_PREPARED"
    assert body["fast_transcript_truth_class"] == "SESSION_OBSERVED"
    assert body["canonical_truth_written"] is False
    assert body["speech_execution"] is False
    assert body["commercial_execution"] is False
    assert body["execution_authority"] == "none"


def test_presence_health_reports_approved_turn_audio_separately(tmp_path):
    audio_secret = "audio-push-" + ("a" * 32)
    response = TestClient(
        app(tmp_path, audio_secret=audio_secret),
        base_url="https://presence.empire.test",
    ).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["presence_signing_configured"] is True
    assert body["approved_turn_audio_configured"] is True
    assert body["approved_turn_audio_ready"] is True
    assert body["speech_execution"] is False
    assert body["autonomous_speech_execution"] is False
    assert body["execution_authority"] == "none"


def test_speech_ticket_path_is_strict_and_cannot_escape_root(tmp_path):
    ticket_id = "avatar-speech:" + ("b" * 64)
    path = _speech_ticket_path(
        root=tmp_path / "tickets",
        ticket_id=ticket_id,
    )
    assert path.parent == tmp_path / "tickets"
    assert path.name == (
        "avatar-speech__" + ("b" * 64) + ".json"
    )

    for invalid in (
        "../avatar-speech:" + ("b" * 64),
        "avatar-speech:../../secret",
        "avatar-speech:" + ("g" * 64),
        "not-a-ticket",
    ):
        with pytest.raises(ValueError, match="ticket id invalid"):
            _speech_ticket_path(
                root=tmp_path / "tickets",
                ticket_id=invalid,
            )
