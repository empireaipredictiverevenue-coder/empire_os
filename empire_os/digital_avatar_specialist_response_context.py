"""Attach internal specialist advisory context to a Digital Avatar response task."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from empire_os.digital_avatar_meeting_specialist_bridge import (
    AvatarMeetingAdvisoryPacket,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask


def _safe_advisory_context(packet: AvatarMeetingAdvisoryPacket) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "domain": advisory.domain,
            "source_component": advisory.source_component,
            "summary": advisory.summary,
            "truth_class": advisory.truth_class.value,
            "evidence_refs": list(advisory.evidence_refs),
            "available": advisory.available,
            "blockers": list(advisory.blockers),
        }
        for advisory in packet.advisories
    )


def attach_specialist_context_to_response_task(
    *,
    task: AvatarRealtimeResponseTask,
    packet: AvatarMeetingAdvisoryPacket,
) -> AvatarRealtimeResponseTask:
    if task.meeting_id != packet.meeting_id:
        raise ValueError("specialist context meeting identity mismatch")
    if task.avatar_id != packet.avatar_id:
        raise ValueError("specialist context avatar identity mismatch")
    if packet.single_visible_avatar is not True:
        raise ValueError("specialist context single-voice invariant violated")
    if packet.specialist_speech_execution_allowed is not False:
        raise ValueError("specialist context speech invariant violated")
    if packet.meeting_provider_call_performed is not False:
        raise ValueError(
            "specialist context meeting-provider-call invariant violated"
        )
    if (
        packet.inference_performed
        and not str(packet.inference_provider_key or "").strip()
    ):
        raise ValueError(
            "specialist context inference-provider invariant violated"
        )
    if packet.external_action_performed is not False:
        raise ValueError("specialist context external-action invariant violated")
    if packet.commercial_authority != "none":
        raise ValueError("specialist context commercial authority invariant violated")
    if packet.financial_authority != "none":
        raise ValueError("specialist context financial authority invariant violated")
    if packet.execution_authority != "none":
        raise ValueError("specialist context execution authority invariant violated")
    available_refs = tuple(
        ref
        for advisory in packet.advisories
        if advisory.available
        for ref in advisory.evidence_refs
        if str(ref or "").strip()
    )
    refs = tuple(
        dict.fromkeys(
            (
                *task.approved_evidence_refs,
                *available_refs,
            )
        )
    )
    blockers = tuple(
        f"specialist_domain_unresolved:{domain}"
        for domain in packet.unresolved_domains
    )

    return replace(
        task,
        approved_evidence_refs=refs,
        specialist_context=_safe_advisory_context(packet),
        specialist_context_ready=packet.response_context_ready,
        specialist_context_blockers=blockers,
    )
