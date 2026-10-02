"""Private Recall SHADOW observations -> live guidance snapshot."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.digital_avatar_meeting_memory import build_avatar_meeting_memory
from empire_os.digital_avatar_response_task import (
    AvatarRealtimeResponseTask,
    build_realtime_response_task,
)
from empire_os.digital_avatar_shadow import (
    AvatarShadowGuidance,
    build_shadow_guidance,
)
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
    build_shadow_meeting_state,
)
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    load_recall_shadow_session,
)


@dataclass(frozen=True)
class RecallShadowGuidanceSnapshot:
    meeting_id: str
    avatar_id: str
    observation_count: int
    guidance: AvatarShadowGuidance
    response_task: AvatarRealtimeResponseTask | None
    mode: str = "OBSERVE"
    private_to_owner: bool = True
    speech_execution: bool = False
    persistence_is_canonical: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["guidance"] = self.guidance.as_dict()
        data["response_task"] = (
            self.response_task.as_dict()
            if self.response_task is not None
            else None
        )
        return data


def _observation(raw: Mapping[str, Any]) -> MeetingObservation:
    return MeetingObservation(
        meeting_id=str(raw["meeting_id"]),
        external_meeting_id=str(raw["external_meeting_id"]),
        platform=MeetingPlatform(raw["platform"]),
        provider_event_id=str(raw["provider_event_id"]),
        kind=MeetingObservationKind(raw["kind"]),
        occurred_at=str(raw["occurred_at"]),
        evidence_ref=str(raw["evidence_ref"]),
        speaker_ref=raw.get("speaker_ref"),
        speaker_name=raw.get("speaker_name"),
        speaker_role=MeetingSpeakerRole(
            raw.get("speaker_role") or MeetingSpeakerRole.UNKNOWN.value
        ),
        text=raw.get("text"),
        is_final=bool(raw.get("is_final", True)),
    )


def apply_manifest_roles(
    *,
    manifest: RecallShadowSessionManifest,
    observations: Iterable[MeetingObservation],
) -> tuple[MeetingObservation, ...]:
    roles = manifest.participant_roles or {}
    result = []
    for observation in observations:
        role = roles.get(str(observation.speaker_ref or ""))
        result.append(
            replace(observation, speaker_role=role)
            if role is not None
            else observation
        )
    return tuple(result)


def build_recall_shadow_guidance_snapshot(
    *,
    manifest: RecallShadowSessionManifest,
    observations: Iterable[MeetingObservation],
) -> RecallShadowGuidanceSnapshot:
    manifest.validate()
    bound = apply_manifest_roles(
        manifest=manifest,
        observations=observations,
    )
    state = build_shadow_meeting_state(
        session=manifest.session,
        observations=bound,
    )
    guidance = build_shadow_guidance(
        identity=manifest.identity,
        session=manifest.session,
        state=state,
        account_name=manifest.account_name,
        objective=manifest.objective,
        proof_refs=manifest.proof_refs,
        commercial_terms_ref=manifest.commercial_terms_ref,
        predictive_inputs=manifest.predictive_inputs,
        action_candidates=manifest.action_candidates,
    )

    response_task = None
    if state.latest_buyer_utterance is not None:
        memory = build_avatar_meeting_memory(
            session=manifest.session,
            observations=bound,
        )
        response_task = build_realtime_response_task(
            memory=memory,
            strategy=guidance.strategy,
        )

    return RecallShadowGuidanceSnapshot(
        meeting_id=manifest.session.meeting_id,
        avatar_id=manifest.identity.avatar_id,
        observation_count=state.observation_count,
        guidance=guidance,
        response_task=response_task,
    )


def refresh_recall_shadow_guidance(
    *,
    session_path: str | Path,
    observation_root: str | Path,
    output_path: str | Path,
) -> RecallShadowGuidanceSnapshot:
    manifest = load_recall_shadow_session(session_path)
    observations = []
    root = Path(observation_root)
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("meeting_id") != manifest.session.meeting_id:
                continue
            observations.append(_observation(raw["observation"]))

    snapshot = build_recall_shadow_guidance_snapshot(
        manifest=manifest,
        observations=observations,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700)
    tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(snapshot.as_dict(), sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        os.chmod(target, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()
    return snapshot
