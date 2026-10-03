import asyncio
import hashlib

import pytest

from empire_os.digital_avatar_presence_audio import (
    PresenceAudioBroker,
    PresenceAudioCommand,
)
from empire_os.digital_avatar_presence_token import AvatarPresenceClaims


def claims():
    return AvatarPresenceClaims(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        issued_at=1,
        expires_at=9999999999,
        nonce="nonce",
    )


class Socket:
    def __init__(self):
        self.messages = []
        self.broker = None
        self.session_id = None

    async def send_json(self, data):
        self.messages.append(data)
        if (
            data.get("type") == "speech.audio.end"
            and self.broker is not None
        ):
            accepted = self.broker.acknowledge(
                session_id=self.session_id,
                message={
                    "type": "speech.playback.completed",
                    "ticket_id": data["ticket_id"],
                    "audio_sha256": data["audio_sha256"],
                },
            )
            assert accepted is True


def command(pcm=b"\x01\x00\x02\x00"):
    return PresenceAudioCommand(
        ticket_id="avatar-speech:ticket-1",
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        audio_sha256=hashlib.sha256(pcm).hexdigest(),
        sample_rate=24000,
        pcm=pcm,
    )


def test_broker_pushes_only_server_command_and_waits_for_completion():
    async def run():
        broker = PresenceAudioBroker(chunk_bytes=1024)
        socket = Socket()
        socket.broker = broker
        socket.session_id = "browser-1"
        broker.attach(
            session_id="browser-1",
            claims=claims(),
            socket=socket,
        )

        result = await broker.push_pcm(command(), timeout_s=1)
        assert result.playback_completed is True
        assert result.execution_authority == "approved_turn_audio_only"
        assert result.commercial_execution_allowed is False
        types = [row["type"] for row in socket.messages]
        assert types == [
            "speech.audio.begin",
            "speech.audio.chunk",
            "speech.audio.end",
        ]
        assert socket.messages[0]["pcm_bytes"] == 4
        assert socket.messages[0]["sample_rate"] == 24000
        assert socket.messages[1]["b64"] == "AQACAA=="

    asyncio.run(run())


def test_broker_requires_exact_presence_identity():
    async def run():
        broker = PresenceAudioBroker()
        socket = Socket()
        broker.attach(
            session_id="browser-1",
            claims=claims(),
            socket=socket,
        )
        bad = PresenceAudioCommand(
            ticket_id="avatar-speech:ticket-1",
            meeting_id="meeting-999",
            avatar_id="avatar-phil-v1",
            bot_id="bot-123",
            audio_sha256=hashlib.sha256(b"\x00\x00").hexdigest(),
            sample_rate=24000,
            pcm=b"\x00\x00",
        )
        with pytest.raises(
            ValueError,
            match="presence browser is not connected",
        ):
            await broker.push_pcm(bad, timeout_s=1)
        assert socket.messages == []

    asyncio.run(run())


def test_browser_ack_with_wrong_hash_does_not_complete_ticket():
    async def run():
        broker = PresenceAudioBroker()
        socket = Socket()
        socket.session_id = "browser-1"
        broker.attach(
            session_id="browser-1",
            claims=claims(),
            socket=socket,
        )
        cmd = command()

        class WrongAckSocket(Socket):
            async def send_json(self, data):
                self.messages.append(data)
                if data.get("type") == "speech.audio.end":
                    accepted = broker.acknowledge(
                        session_id="browser-1",
                        message={
                            "type": "speech.playback.completed",
                            "ticket_id": data["ticket_id"],
                            "audio_sha256": "0" * 64,
                        },
                    )
                    assert accepted is False

        wrong = WrongAckSocket()
        broker.detach(session_id="browser-1")
        broker.attach(
            session_id="browser-1",
            claims=claims(),
            socket=wrong,
        )
        with pytest.raises(asyncio.TimeoutError):
            await broker.push_pcm(cmd, timeout_s=0.01)

    asyncio.run(run())


def test_duplicate_active_presence_identity_fails_closed():
    async def run():
        broker = PresenceAudioBroker()
        broker.attach(
            session_id="browser-1",
            claims=claims(),
            socket=Socket(),
        )
        broker.attach(
            session_id="browser-2",
            claims=claims(),
            socket=Socket(),
        )
        with pytest.raises(ValueError, match="ambiguous"):
            await broker.push_pcm(command(), timeout_s=1)

    asyncio.run(run())


@pytest.mark.parametrize(
    ("sample_rate", "pcm", "message"),
    [
        (4000, b"\x00\x00", "sample rate unsupported"),
        (24000, b"", "PCM required"),
        (24000, b"\x00", "int16 samples"),
    ],
)
def test_audio_command_validation_fails_closed(sample_rate, pcm, message):
    value = PresenceAudioCommand(
        ticket_id="ticket-1",
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        audio_sha256=hashlib.sha256(pcm).hexdigest(),
        sample_rate=sample_rate,
        pcm=pcm,
    )
    with pytest.raises(ValueError, match=message):
        value.validate(max_audio_bytes=1024)
