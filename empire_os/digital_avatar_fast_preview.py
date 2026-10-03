"""Low-latency private COPILOT preview from session-authenticated buyer text."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.digital_avatar_evidence_pack import (
    AvatarEvidenceResolver,
    build_avatar_evidence_pack,
)
from empire_os.digital_avatar_presence_transcript import (
    PresenceTranscriptObservation,
)
from empire_os.digital_avatar_response_draft import (
    AvatarResponseDraft,
    GroundedAvatarDraftProvider,
    generate_validated_grounded_avatar_response_draft,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_strategy import build_avatar_meeting_strategy
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
)
from empire_os.recall_shadow_session import RecallShadowSessionManifest


@dataclass(frozen=True)
class AvatarFastPreviewPacket:
    meeting_id: str
    avatar_id: str
    bot_id: str
    participant_ref: str | None
    observation_id: str
    task: AvatarRealtimeResponseTask
    draft: AvatarResponseDraft | None
    status: str
    unresolved_refs: tuple[str, ...]
    pending_signed_verification: bool = True
    private_to_owner: bool = True
    human_approval_required: bool = True
    speech_ready: bool = False
    transmission_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "task": self.task.as_dict(),
            "draft": self.draft.as_dict() if self.draft else None,
        }


def build_fast_preview_response_task(
    *,
    manifest: RecallShadowSessionManifest,
    observation: PresenceTranscriptObservation,
) -> AvatarRealtimeResponseTask:
    manifest.validate()
    if observation.meeting_id != manifest.session.meeting_id:
        raise ValueError("fast preview meeting/session mismatch")
    if observation.avatar_id != manifest.identity.avatar_id:
        raise ValueError("fast preview avatar/session mismatch")
    if observation.truth_class != "SESSION_OBSERVED":
        raise ValueError("fast preview requires session-observed transcript")
    if observation.canonical_evidence or observation.commercial_truth_allowed:
        raise ValueError("fast preview observation has forbidden truth authority")
    if not observation.text.strip():
        raise ValueError("fast preview buyer text required")

    strategy = build_avatar_meeting_strategy(
        identity=manifest.identity,
        session=manifest.session,
        account_name=manifest.account_name,
        objective=manifest.objective,
        buyer_signal_summary=None,
        buyer_signal_evidence_refs=(),
        proof_refs=manifest.proof_refs,
        commercial_terms_ref=manifest.commercial_terms_ref,
        predictive_inputs=manifest.predictive_inputs,
        action_candidates=manifest.action_candidates,
    )
    approved_refs = tuple(
        dict.fromkeys(
            str(ref or "").strip()
            for ref in (
                *manifest.proof_refs,
                manifest.commercial_terms_ref,
            )
            if str(ref or "").strip()
        )
    )
    action = strategy.next_best_action
    action_key = (
        str(action.get("action_key") or "").strip()
        if isinstance(action, Mapping)
        else ""
    ) or None

    constraints = (
        "Buyer utterance is session-authenticated low-latency context pending signed Recall verification.",
        "Do not cite the buyer utterance as verified evidence.",
        "Use only approved verified proof/terms evidence for factual business claims.",
        "Do not claim predicted revenue is actual revenue.",
        "Do not invent pricing, outcomes, integrations, capacity or timing.",
        "Return a private preview only; do not speak, send, accept terms, request payment or move funds.",
    )
    return AvatarRealtimeResponseTask(
        meeting_id=observation.meeting_id,
        avatar_id=observation.avatar_id,
        latest_buyer_utterance=observation.text,
        objective=manifest.objective,
        recommended_action_key=action_key,
        approved_evidence_refs=approved_refs,
        commercial_terms_ref=manifest.commercial_terms_ref,
        constraints=constraints,
        mode="COPILOT_FAST_PREVIEW",
        output_channel="private_fast_preview",
        requires_human_approval=True,
        speech_execution_allowed=False,
        execution_authority="none",
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def materialize_fast_private_preview(
    *,
    manifest: RecallShadowSessionManifest,
    observation: PresenceTranscriptObservation,
    evidence_resolver: AvatarEvidenceResolver,
    provider: GroundedAvatarDraftProvider,
    output_root: str | Path,
) -> AvatarFastPreviewPacket:
    task = build_fast_preview_response_task(
        manifest=manifest,
        observation=observation,
    )
    pack = build_avatar_evidence_pack(
        task=task,
        resolver=evidence_resolver,
    )
    digest_payload = {
        "observation_id": observation.observation_id,
        "task": task.as_dict(),
        "evidence_pack": pack.as_dict(),
    }
    digest = sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    root = Path(output_root) / task.meeting_id
    target = root / f"{digest}.json"
    latest = root / "latest.json"
    if target.is_file():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("fast preview artifact unreadable") from exc
        return AvatarFastPreviewPacket(
            meeting_id=task.meeting_id,
            avatar_id=task.avatar_id,
            bot_id=observation.bot_id,
            participant_ref=observation.participant_ref,
            observation_id=observation.observation_id,
            task=task,
            draft=None,
            status=str(raw.get("status") or "existing"),
            unresolved_refs=tuple(raw.get("unresolved_refs") or ()),
        )

    if not pack.ready_for_drafting:
        result = AvatarFastPreviewPacket(
            meeting_id=task.meeting_id,
            avatar_id=task.avatar_id,
            bot_id=observation.bot_id,
            participant_ref=observation.participant_ref,
            observation_id=observation.observation_id,
            task=task,
            draft=None,
            status="blocked_evidence",
            unresolved_refs=pack.unresolved_refs,
        )
        _atomic_json(target, result.as_dict())
        _atomic_json(latest, result.as_dict())
        return result

    draft = generate_validated_grounded_avatar_response_draft(
        task=task,
        evidence_pack=pack,
        provider=provider,
        source_ref=(
            f"avatar-fast-preview:{task.meeting_id}:"
            f"{observation.observation_id.split(':')[-1][:24]}"
        ),
    )
    result = AvatarFastPreviewPacket(
        meeting_id=task.meeting_id,
        avatar_id=task.avatar_id,
        bot_id=observation.bot_id,
        participant_ref=observation.participant_ref,
        observation_id=observation.observation_id,
        task=task,
        draft=draft,
        status=(
            "preview_ready_pending_verification"
            if draft.ready_for_human_review
            else "blocked_validation"
        ),
        unresolved_refs=(),
    )
    _atomic_json(target, result.as_dict())
    _atomic_json(latest, result.as_dict())
    return result


@dataclass(frozen=True)
class AvatarFastPreviewVerification:
    meeting_id: str
    avatar_id: str
    bot_id: str
    fast_observation_id: str
    verified_provider_event_id: str
    verified_evidence_ref: str
    signed_verification_matched: bool
    eligible_for_human_review: bool
    eligible_for_speech_approval: bool
    speech_execution_allowed: bool = False
    transmission_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def verify_fast_preview_against_signed_observation(
    *,
    preview: AvatarFastPreviewPacket,
    verified_observation: MeetingObservation,
) -> AvatarFastPreviewVerification:
    verified_observation.validate()
    if verified_observation.kind != MeetingObservationKind.TRANSCRIPT_TURN:
        raise ValueError("fast preview verification requires transcript turn")
    if verified_observation.is_final is not True:
        raise ValueError("fast preview verification requires final transcript")
    if verified_observation.meeting_id != preview.meeting_id:
        raise ValueError("fast preview signed meeting mismatch")
    if verified_observation.external_meeting_id != preview.bot_id:
        raise ValueError("fast preview signed bot mismatch")
    if (
        preview.participant_ref is not None
        and verified_observation.speaker_ref != preview.participant_ref
    ):
        raise ValueError("fast preview signed participant mismatch")
    if _normalized_text(verified_observation.text) != _normalized_text(
        preview.task.latest_buyer_utterance
    ):
        raise ValueError("fast preview signed transcript text mismatch")
    if not str(verified_observation.evidence_ref or "").startswith("recall:"):
        raise ValueError("fast preview signed evidence ref invalid")
    if preview.pending_signed_verification is not True:
        raise ValueError("fast preview does not require signed verification")

    draft_ready = bool(
        preview.draft is not None
        and preview.draft.ready_for_human_review
        and preview.status == "preview_ready_pending_verification"
    )
    return AvatarFastPreviewVerification(
        meeting_id=preview.meeting_id,
        avatar_id=preview.avatar_id,
        bot_id=preview.bot_id,
        fast_observation_id=preview.observation_id,
        verified_provider_event_id=verified_observation.provider_event_id,
        verified_evidence_ref=verified_observation.evidence_ref,
        signed_verification_matched=True,
        eligible_for_human_review=draft_ready,
        eligible_for_speech_approval=draft_ready,
    )
