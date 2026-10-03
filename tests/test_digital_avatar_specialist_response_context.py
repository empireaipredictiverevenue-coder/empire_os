from dataclasses import replace

import pytest

from empire_os.digital_avatar_meeting_specialist_bridge import (
    AvatarSpecialistAdvisory,
    build_avatar_meeting_advisory_packet,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_specialist_response_context import (
    attach_specialist_context_to_response_task,
)
from empire_os.digital_avatar_turn import AvatarClaimTruth


def task():
    return AvatarRealtimeResponseTask(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        latest_buyer_utterance="What does it cost?",
        objective="qualify fit and agree next step",
        recommended_action_key="answer_buyer_question",
        approved_evidence_refs=("recall:turn:7",),
        commercial_terms_ref=None,
        constraints=("Use only supplied evidence.",),
    )


def advisory(
    domain="pricing",
    *,
    available=True,
    evidence_refs=("commercial_evidence:11111111-1111-4111-8111-111111111111",),
    blockers=(),
):
    return AvatarSpecialistAdvisory(
        domain=domain,
        source_component="empire.pricing",
        summary="Pricing specialist recommends using the verified price evidence.",
        truth_class=AvatarClaimTruth.VERIFIED,
        evidence_refs=tuple(evidence_refs),
        available=available,
        blockers=tuple(blockers),
    )
def packet(*, available=True):
    item = (
        advisory()
        if available
        else advisory(
            available=False,
            evidence_refs=(),
            blockers=("verified_price_missing",),
        )
    )
    return build_avatar_meeting_advisory_packet(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        required_domains=("pricing",),
        advisories=(item,),
    )


def test_ready_specialist_context_adds_underlying_refs_not_summary_ref():
    value = attach_specialist_context_to_response_task(
        task=task(),
        packet=packet(),
    )
    assert value.specialist_context_ready is True
    assert value.specialist_context_blockers == ()
    assert (
        "commercial_evidence:11111111-1111-4111-8111-111111111111"
        in value.approved_evidence_refs
    )
    assert all(
        not ref.startswith("specialist:")
        for ref in value.approved_evidence_refs
    )
    assert value.specialist_context[0]["domain"] == "pricing"
    assert "Pricing specialist" in value.specialist_context[0]["summary"]
def test_unresolved_specialist_context_marks_task_not_ready():
    value = attach_specialist_context_to_response_task(
        task=task(),
        packet=packet(available=False),
    )
    assert value.specialist_context_ready is False
    assert value.specialist_context_blockers == (
        "specialist_domain_unresolved:pricing",
    )
    assert value.approved_evidence_refs == ("recall:turn:7",)


def test_context_identity_must_match_response_task():
    wrong = replace(task(), meeting_id="meeting-999")
    with pytest.raises(ValueError, match="meeting identity mismatch"):
        attach_specialist_context_to_response_task(
            task=wrong,
            packet=packet(),
        )

    wrong_avatar = replace(task(), avatar_id="avatar-other")
    with pytest.raises(ValueError, match="avatar identity mismatch"):
        attach_specialist_context_to_response_task(
            task=wrong_avatar,
            packet=packet(),
        )


def test_authority_bearing_packet_is_rejected_before_attachment():
    unsafe = replace(
        packet(),
        execution_authority="live",
    )
    with pytest.raises(ValueError, match="execution authority invariant"):
        attach_specialist_context_to_response_task(
            task=task(),
            packet=unsafe,
        )
