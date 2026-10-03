from datetime import datetime, timedelta, timezone
import hashlib

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from empire_os.digital_avatar_presence_api import (
    PresenceBrowserRegistry,
    create_digital_avatar_presence_app,
)
from empire_os.digital_avatar_presence_audio import PresenceAudioPlaybackResult
from empire_os.digital_avatar_presence_token import issue_avatar_presence_token


NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)
SECRET = "presence-secret-" + ("x" * 32)


def token(now=NOW, ttl_seconds=300):
    return issue_avatar_presence_token(
        secret=SECRET,
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        now=now,
        ttl_seconds=ttl_seconds,
        nonce="presence-browser-test",
    ).token


def make_client(now=NOW, transcript_sink=None, **kwargs):
    app = create_digital_avatar_presence_app(
        secret_provider=lambda: SECRET,
        registry=PresenceBrowserRegistry(),
        now_provider=lambda: now,
        transcript_sink=transcript_sink,
        **kwargs,
    )
    return TestClient(app, base_url="https://presence.empire.test")


def test_presence_page_requires_short_lived_token():
    response = make_client().get("/avatar/presence")
    assert response.status_code == 401
    assert response.json()["detail"] == "presence_token_required"


def test_presence_page_exchanges_url_token_for_secure_cookie():
    issued = token()
    client = make_client()
    response = client.get(
        "/avatar/presence",
        params={"token": issued},
    )
    assert response.status_code == 200
    assert issued not in response.text
    assert "Digital Avatar Presence starting" in response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    cookie = response.headers["set-cookie"]
    assert "empire_avatar_presence=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "token=" not in cookie


def test_authenticated_presence_socket_starts_audio_locked():
    client = make_client()
    response = client.get(
        "/avatar/presence",
        params={"token": token()},
    )
    assert response.status_code == 200

    cookie = client.cookies.get("empire_avatar_presence")
    with client.websocket_connect(
        "/avatar/presence/ws",
        headers={"cookie": f"empire_avatar_presence={cookie}"},
    ) as socket:
        socket.send_json({
            "type": "hello",
            "protocol": "empire.avatar.presence.v1",
        })
        ready = socket.receive_json()
        assert ready["type"] == "presence.ready"
        assert ready["meeting_id"] == "meeting-001"
        assert ready["avatar_id"] == "avatar-phil-v1"
        assert ready["bot_id"] == "bot-123"
        assert ready["audio_locked"] is True
        assert ready["visual_attached"] is False
        assert ready["speech_transmission_allowed"] is False
        assert ready["commercial_execution_allowed"] is False
        assert ready["execution_authority"] == "none"

        socket.send_json({"type": "ping"})
        pong = socket.receive_json()
        assert pong["type"] == "pong"
        assert pong["execution_authority"] == "none"


def test_presence_browser_cannot_issue_media_commands():
    client = make_client()
    client.get("/avatar/presence", params={"token": token()})
    cookie = client.cookies.get("empire_avatar_presence")
    with client.websocket_connect(
        "/avatar/presence/ws",
        headers={"cookie": f"empire_avatar_presence={cookie}"},
    ) as socket:
        socket.send_json({
            "type": "hello",
            "protocol": "empire.avatar.presence.v1",
        })
        socket.receive_json()
        socket.send_json({
            "type": "play_audio",
            "audio_sha256": "fake",
        })
        error = socket.receive_json()
        assert error == {
            "type": "error",
            "code": "client_command_not_allowed",
            "execution_authority": "none",
        }


def test_presence_socket_without_session_is_rejected():
    client = make_client()
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/avatar/presence/ws"):
            pass
    assert exc.value.code == 4401


def test_expired_url_token_is_rejected():
    future = NOW + timedelta(minutes=6)
    expired = token(now=NOW, ttl_seconds=300)
    client = make_client(now=future)
    response = client.get(
        "/avatar/presence",
        params={"token": expired},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "presence_token_invalid"


def test_runtime_javascript_only_plays_server_pushed_approved_pcm():
    response = make_client().get("/avatar/presence/runtime.js")
    assert response.status_code == 200
    body = response.text
    assert "history.replaceState" in body
    assert "/avatar/presence/ws" in body
    assert "AudioContext" in body
    assert 'data.type === "speech.audio.begin"' in body
    assert 'data.type === "speech.audio.chunk"' in body
    assert 'data.type === "speech.audio.end"' in body
    assert 'type: "speech.playback.completed"' in body
    assert "crypto.subtle.digest" in body
    assert "getUserMedia" not in body
    assert "play_audio" not in body
    assert "no-store" in response.headers["cache-control"]


def test_presence_socket_accepts_fast_transcript_as_noncanonical_signal():
    observed = []
    client = make_client(transcript_sink=observed.append)
    client.get("/avatar/presence", params={"token": token()})
    cookie = client.cookies.get("empire_avatar_presence")
    with client.websocket_connect(
        "/avatar/presence/ws",
        headers={"cookie": f"empire_avatar_presence={cookie}"},
    ) as socket:
        socket.send_json({
            "type": "hello",
            "protocol": "empire.avatar.presence.v1",
        })
        socket.receive_json()
        socket.send_json({
            "type": "recall.transcript.observed",
            "payload": {
                "transcript": {
                    "participant": {"id": 7, "name": "Buyer"},
                    "words": [
                        {"text": "Can"},
                        {"text": "you"},
                        {"text": "deploy"},
                        {"text": "this?"},
                    ],
                }
            },
        })
        ack = socket.receive_json()

    assert ack["type"] == "transcript.accepted"
    assert ack["truth_class"] == "SESSION_OBSERVED"
    assert ack["canonical_evidence"] is False
    assert ack["commercial_truth_allowed"] is False
    assert ack["execution_authority"] == "none"
    assert len(observed) == 1
    assert observed[0].text == "Can you deploy this?"
    assert observed[0].canonical_evidence is False
    assert observed[0].commercial_truth_allowed is False


def test_presence_runtime_connects_to_recall_transcript_socket():
    body = make_client().get("/avatar/presence/runtime.js").text
    assert "wss://meeting-data.bot.recall.ai/api/v1/transcript" in body
    assert 'type: "recall.transcript.observed"' in body
    assert "getUserMedia" not in body


PUSH_SECRET = "presence-audio-push-" + ("y" * 32)


class FakeAudioBroker:
    def __init__(self, *, error=None):
        self.error = error
        self.commands = []
        self.attached = []
        self.detached = []

    def attach(self, *, session_id, claims, socket):
        self.attached.append((session_id, claims, socket))

    def detach(self, *, session_id):
        self.detached.append(session_id)

    def acknowledge(self, *, session_id, message):
        return False

    async def push_pcm(self, command, *, timeout_s):
        self.commands.append((command, timeout_s))
        if self.error is not None:
            raise self.error
        return PresenceAudioPlaybackResult(
            ticket_id=command.ticket_id,
            meeting_id=command.meeting_id,
            avatar_id=command.avatar_id,
            bot_id=command.bot_id,
            audio_sha256=command.audio_sha256,
            pcm_bytes=command.pcm_bytes,
            sample_rate=command.sample_rate,
            playback_completed=True,
        )


def audio_push_headers(pcm, **overrides):
    headers = {
        "authorization": "Bearer " + PUSH_SECRET,
        "content-type": "application/octet-stream",
        "x-empire-ticket-id": "avatar-speech:" + ("a" * 64),
        "x-empire-meeting-id": "meeting-001",
        "x-empire-avatar-id": "avatar-phil-v1",
        "x-empire-bot-id": "bot-123",
        "x-empire-audio-sha256": hashlib.sha256(pcm).hexdigest(),
        "x-empire-sample-rate": "24000",
    }
    headers.update(overrides)
    return headers


def test_internal_audio_push_requires_secret_and_exact_ticket_binding():
    pcm = b"\x01\x00\x02\x00"
    calls = {"validate": [], "finalize": []}
    broker = FakeAudioBroker()

    def validator(**kwargs):
        calls["validate"].append(kwargs)

    def finalizer(**kwargs):
        calls["finalize"].append(kwargs)
        return {"state": "completed"}

    client = make_client(
        audio_push_secret_provider=lambda: PUSH_SECRET,
        speech_ticket_validator=validator,
        speech_ticket_finalizer=finalizer,
        audio_broker=broker,
    )
    unauthorized = client.post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers={
            **audio_push_headers(pcm),
            "authorization": "Bearer wrong",
        },
    )
    assert unauthorized.status_code == 401
    assert broker.commands == []

    response = client.post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers=audio_push_headers(pcm),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["speech_transmission_performed"] is True
    assert body["browser_playback_completed"] is True
    assert body["meeting_audio_delivery_verified"] is False
    assert body["ticket_state"] == "completed"
    assert body["raw_audio_persisted"] is False
    assert len(calls["validate"]) == 1
    assert calls["validate"][0]["pcm_bytes"] == len(pcm)
    assert calls["validate"][0]["sample_rate"] == 24000
    assert len(calls["finalize"]) == 1
    assert calls["finalize"][0]["performed"] is True
    assert len(broker.commands) == 1


def test_internal_audio_push_rejects_body_hash_mismatch_before_ticket_validation():
    pcm = b"\x01\x00"
    calls = []
    client = make_client(
        audio_push_secret_provider=lambda: PUSH_SECRET,
        speech_ticket_validator=lambda **kwargs: calls.append(kwargs),
        speech_ticket_finalizer=lambda **kwargs: {"state": "completed"},
        audio_broker=FakeAudioBroker(),
    )
    response = client.post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers=audio_push_headers(
            pcm,
            **{"x-empire-audio-sha256": "0" * 64},
        ),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "presence_audio_sha256_mismatch"
    assert calls == []


def test_internal_audio_delivery_failure_moves_ticket_to_reconciliation():
    pcm = b"\x01\x00"
    finalized = []
    broker = FakeAudioBroker(
        error=RuntimeError("presence browser disconnected")
    )
    client = make_client(
        audio_push_secret_provider=lambda: PUSH_SECRET,
        speech_ticket_validator=lambda **kwargs: None,
        speech_ticket_finalizer=lambda **kwargs: (
            finalized.append(kwargs) or {"state": "reconciliation_required"}
        ),
        audio_broker=broker,
    )
    response = client.post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers=audio_push_headers(pcm),
    )
    assert response.status_code == 503
    assert "presence browser disconnected" in response.json()["detail"]
    assert len(finalized) == 1
    assert finalized[0]["performed"] is False
    assert finalized[0]["error_code"].startswith(
        "presence_audio_delivery_error:"
    )


def test_unconfigured_internal_audio_push_is_fail_closed():
    pcm = b"\x01\x00"
    response = make_client().post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers=audio_push_headers(pcm),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "presence_audio_push_not_configured"
