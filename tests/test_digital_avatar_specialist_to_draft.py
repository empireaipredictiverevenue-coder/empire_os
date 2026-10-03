import pytest

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_evidence_pack import (
    AvatarEvidenceItem,
    AvatarEvidencePack,
)
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_response_draft import (
    generate_validated_grounded_avatar_response_draft,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_specialist_advisory_generation import (
    generate_grounded_specialist_advisory_packet,
)
from empire_os.digital_avatar_specialist_consultation import (
    AvatarSpecialistConsultationRequest,
    build_avatar_specialist_consultation_plan,
)
from empire_os.digital_avatar_specialist_response_context import (
    attach_specialist_context_to_response_task,
)
from empire_os.digital_avatar_turn import AvatarClaimTruth


QUESTION_REF = "buyer:q1"
OBJECTIVE_REF = "objective:v1"
PRICE_REF = "commercial_evidence:11111111-1111-4111-8111-111111111111"


def runtime():
    return AvatarFleetRuntimeBinding(
        tenant_id="tenant-a",
        avatar_id="avatar-a",
        owner_ref="person:avatar-a",
        owner_name="Owner A",
        capability_labels=("sales",),
        membership_user_id="user-1",
        membership_role="operator",
        owner_consent_evidence_ref="consent:avatar-a:v1",
    )


def task():
    return AvatarRealtimeResponseTask(
        meeting_id="meeting-001",
        avatar_id="avatar-a",
        latest_buyer_utterance="What does it cost?",
        objective="qualify fit",
        recommended_action_key="answer_buyer_question",
        approved_evidence_refs=(QUESTION_REF, OBJECTIVE_REF, PRICE_REF),
        commercial_terms_ref=None,
        constraints=("Use only supplied evidence.",),
    )


def pack():
    return AvatarEvidencePack(
        meeting_id="meeting-001",
        avatar_id="avatar-a",
        items=(
            AvatarEvidenceItem(
                evidence_ref=QUESTION_REF,
                content="Buyer asked what it costs.",
                truth_class=AvatarClaimTruth.OBSERVED,
                source_kind="meeting_transcript",
                provenance="recall:verified:q1",
                verified=True,
            ),
            AvatarEvidenceItem(
                evidence_ref=OBJECTIVE_REF,
                content="Meeting objective is qualify fit.",
                truth_class=AvatarClaimTruth.VERIFIED,
                source_kind="meeting_objective",
                provenance="objective:verified:v1",
                verified=True,
            ),
            AvatarEvidenceItem(
                evidence_ref=PRICE_REF,
                content="Verified buyer-safe price is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                source_kind="commercial_price",
                provenance="price:verified:v1",
                verified=True,
            ),
        ),
        unresolved_refs=(),
        ready_for_drafting=True,
    )
class SpecialistProvider:
    provider_key = "specialist-test"

    def generate(self, *, lane, task, evidence_pack):
        return {
            "summary": "Use the verified price evidence and stay concise.",
            "truth_class": "INFERRED",
            "evidence_refs": [PRICE_REF],
        }


class DraftProvider:
    provider_key = "draft-test"

    def __init__(self):
        self.calls = 0

    def generate_grounded(self, task, evidence_pack):
        self.calls += 1
        assert task.specialist_context_ready is True
        assert task.specialist_context[0]["domain"] == "sales"
        assert task.specialist_context[0]["summary"] == (
            "Use the verified price evidence and stay concise."
        )
        return {
            "text": "I can walk you through the verified price.",
            "claims": [{
                "text": "A verified buyer-safe price is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": [PRICE_REF],
            }],
        }
def consultation_plan():
    return build_avatar_specialist_consultation_plan(
        runtime=runtime(),
        request=AvatarSpecialistConsultationRequest(
            tenant_id="tenant-a",
            meeting_id="meeting-001",
            avatar_id="avatar-a",
            mode=AvatarMeetingMode.COPILOT,
            consultation_domains=("sales",),
            question_evidence_ref=QUESTION_REF,
            objective_evidence_ref=OBJECTIVE_REF,
        ),
    )


def test_specialist_advice_flows_into_private_grounded_draft_not_evidence():
    original = task()
    evidence = pack()
    advisory = generate_grounded_specialist_advisory_packet(
        plan=consultation_plan(),
        task=original,
        evidence_pack=evidence,
        provider=SpecialistProvider(),
    )
    enriched = attach_specialist_context_to_response_task(
        task=original,
        packet=advisory,
    )

    assert enriched.specialist_context_ready is True
    assert all(
        not ref.startswith("specialist:")
        for ref in enriched.approved_evidence_refs
    )
    assert PRICE_REF in enriched.approved_evidence_refs

    provider = DraftProvider()
    draft = generate_validated_grounded_avatar_response_draft(
        task=enriched,
        evidence_pack=evidence,
        provider=provider,
        source_ref="draft:meeting-001:specialist-e2e",
    )
    assert provider.calls == 1
    assert draft.ready_for_human_review is True
    assert draft.transmission_performed is False
    assert draft.speech_execution_allowed is False
    assert draft.execution_authority == "none"
    assert draft.claims[0].evidence_refs == (PRICE_REF,)
def test_unresolved_specialist_lane_blocks_response_generation():
    class FailingSpecialist:
        provider_key = "specialist-fail"

        def generate(self, **_kwargs):
            raise RuntimeError("no specialist evidence")

    original = task()
    evidence = pack()
    advisory = generate_grounded_specialist_advisory_packet(
        plan=consultation_plan(),
        task=original,
        evidence_pack=evidence,
        provider=FailingSpecialist(),
    )
    enriched = attach_specialist_context_to_response_task(
        task=original,
        packet=advisory,
    )
    assert enriched.specialist_context_ready is False

    provider = DraftProvider()
    with pytest.raises(ValueError, match="specialist context is not ready"):
        generate_validated_grounded_avatar_response_draft(
            task=enriched,
            evidence_pack=evidence,
            provider=provider,
            source_ref="draft:blocked",
        )
    assert provider.calls == 0
