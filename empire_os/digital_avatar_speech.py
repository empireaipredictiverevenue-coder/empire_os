"""Human-approved local speech-render tasks for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_copilot import AvatarCopilotHandoff


def _dt(value: str) -> datetime:
    raw = str(value or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("speech approval timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("speech approval timestamps must include timezone")
    return parsed.astimezone(timezone.utc)


def speech_text_sha256(text: str) -> str:
    return sha256(str(text or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AvatarHumanTurnApproval:
    meeting_id: str
    avatar_id: str
    approved_by: str
    approval_evidence_ref: str
    approved_at: str
    expires_at: str
    approved_text_sha256: str

    def validate(
        self,
        *,
        identity: DigitalAvatarIdentity,
        handoff: AvatarCopilotHandoff,
        now: datetime,
    ) -> None:
        if self.meeting_id != handoff.meeting_id:
            raise ValueError("speech approval meeting mismatch")
        if self.avatar_id != handoff.avatar_id:
            raise ValueError("speech approval avatar mismatch")
        if self.approved_by.strip() != identity.owner_name.strip():
            raise ValueError("speech approval owner mismatch")
        if not self.approval_evidence_ref.strip():
            raise ValueError("speech approval evidence required")
        approved = _dt(self.approved_at)
        expires = _dt(self.expires_at)
        current = now.astimezone(timezone.utc)
        if expires <= approved:
            raise ValueError("speech approval expiry invalid")
        if current < approved or current >= expires:
            raise ValueError("speech approval not active")
        if self.approved_text_sha256 != speech_text_sha256(handoff.draft_text):
            raise ValueError("speech approval text fingerprint mismatch")


@dataclass(frozen=True)
class AvatarSpeechRenderTask:
    meeting_id: str
    avatar_id: str
    owner_name: str
    text: str
    text_sha256: str
    purpose: str
    evidence_refs: tuple[str, ...]
    voice_profile_ref: str
    approval_evidence_ref: str
    local_audio_render_allowed: bool = True
    meeting_transmission_allowed: bool = False
    speech_execution_allowed: bool = False
    chat_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_avatar_speech_render_task(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    handoff: AvatarCopilotHandoff,
    approval: AvatarHumanTurnApproval,
    now: datetime | None = None,
) -> AvatarSpeechRenderTask:
    identity.validate()
    session.validate()

    if session.mode != AvatarMeetingMode.COPILOT:
        raise ValueError("approved speech render requires COPILOT mode")
    if session.avatar_id != identity.avatar_id:
        raise ValueError("speech render avatar/session identity mismatch")
    if handoff.meeting_id != session.meeting_id:
        raise ValueError("speech render handoff meeting mismatch")
    if handoff.avatar_id != identity.avatar_id:
        raise ValueError("speech render handoff avatar mismatch")
    if session.disclosure_announced is not True:
        raise ValueError("AI disclosure must be announced before speech rendering")
    if not handoff.ready_for_human_approval:
        raise ValueError("copilot handoff is not ready for human approval")
    if handoff.decision.human_takeover_required:
        raise ValueError("human takeover required; avatar speech blocked")
    if handoff.transmission_performed:
        raise ValueError("copilot handoff already transmitted")
    voice_profile_ref = str(identity.voice_profile_ref or "").strip()
    if not voice_profile_ref:
        raise ValueError("bound avatar voice profile required")

    current = now or datetime.now(timezone.utc)
    approval.validate(
        identity=identity,
        handoff=handoff,
        now=current,
    )

    return AvatarSpeechRenderTask(
        meeting_id=session.meeting_id,
        avatar_id=identity.avatar_id,
        owner_name=identity.owner_name,
        text=handoff.draft_text,
        text_sha256=speech_text_sha256(handoff.draft_text),
        purpose=handoff.purpose,
        evidence_refs=handoff.evidence_refs,
        voice_profile_ref=voice_profile_ref,
        approval_evidence_ref=approval.approval_evidence_ref,
    )
