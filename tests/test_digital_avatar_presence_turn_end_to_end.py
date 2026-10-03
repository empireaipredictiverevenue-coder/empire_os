import hashlib
import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from empire_os.digital_avatar_presence_api import (
    PresenceBrowserRegistry,
    create_digital_avatar_presence_app,
)
from empire_os.digital_avatar_presence_audio import PresenceAudioBroker
from empire_os.digital_avatar_presence_token import AvatarPresenceClaims
from empire_os.digital_avatar_speech_transmission import (
    AvatarSpeechTransmissionTicket,
    claim_speech_transmission_ticket,
    finalize_inflight_speech_transmission_record,
    materialize_speech_transmission_ticket,
    validate_inflight_speech_transmission_record,
)


NOW = datetime(2026, 10, 2, 20, 30, tzinfo=timezone.utc)
PRESENCE_SECRET = "presence-secret-" + ("x" * 32)
PUSH_SECRET = "presence-push-" + ("y" * 32)


def ticket_for(pcm):
    return AvatarSpeechTransmissionTicket(
        ticket_id="avatar-speech:" + ("a" * 64),
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        render_id="render-001",
        text_sha256="b" * 64,
        audio_sha256=hashlib.sha256(pcm).hexdigest(),
        approval_evidence_ref="approval:speech:meeting-001:turn-1",
        approved_by="Phil Livesley",
        expires_at="2026-10-02T20:35:00+00:00",
        pcm_bytes=len(pcm),
        sample_rate=24000,
    )


def claims():
    epoch = int(NOW.timestamp())
    return AvatarPresenceClaims(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        issued_at=epoch,
        expires_at=epoch + 300,
        nonce="approved-turn-e2e",
    )


def headers(ticket):
    return {
        "authorization": "Bearer " + PUSH_SECRET,
        "content-type": "application/octet-stream",
        "x-empire-ticket-id": ticket.ticket_id,
        "x-empire-meeting-id": ticket.meeting_id,
        "x-empire-avatar-id": ticket.avatar_id,
        "x-empire-bot-id": ticket.bot_id,
        "x-empire-audio-sha256": ticket.audio_sha256,
        "x-empire-sample-rate": str(ticket.sample_rate),
    }


class CompletingBrowserSocket:
    def __init__(self, broker):
        self.broker = broker
        self.messages = []

    async def send_json(self, data):
        self.messages.append(data)
        if data.get("type") == "speech.audio.end":
            accepted = self.broker.acknowledge(
                session_id="browser-1",
                message={
                    "type": "speech.playback.completed",
                    "ticket_id": data["ticket_id"],
                    "audio_sha256": data["audio_sha256"],
                },
            )
            assert accepted is True


def app_for(tmp_path, broker):
    root = tmp_path / "tickets"

    def ticket_path(ticket_id):
        return root / f"{ticket_id.replace(':', '__')}.json"

    def validator(**kwargs):
        ticket_id = kwargs.pop("ticket_id")
        return validate_inflight_speech_transmission_record(
            path=ticket_path(ticket_id),
            ticket_id=ticket_id,
            **kwargs,
        )

    def finalizer(**kwargs):
        ticket_id = kwargs.pop("ticket_id")
        return finalize_inflight_speech_transmission_record(
            path=ticket_path(ticket_id),
            ticket_id=ticket_id,
            **kwargs,
        )

    return create_digital_avatar_presence_app(
        secret_provider=lambda: PRESENCE_SECRET,
        registry=PresenceBrowserRegistry(),
        now_provider=lambda: NOW,
        audio_push_secret_provider=lambda: PUSH_SECRET,
        speech_ticket_validator=validator,
        speech_ticket_finalizer=finalizer,
        audio_broker=broker,
        audio_push_timeout_s=2.0,
    )


def test_claimed_ticket_flows_http_through_real_broker_and_finishes_once(tmp_path):
    pcm = b"\x01\x00\x02\x00" * 64
    ticket = ticket_for(pcm)
    root = tmp_path / "tickets"
    path = materialize_speech_transmission_ticket(
        root=root,
        ticket=ticket,
    )
    claim_speech_transmission_ticket(
        path=path,
        ticket=ticket,
        now=NOW,
    )

    broker = PresenceAudioBroker(chunk_bytes=1024)
    browser = CompletingBrowserSocket(broker)
    broker.attach(
        session_id="browser-1",
        claims=claims(),
        socket=browser,
    )
    client = TestClient(
        app_for(tmp_path, broker),
        base_url="https://presence.empire.test",
    )

    response = client.post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers=headers(ticket),
    )


    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == ticket.ticket_id
    assert body["audio_sha256"] == ticket.audio_sha256
    assert body["browser_playback_completed"] is True
    assert body["speech_transmission_performed"] is True
    assert body["meeting_audio_delivery_verified"] is False
    assert body["ticket_state"] == "completed"
    assert body["commercial_execution_allowed"] is False
    assert body["execution_authority"] == "approved_turn_audio_only"

    types = [message["type"] for message in browser.messages]
    assert types == [
        "speech.audio.begin",
        "speech.audio.chunk",
        "speech.audio.end",
    ]

    record = json.loads(path.read_text())
    assert record["state"] == "completed"
    assert record["consumed"] is True
    assert record["speech_transmission_performed"] is True

    replay = client.post(
        "/internal/avatar/presence/audio",
        content=pcm,
        headers=headers(ticket),
    )
    assert replay.status_code == 409
    assert "not in flight" in replay.json()["detail"]
