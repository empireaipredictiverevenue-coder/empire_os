"""Grounded internal specialist advisory generation for Digital Avatar."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol

from empire_os.digital_avatar_evidence_pack import AvatarEvidencePack
from empire_os.digital_avatar_meeting_specialist_bridge import (
    AvatarMeetingAdvisoryPacket,
    AvatarSpecialistAdvisory,
    build_avatar_meeting_advisory_packet,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_specialist_consultation import (
    AvatarSpecialistConsultationLane,
    AvatarSpecialistConsultationPlan,
)
from empire_os.digital_avatar_turn import AvatarClaimTruth


class AvatarSpecialistInferenceProvider(Protocol):
    provider_key: str

    def generate(
        self,
        *,
        lane: AvatarSpecialistConsultationLane,
        task: AvatarRealtimeResponseTask,
        evidence_pack: AvatarEvidencePack,
    ) -> Mapping[str, Any]:
        ...


def _clean_refs(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(
        str(item or "").strip()
        for item in value
        if str(item or "").strip()
    ))


def _unavailable(
    *,
    lane: AvatarSpecialistConsultationLane,
    blocker: str,
) -> AvatarSpecialistAdvisory:
    return AvatarSpecialistAdvisory(
        domain=lane.domain,
        source_component=f"department:{lane.department_key}",
        summary="",
        truth_class=AvatarClaimTruth.INFERRED,
        evidence_refs=(),
        available=False,
        blockers=(blocker,),
    )
def _validated_advisory(
    *,
    lane: AvatarSpecialistConsultationLane,
    payload: Mapping[str, Any],
    approved_refs: frozenset[str],
) -> AvatarSpecialistAdvisory:
    summary = " ".join(str(payload.get("summary") or "").split())
    if not summary:
        return _unavailable(
            lane=lane,
            blocker="specialist_summary_missing",
        )

    truth_raw = str(payload.get("truth_class") or "").strip().upper()
    try:
        truth = AvatarClaimTruth(truth_raw)
    except ValueError:
        return _unavailable(
            lane=lane,
            blocker="specialist_truth_class_invalid",
        )
    if truth not in {
        AvatarClaimTruth.INFERRED,
        AvatarClaimTruth.FORECAST,
    }:
        return _unavailable(
            lane=lane,
            blocker="specialist_generated_truth_must_be_inferred_or_forecast",
        )

    refs = _clean_refs(payload.get("evidence_refs"))
    if not refs:
        return _unavailable(
            lane=lane,
            blocker="specialist_evidence_missing",
        )
    if any(ref not in approved_refs for ref in refs):
        return _unavailable(
            lane=lane,
            blocker="specialist_uses_unapproved_evidence",
        )

    return AvatarSpecialistAdvisory(
        domain=lane.domain,
        source_component=f"department:{lane.department_key}",
        summary=summary,
        truth_class=truth,
        evidence_refs=refs,
    )


def generate_grounded_specialist_advisory_packet(
    *,
    plan: AvatarSpecialistConsultationPlan,
    task: AvatarRealtimeResponseTask,
    evidence_pack: AvatarEvidencePack,
    provider: AvatarSpecialistInferenceProvider,
) -> AvatarMeetingAdvisoryPacket:
    if plan.meeting_id != task.meeting_id:
        raise ValueError("specialist plan/task meeting identity mismatch")
    if plan.avatar_id != task.avatar_id:
        raise ValueError("specialist plan/task avatar identity mismatch")
    if evidence_pack.meeting_id != task.meeting_id:
        raise ValueError("specialist evidence/task meeting identity mismatch")
    if evidence_pack.avatar_id != task.avatar_id:
        raise ValueError("specialist evidence/task avatar identity mismatch")
    if plan.read_only is not True or plan.private_to_owner is not True:
        raise ValueError("specialist consultation privacy/read invariant violated")
    if (
        plan.department_work_enqueued
        or plan.external_execution_performed
        or plan.speech_execution_allowed
        or plan.commercial_execution_allowed
        or plan.payment_execution_allowed
        or plan.revenue_recognition_allowed
        or plan.execution_authority != "none"
    ):
        raise ValueError("specialist consultation grants forbidden authority")

    pack_refs = frozenset(item.evidence_ref for item in evidence_pack.items)
    required_plan_refs = frozenset(plan.evidence_refs)
    pack_ready = (
        evidence_pack.ready_for_drafting
        and required_plan_refs.issubset(pack_refs)
    )

    if not pack_ready:
        advisories = tuple(
            _unavailable(
                lane=lane,
                blocker="specialist_evidence_pack_not_ready",
            )
            for lane in plan.selected_lanes
        )
        return build_avatar_meeting_advisory_packet(
            meeting_id=plan.meeting_id,
            avatar_id=plan.avatar_id,
            required_domains=tuple(
                lane.domain for lane in plan.selected_lanes
            ),
            advisories=advisories,
        )

    provider_key = str(
        getattr(provider, "provider_key", "") or ""
    ).strip()
    if not provider_key:
        raise ValueError("specialist inference provider key required")

    advisories: list[AvatarSpecialistAdvisory] = []
    for lane in plan.selected_lanes:
        try:
            payload = provider.generate(
                lane=lane,
                task=task,
                evidence_pack=evidence_pack,
            )
            if not isinstance(payload, Mapping):
                raise RuntimeError("specialist inference result must be object")
            advisory = _validated_advisory(
                lane=lane,
                payload=payload,
                approved_refs=pack_refs,
            )
        except Exception:
            advisory = _unavailable(
                lane=lane,
                blocker="specialist_inference_failed",
            )
        advisories.append(advisory)

    return build_avatar_meeting_advisory_packet(
        meeting_id=plan.meeting_id,
        avatar_id=plan.avatar_id,
        required_domains=tuple(
            lane.domain for lane in plan.selected_lanes
        ),
        advisories=tuple(advisories),
        inference_performed=bool(plan.selected_lanes),
        inference_provider_key=provider_key,
    )
@dataclass
class GroundedGatewaySpecialistInferenceProvider:
    gateway: Any
    provider_key: str = "empire_llm_gateway_specialist_grounded"

    def generate(
        self,
        *,
        lane: AvatarSpecialistConsultationLane,
        task: AvatarRealtimeResponseTask,
        evidence_pack: AvatarEvidencePack,
    ) -> Mapping[str, Any]:
        if not evidence_pack.ready_for_drafting:
            raise ValueError("specialist evidence pack is not ready")
        if self.gateway is None or not callable(
            getattr(self.gateway, "structured_chat", None)
        ):
            raise RuntimeError(
                "Empire LLM gateway with structured_chat required"
            )

        system = (
            "Act as a private internal specialist adviser. "
            "Return JSON only with summary, truth_class and evidence_refs. "
            "Use only the supplied evidence. The generated summary is reasoning "
            "guidance, never evidence. truth_class must be INFERRED or FORECAST. "
            "Cite only supplied evidence_ref values. Do not reveal chain of "
            "thought; return only a concise advisory conclusion. Do not call "
            "tools, speak, send messages, accept terms, request payment, move "
            "funds, write revenue, or claim any action occurred."
        )
        state = {
            "domain": lane.domain,
            "department_key": lane.department_key,
            "department_name": lane.department_name,
            "department_mission": lane.mission,
            "agent_roles": list(lane.agent_roles),
            "meeting_id": task.meeting_id,
            "objective": task.objective,
            "latest_buyer_utterance": task.latest_buyer_utterance,
            "recommended_action_key": task.recommended_action_key,
            "evidence": [
                item.as_dict()
                for item in evidence_pack.items
            ],
        }
        result = self.gateway.structured_chat(
            [{"role": "user", "content": json.dumps(state, sort_keys=True)}],
            task="reasoning",
            system=system,
            temperature=0.1,
            stakes="high",
        )
        if not isinstance(result, Mapping) or result.get("error"):
            raise RuntimeError("specialist inference provider failed")
        return result
