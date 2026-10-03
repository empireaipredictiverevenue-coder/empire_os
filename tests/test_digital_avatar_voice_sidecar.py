from datetime import datetime, timezone
import hashlib

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_copilot import build_avatar_copilot_handoff
from empire_os.digital_avatar_speech import (
    AvatarHumanTurnApproval,
    build_avatar_speech_render_task,
    speech_text_sha256,
)
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
)
from empire_os.digital_avatar_voice_profile import (
    AvatarVoiceProfile,
    build_avatar_voice_render_plan,
)
from empire_os.digital_avatar_voice_sidecar import (
    AvatarVoiceSidecarConfig,
    build_voice_sidecar_request,
    render_voice_sidecar_pcm,
)


NOW = datetime(2026, 10, 2, 18, 30, tzinfo=timezone.utc)


def task_and_plan():
    identity = DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
        voice_profile_ref="voice:phil:v1",
    )
    session = AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=True,
    )
    draft = AvatarTurnDraft(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        purpose=AvatarTurnPurpose.ANSWER,
        text="Yes. I can show you the verified case evidence.",
        claims=(
            AvatarTurnClaim(
                text="Verified case evidence is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                evidence_refs=("evidence:case:7",),
            ),
        ),
        strategy_evidence_refs=("strategy:meeting-001:v1",),
    )
    handoff = build_avatar_copilot_handoff(
        identity=identity,
        session=session,
        draft=draft,
    )
    approval = AvatarHumanTurnApproval(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        approved_by="Phil Livesley",
        approval_evidence_ref="approval:speech:1",
        approved_at="2026-10-02T18:29:00+00:00",
        expires_at="2026-10-02T18:32:00+00:00",
        approved_text_sha256=speech_text_sha256(draft.text),
    )
    task = build_avatar_speech_render_task(
        identity=identity,
        session=session,
        handoff=handoff,
        approval=approval,
        now=NOW,
    )
    profile = AvatarVoiceProfile(
        profile_ref="voice:phil:v1",
        owner_consent_evidence_ref="consent:phil:voice-clone:v1",
        reference_audio_ref="voice-media:phil:clean-ref:v1",
        reference_transcript_ref="voice-transcript:phil:clean-ref:v1",
        engine_voice_id="phil-v1",
        clone_required=True,
        preferred_engine="cosyvoice3",
    )
    plan = build_avatar_voice_render_plan(
        task=task,
        profile=profile,
        available_engines={"cosyvoice3": True},
    )
    return task, plan


class FakeTransport:
    def __init__(self, *, status=200, content_type="audio/L16", chunks=None):
        self.status = status
        self.content_type = content_type
        self.chunks = list(chunks or [b"abc", b"def"])
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return (
            self.status,
            {"content-type": self.content_type},
            iter(self.chunks),
        )


def test_sidecar_request_sends_registered_voice_not_reference_media():
    task, plan = task_and_plan()
    request = build_voice_sidecar_request(task=task, plan=plan)
    payload = request.as_dict()
    assert payload["voice_id"] == "phil-v1"
    assert payload["text"] == task.text
    assert payload["text_sha256"] == task.text_sha256
    assert "reference_audio_ref" not in payload
    assert "reference_transcript_ref" not in payload
    assert "voice-media:phil" not in str(payload)
    assert "voice-transcript:phil" not in str(payload)
    assert request.render_id.startswith("avatar-voice:")


def test_https_sidecar_streams_pcm_without_meeting_transmission():
    task, plan = task_and_plan()
    request = build_voice_sidecar_request(task=task, plan=plan)
    transport = FakeTransport(chunks=[b"abc", b"def"])
    seen = []
    artifact = render_voice_sidecar_pcm(
        config=AvatarVoiceSidecarConfig(
            base_url="https://voice-gpu.internal.empire",
            auth_token="test-token",
        ),
        request=request,
        on_chunk=seen.append,
        transport=transport,
    )
    assert seen == [b"abc", b"def"]
    assert artifact.pcm_bytes == 6
    assert artifact.chunk_count == 2
    assert artifact.audio_sha256 == hashlib.sha256(b"abcdef").hexdigest()
    assert artifact.meeting_transmission_performed is False
    assert artifact.speech_execution_performed is False
    assert artifact.execution_authority == "none"

    call = transport.calls[0]
    assert call["url"] == "https://voice-gpu.internal.empire/v1/render"
    assert call["headers"]["Authorization"] == "Bearer test-token"
    assert call["payload"]["voice_id"] == "phil-v1"


def test_remote_http_sidecar_is_rejected_before_transport():
    task, plan = task_and_plan()
    request = build_voice_sidecar_request(task=task, plan=plan)
    transport = FakeTransport()
    with pytest.raises(ValueError, match="must use HTTPS"):
        render_voice_sidecar_pcm(
            config=AvatarVoiceSidecarConfig(
                base_url="http://voice-gpu.example.internal",
                auth_token="test-token",
            ),
            request=request,
            on_chunk=lambda _chunk: None,
            transport=transport,
        )
    assert transport.calls == []


def test_loopback_http_requires_explicit_dev_override():
    task, plan = task_and_plan()
    request = build_voice_sidecar_request(task=task, plan=plan)
    with pytest.raises(ValueError, match="must use HTTPS"):
        render_voice_sidecar_pcm(
            config=AvatarVoiceSidecarConfig(
                base_url="http://127.0.0.1:9988",
                auth_token="test-token",
            ),
            request=request,
            on_chunk=lambda _chunk: None,
            transport=FakeTransport(),
        )

    transport = FakeTransport()
    artifact = render_voice_sidecar_pcm(
        config=AvatarVoiceSidecarConfig(
            base_url="http://127.0.0.1:9988",
            auth_token="test-token",
            allow_loopback_http=True,
        ),
        request=request,
        on_chunk=lambda _chunk: None,
        transport=transport,
    )
    assert artifact.pcm_bytes == 6


def test_sidecar_rejects_non_audio_and_oversized_output():
    task, plan = task_and_plan()
    request = build_voice_sidecar_request(task=task, plan=plan)

    with pytest.raises(RuntimeError, match="non-audio"):
        render_voice_sidecar_pcm(
            config=AvatarVoiceSidecarConfig(
                base_url="https://voice-gpu.internal.empire",
                auth_token="test-token",
            ),
            request=request,
            on_chunk=lambda _chunk: None,
            transport=FakeTransport(content_type="application/json"),
        )

    with pytest.raises(RuntimeError, match="exceeds configured limit"):
        render_voice_sidecar_pcm(
            config=AvatarVoiceSidecarConfig(
                base_url="https://voice-gpu.internal.empire",
                auth_token="test-token",
                max_audio_bytes=5,
            ),
            request=request,
            on_chunk=lambda _chunk: None,
            transport=FakeTransport(chunks=[b"abcdef"]),
        )
