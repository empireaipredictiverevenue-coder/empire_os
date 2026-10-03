from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_speech import (
    AvatarHumanTurnApproval,
    AvatarSpeechRenderTask,
)
from empire_os.digital_avatar_speech_transmission import (
    authorize_avatar_speech_transmission,
    claim_speech_transmission_ticket,
    finalize_inflight_speech_transmission_record,
    materialize_speech_transmission_ticket,
    validate_inflight_speech_transmission_record,
)
from empire_os.digital_avatar_voice_sidecar import AvatarVoiceRenderArtifact


NOW = datetime(2026, 10, 2, 19, 30, tzinfo=timezone.utc)


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


def task():
    return AvatarSpeechRenderTask(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        text="Yes. I can show you the verified case evidence.",
        text_sha256="text-hash-1",
        purpose="answer",
        evidence_refs=("evidence:case:7",),
        voice_profile_ref="voice:phil:v1",
        approval_evidence_ref="approval:speech:turn-1",
    )


def artifact(**overrides):
    values = {
        "render_id": "avatar-voice:render-1",
        "engine": "cosyvoice3",
        "voice_id": "phil-v1",
        "text_sha256": "text-hash-1",
        "audio_sha256": "audio-hash-1",
        "pcm_bytes": 48000,
        "sample_rate": 24000,
        "chunk_count": 12,
    }
    values.update(overrides)
    return AvatarVoiceRenderArtifact(**values)


def approval(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "approved_by": "Phil Livesley",
        "approval_evidence_ref": "approval:speech:turn-1",
        "approved_at": "2026-10-02T19:29:00+00:00",
        "expires_at": "2026-10-02T19:32:00+00:00",
        "approved_text_sha256": "text-hash-1",
    }
    values.update(overrides)
    return AvatarHumanTurnApproval(**values)


def presence_state(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "presence_active": True,
        "output_media_start_performed": True,
        "speech_execution_allowed": False,
        "commercial_execution_allowed": False,
        "execution_authority": "copilot_presence_start_only",
    }
    values.update(overrides)
    return values


def test_exact_rendered_turn_becomes_one_time_transmission_ticket():
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    assert ticket.meeting_id == "meeting-001"
    assert ticket.bot_id == "bot-123"
    assert ticket.text_sha256 == "text-hash-1"
    assert ticket.audio_sha256 == "audio-hash-1"
    assert ticket.one_time is True
    assert ticket.speech_transmission_allowed is True
    assert ticket.commercial_execution_allowed is False
    assert ticket.execution_authority == "approved_turn_audio_only"


def test_transmission_rejects_rendered_audio_for_different_text():
    with pytest.raises(ValueError, match="render artifact text fingerprint mismatch"):
        authorize_avatar_speech_transmission(
            identity=identity(),
            task=task(),
            artifact=artifact(text_sha256="different-text"),
            approval=approval(),
            presence_state=presence_state(),
            now=NOW,
        )


def test_transmission_requires_active_presence():
    with pytest.raises(ValueError, match="presence is not active"):
        authorize_avatar_speech_transmission(
            identity=identity(),
            task=task(),
            artifact=artifact(),
            approval=approval(),
            presence_state=presence_state(presence_active=False),
            now=NOW,
        )


def test_transmission_rechecks_human_approval_expiry():
    with pytest.raises(ValueError, match="speech approval not active"):
        authorize_avatar_speech_transmission(
            identity=identity(),
            task=task(),
            artifact=artifact(),
            approval=approval(
                approved_at="2026-10-02T19:00:00+00:00",
                expires_at="2026-10-02T19:10:00+00:00",
            ),
            presence_state=presence_state(),
            now=NOW,
        )


def test_ticket_materialization_stores_hashes_not_raw_audio(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    record = json.loads(path.read_text())
    assert record["audio_sha256"] == "audio-hash-1"
    assert record["raw_audio_persisted"] is False
    assert record["state"] == "authorized"
    assert record["consumed"] is False
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_ticket_can_be_claimed_only_once(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    first = claim_speech_transmission_ticket(
        path=path,
        ticket=ticket,
        now=NOW,
    )
    assert first["state"] == "in_flight"
    assert first["consumed"] is True
    with pytest.raises(ValueError, match="already claimed"):
        claim_speech_transmission_ticket(
            path=path,
            ticket=ticket,
            now=NOW,
        )


def test_claim_lock_blocks_concurrent_sender(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    lock = path.parent / f".{path.name}.claim.lock"
    lock.write_text("other-sender")
    with pytest.raises(ValueError, match="claim already in progress"):
        claim_speech_transmission_ticket(
            path=path,
            ticket=ticket,
            now=NOW,
        )
    record = json.loads(path.read_text())
    assert record["state"] == "authorized"
    assert record["consumed"] is False


def test_expired_ticket_cannot_be_claimed(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    with pytest.raises(ValueError, match="ticket expired"):
        claim_speech_transmission_ticket(
            path=path,
            ticket=ticket,
            now=NOW + timedelta(minutes=3),
        )


def test_completed_ticket_cannot_be_replayed(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    claim_speech_transmission_ticket(path=path, ticket=ticket, now=NOW)
    from empire_os.digital_avatar_speech_transmission import (
        finalize_speech_transmission_ticket,
    )
    final = finalize_speech_transmission_ticket(
        path=path,
        ticket=ticket,
        performed=True,
        now=NOW,
    )
    assert final["state"] == "completed"
    assert final["speech_transmission_performed"] is True
    with pytest.raises(ValueError, match="already claimed"):
        claim_speech_transmission_ticket(
            path=path,
            ticket=ticket,
            now=NOW,
        )


def test_ambiguous_transmission_never_returns_to_authorized(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    claim_speech_transmission_ticket(path=path, ticket=ticket, now=NOW)
    from empire_os.digital_avatar_speech_transmission import (
        finalize_speech_transmission_ticket,
    )
    final = finalize_speech_transmission_ticket(
        path=path,
        ticket=ticket,
        performed=False,
        now=NOW,
        error_code="presence_channel_timeout",
    )
    assert final["state"] == "reconciliation_required"
    assert final["speech_transmission_performed"] is False
    assert final["error_code"] == "presence_channel_timeout"
    with pytest.raises(ValueError, match="already claimed"):
        claim_speech_transmission_ticket(
            path=path,
            ticket=ticket,
            now=NOW,
        )


def claimed_ticket_record(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    claim_speech_transmission_ticket(
        path=path,
        ticket=ticket,
        now=NOW,
    )
    return ticket, path


def test_inflight_ticket_record_validates_exact_audio_binding(tmp_path):
    ticket, path = claimed_ticket_record(tmp_path)
    record = validate_inflight_speech_transmission_record(
        path=path,
        ticket_id=ticket.ticket_id,
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        audio_sha256="audio-hash-1",
        pcm_bytes=48000,
        sample_rate=24000,
        now=NOW,
    )
    assert record["state"] == "in_flight"
    assert record["consumed"] is True
    assert record["execution_authority"] == "approved_turn_audio_only"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("meeting_id", "meeting-999", "meeting mismatch"),
        ("avatar_id", "avatar-other", "avatar mismatch"),
        ("bot_id", "bot-other", "bot mismatch"),
        ("audio_sha256", "wrong-hash", "audio mismatch"),
        ("pcm_bytes", 1, "pcm size mismatch"),
        ("sample_rate", 16000, "sample rate mismatch"),
    ],
)
def test_inflight_ticket_rejects_mismatched_audio_binding(
    tmp_path,
    key,
    value,
    message,
):
    ticket, path = claimed_ticket_record(tmp_path)
    kwargs = {
        "path": path,
        "ticket_id": ticket.ticket_id,
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "audio_sha256": "audio-hash-1",
        "pcm_bytes": 48000,
        "sample_rate": 24000,
        "now": NOW,
    }
    kwargs[key] = value
    with pytest.raises(ValueError, match=message):
        validate_inflight_speech_transmission_record(**kwargs)


def test_authorized_but_unclaimed_ticket_cannot_reach_presence(tmp_path):
    ticket = authorize_avatar_speech_transmission(
        identity=identity(),
        task=task(),
        artifact=artifact(),
        approval=approval(),
        presence_state=presence_state(),
        now=NOW,
    )
    path = materialize_speech_transmission_ticket(
        root=tmp_path / "tickets",
        ticket=ticket,
    )
    with pytest.raises(ValueError, match="not in flight"):
        validate_inflight_speech_transmission_record(
            path=path,
            ticket_id=ticket.ticket_id,
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            bot_id="bot-123",
            audio_sha256="audio-hash-1",
            pcm_bytes=48000,
            sample_rate=24000,
            now=NOW,
        )


def test_record_finalizer_completes_only_inflight_ticket(tmp_path):
    ticket, path = claimed_ticket_record(tmp_path)
    final = finalize_inflight_speech_transmission_record(
        path=path,
        ticket_id=ticket.ticket_id,
        performed=True,
        now=NOW,
    )
    assert final["state"] == "completed"
    assert final["speech_transmission_performed"] is True
    assert final["error_code"] is None


def test_record_finalizer_marks_ambiguous_delivery_for_reconciliation(tmp_path):
    ticket, path = claimed_ticket_record(tmp_path)
    final = finalize_inflight_speech_transmission_record(
        path=path,
        ticket_id=ticket.ticket_id,
        performed=False,
        now=NOW,
        error_code="presence_playback_timeout",
    )
    assert final["state"] == "reconciliation_required"
    assert final["speech_transmission_performed"] is False
    assert final["error_code"] == "presence_playback_timeout"
