from datetime import datetime, timezone
import json

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_approved_turn_executor import (
    PresenceAudioPushConfig,
    execute_approved_avatar_turn,
)
from empire_os.digital_avatar_copilot import build_avatar_copilot_handoff
from empire_os.digital_avatar_speech import (
    AvatarHumanTurnApproval,
    speech_text_sha256,
)
from empire_os.digital_avatar_speech_transmission import (
    finalize_inflight_speech_transmission_record,
)
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
)
from empire_os.digital_avatar_voice_profile import AvatarVoiceProfile
from empire_os.digital_avatar_voice_sidecar import AvatarVoiceSidecarConfig


NOW = datetime(2026, 10, 2, 20, 30, tzinfo=timezone.utc)
PUSH_SECRET = "approved-turn-push-" + ("z" * 32)


def identity():
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
        voice_profile_ref="voice:phil:v1",
        visual_profile_ref="visual:phil:v1",
    )


def session():
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=True,
    )


def handoff():
    draft = AvatarTurnDraft(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        purpose=AvatarTurnPurpose.ANSWER,
        text="Yes. I can show you the verified case evidence.",
        claims=(
            AvatarTurnClaim(
                text="Verified case evidence is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                evidence_refs=("canonical:commercial_outcomes:proof-1",),
            ),
        ),
        strategy_evidence_refs=("strategy:meeting-001:v1",),
    )
    return build_avatar_copilot_handoff(
        identity=identity(),
        session=session(),
        draft=draft,
    )


def approval(**overrides):
    value = handoff()
    fields = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "approved_by": "Phil Livesley",
        "approval_evidence_ref": "approval:speech:meeting-001:turn-1",
        "approved_at": "2026-10-02T20:29:00+00:00",
        "expires_at": "2026-10-02T20:32:00+00:00",
        "approved_text_sha256": speech_text_sha256(value.draft_text),
    }
    fields.update(overrides)
    return AvatarHumanTurnApproval(**fields)


def profile():
    return AvatarVoiceProfile(
        profile_ref="voice:phil:v1",
        owner_consent_evidence_ref="consent:phil:voice-clone:v1",
        reference_audio_ref="voice-media:phil:clean-ref:v1",
        reference_transcript_ref="voice-transcript:phil:clean-ref:v1",
        engine_voice_id="phil-v1",
        clone_required=True,
        preferred_engine="cosyvoice3",
    )


def presence_state():
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "presence_active": True,
        "output_media_start_performed": True,
        "speech_execution_allowed": False,
        "commercial_execution_allowed": False,
        "execution_authority": "copilot_presence_start_only",
    }


class VoiceTransport:
    def __init__(self):
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return (
            200,
            {"content-type": "audio/L16"},
            iter([b"\x01\x00", b"\x02\x00"]),
        )


def push_config():
    return PresenceAudioPushConfig(
        url="http://127.0.0.1:8100/internal/avatar/presence/audio",
        secret=PUSH_SECRET,
        timeout_s=2,
    )


class CompletingPresenceTransport:
    def __init__(self, ticket_root):
        self.ticket_root = ticket_root
        self.calls = []

    def post_pcm(self, *, url, headers, body, timeout_s):
        self.calls.append((url, headers, body, timeout_s))
        ticket_id = headers["X-Empire-Ticket-Id"]
        path = (
            self.ticket_root
            / f"{ticket_id.replace(':', '__')}.json"
        )
        finalized = finalize_inflight_speech_transmission_record(
            path=path,
            ticket_id=ticket_id,
            performed=True,
            now=NOW,
        )
        return 200, {
            "ticket_id": ticket_id,
            "meeting_id": headers["X-Empire-Meeting-Id"],
            "avatar_id": headers["X-Empire-Avatar-Id"],
            "bot_id": headers["X-Empire-Bot-Id"],
            "audio_sha256": headers["X-Empire-Audio-Sha256"],
            "pcm_bytes": len(body),
            "sample_rate": int(headers["X-Empire-Sample-Rate"]),
            "browser_playback_completed": True,
            "speech_transmission_performed": True,
            "meeting_audio_delivery_verified": False,
            "ticket_state": finalized["state"],
            "raw_audio_persisted": False,
        }


class FailingPresenceTransport:
    def __init__(self):
        self.calls = 0

    def post_pcm(self, **kwargs):
        self.calls += 1
        raise TimeoutError("loopback timeout")


def execute(tmp_path, *, approval_value=None, presence_transport=None):
    voice = VoiceTransport()
    value = execute_approved_avatar_turn(
        identity=identity(),
        session=session(),
        handoff=handoff(),
        approval=approval_value or approval(),
        voice_profile=profile(),
        voice_sidecar_config=AvatarVoiceSidecarConfig(
            base_url="https://voice-gpu.internal.empire",
            auth_token="test-voice-sidecar-token",
        ),
        presence_state=presence_state(),
        speech_ticket_root=tmp_path / "tickets",
        presence_push=push_config(),
        available_voice_engines={"cosyvoice3": True},
        now=NOW,
        voice_transport=voice,
        presence_transport=presence_transport,
    )
    return value, voice


def test_approved_turn_renders_claims_and_completes_once(tmp_path):
    presence = CompletingPresenceTransport(tmp_path / "tickets")
    result, voice = execute(
        tmp_path,
        presence_transport=presence,
    )
    assert result.state == "completed"
    assert result.browser_playback_completed is True
    assert result.speech_transmission_performed is True
    assert result.meeting_audio_delivery_verified is False
    assert result.raw_audio_persisted is False
    assert result.autonomous_speech_execution is False
    assert result.commercial_execution is False
    assert result.payment_execution is False
    assert result.execution_authority == "approved_turn_audio_only"
    assert len(voice.calls) == 1
    assert len(presence.calls) == 1

    ticket_path = (
        tmp_path
        / "tickets"
        / f"{result.ticket_id.replace(':', '__')}.json"
    )
    record = json.loads(ticket_path.read_text())
    assert record["state"] == "completed"
    assert record["consumed"] is True
    assert record["speech_transmission_performed"] is True
    assert record["raw_audio_persisted"] is False


def test_transport_timeout_burns_ticket_for_reconciliation(tmp_path):
    failing = FailingPresenceTransport()
    result, _voice = execute(
        tmp_path,
        presence_transport=failing,
    )
    assert result.state == "reconciliation_required"
    assert result.speech_transmission_performed is False
    assert result.browser_playback_completed is False
    assert failing.calls == 1

    ticket_path = (
        tmp_path
        / "tickets"
        / f"{result.ticket_id.replace(':', '__')}.json"
    )
    record = json.loads(ticket_path.read_text())
    assert record["state"] == "reconciliation_required"
    assert record["consumed"] is True

    with pytest.raises(ValueError, match="already claimed"):
        execute(
            tmp_path,
            presence_transport=CompletingPresenceTransport(
                tmp_path / "tickets"
            ),
        )


def test_expired_owner_approval_blocks_before_voice_render(tmp_path):
    voice = VoiceTransport()
    expired = approval(
        approved_at="2026-10-02T20:00:00+00:00",
        expires_at="2026-10-02T20:10:00+00:00",
    )
    with pytest.raises(ValueError, match="speech approval not active"):
        execute_approved_avatar_turn(
            identity=identity(),
            session=session(),
            handoff=handoff(),
            approval=expired,
            voice_profile=profile(),
            voice_sidecar_config=AvatarVoiceSidecarConfig(
                base_url="https://voice-gpu.internal.empire",
                auth_token="test-voice-sidecar-token",
            ),
            presence_state=presence_state(),
            speech_ticket_root=tmp_path / "tickets",
            presence_push=push_config(),
            available_voice_engines={"cosyvoice3": True},
            now=NOW,
            voice_transport=voice,
            presence_transport=CompletingPresenceTransport(
                tmp_path / "tickets"
            ),
        )
    assert voice.calls == []


def test_presence_push_is_loopback_only():
    with pytest.raises(ValueError, match="loopback-only"):
        PresenceAudioPushConfig(
            url="https://empire-ai.co.uk/internal/avatar/presence/audio",
            secret=PUSH_SECRET,
        ).validate()
