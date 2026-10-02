"""Grounded realtime response-task contract for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar_meeting_memory import AvatarMeetingMemory
from empire_os.digital_avatar_strategy import AvatarMeetingStrategyPacket


@dataclass(frozen=True)
class AvatarRealtimeResponseTask:
    meeting_id: str
    avatar_id: str
    latest_buyer_utterance: str
    objective: str
    recommended_action_key: str | None
    approved_evidence_refs: tuple[str, ...]
    commercial_terms_ref: str | None
    constraints: tuple[str, ...]
    mode: str = "COPILOT_PREVIEW"
    output_channel: str = "private_draft"
    requires_human_approval: bool = True
    speech_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_realtime_response_task(
    *,
    memory: AvatarMeetingMemory,
    strategy: AvatarMeetingStrategyPacket,
    additional_evidence_refs: Sequence[str] = (),
) -> AvatarRealtimeResponseTask:
    if memory.meeting_id != strategy.meeting_id:
        raise ValueError("meeting memory/strategy identity mismatch")
    if memory.avatar_id != strategy.avatar_id:
        raise ValueError("avatar memory/strategy identity mismatch")
    latest = memory.latest_buyer_utterance
    if not isinstance(latest, Mapping):
        raise ValueError("observed buyer utterance required")
    utterance = str(latest.get("text") or "").strip()
    utterance_ref = str(latest.get("evidence_ref") or "").strip()
    if not utterance or not utterance_ref:
        raise ValueError("buyer utterance text and evidence required")

    action = strategy.next_best_action
    action_key = (
        str(action.get("action_key") or "").strip()
        if isinstance(action, Mapping)
        else ""
    ) or None

    refs = tuple(
        dict.fromkeys(
            str(ref or "").strip()
            for ref in (
                utterance_ref,
                *strategy.proof_refs,
                *additional_evidence_refs,
            )
            if str(ref or "").strip()
        )
    )


    constraints = (
        "Use only the supplied observed or verified evidence.",
        "Do not claim predicted revenue is actual revenue.",
        "Do not invent pricing, customer results, integrations, capacity or timing.",
        "Do not accept legal terms, request payment or move funds.",
        "Keep forecasts explicitly labelled as forecasts.",
        "Return a private draft for human approval; do not speak or send.",
    )

    return AvatarRealtimeResponseTask(
        meeting_id=memory.meeting_id,
        avatar_id=memory.avatar_id,
        latest_buyer_utterance=utterance,
        objective=strategy.objective,
        recommended_action_key=action_key,
        approved_evidence_refs=refs,
        commercial_terms_ref=strategy.commercial_terms_ref,
        constraints=constraints,
    )
