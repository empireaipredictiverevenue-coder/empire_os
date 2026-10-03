from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_evidence_pack import (
    AvatarEvidenceItem,
    AvatarEvidencePack,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_specialist_advisory_generation import (
    GroundedGatewaySpecialistInferenceProvider,
    generate_grounded_specialist_advisory_packet,
)
from empire_os.digital_avatar_specialist_consultation import (
    AvatarSpecialistConsultationLane,
    AvatarSpecialistConsultationPlan,
)
from empire_os.digital_avatar_turn import AvatarClaimTruth


QUESTION_REF = "buyer:meeting-001:q1"
OBJECTIVE_REF = "objective:meeting-001:v1"
PRICE_REF = "commercial_evidence:11111111-1111-4111-8111-111111111111"


def task():
    return AvatarRealtimeResponseTask(
        meeting_id="meeting-001",
        avatar_id="avatar-a",
        latest_buyer_utterance="What would this cost us?",
        objective="qualify fit and agree next step",
        recommended_action_key="answer_buyer_question",
        approved_evidence_refs=(QUESTION_REF, OBJECTIVE_REF, PRICE_REF),
        commercial_terms_ref=None,
        constraints=("Use only supplied evidence.",),
    )


def item(ref, content, truth=AvatarClaimTruth.VERIFIED):
    return AvatarEvidenceItem(
        evidence_ref=ref,
        content=content,
        truth_class=truth,
        source_kind="test_evidence",
        provenance=f"test:{ref}",
        verified=True,
    )


def evidence_pack(*, ready=True, include_objective=True):
    items = [
        item(
            QUESTION_REF,
            "Buyer asked what the solution would cost.",
            AvatarClaimTruth.OBSERVED,
        ),
        item(
            PRICE_REF,
            "Verified buyer-safe price is available.",
        ),
    ]
    if include_objective:
        items.append(item(OBJECTIVE_REF, "Meeting objective is qualify fit."))
    unresolved = () if ready and include_objective else (OBJECTIVE_REF,)
    return AvatarEvidencePack(
        meeting_id="meeting-001",
        avatar_id="avatar-a",
        items=tuple(items),
        unresolved_refs=unresolved,
        ready_for_drafting=bool(ready and not unresolved),
    )
def lane(domain, department_key):
    return AvatarSpecialistConsultationLane(
        domain=domain,
        department_key=department_key,
        department_name=department_key.replace("_", " ").title(),
        mission=f"Advise on {domain}.",
        components=(f"{department_key}_component",),
        agent_roles=(domain,),
    )


def plan():
    lanes = (
        lane("sales", "sales_revenue"),
        lane("predictive_revenue", "data_quant"),
    )
    return AvatarSpecialistConsultationPlan(
        tenant_id="tenant-a",
        meeting_id="meeting-001",
        avatar_id="avatar-a",
        mode=AvatarMeetingMode.COPILOT.value,
        requested_domains=("sales", "predictive_revenue"),
        selected_lanes=lanes,
        truncated_domains=(),
        evidence_refs=(QUESTION_REF, OBJECTIVE_REF),
    )


class Provider:
    provider_key = "fake-specialist-grounded"

    def __init__(self, payloads=None, fail_domain=None):
        self.calls = []
        self.payloads = dict(payloads or {})
        self.fail_domain = fail_domain

    def generate(self, *, lane, task, evidence_pack):
        self.calls.append(lane.domain)
        if lane.domain == self.fail_domain:
            raise RuntimeError("specialist failed")
        return self.payloads.get(
            lane.domain,
            {
                "summary": f"{lane.domain} recommends using verified evidence.",
                "truth_class": "INFERRED",
                "evidence_refs": [PRICE_REF],
            },
        )
def test_complete_pack_generates_grounded_multi_lane_advisories():
    provider = Provider()
    packet = generate_grounded_specialist_advisory_packet(
        plan=plan(),
        task=task(),
        evidence_pack=evidence_pack(),
        provider=provider,
    )
    assert provider.calls == ["sales", "predictive_revenue"]
    assert packet.response_context_ready is True
    assert packet.unresolved_domains == ()
    assert packet.inference_performed is True
    assert packet.inference_provider_key == "fake-specialist-grounded"
    assert packet.meeting_provider_call_performed is False
    assert packet.provider_call_performed is False
    assert packet.external_action_performed is False
    assert all(
        advisory.truth_class == AvatarClaimTruth.INFERRED
        for advisory in packet.advisories
    )
    assert all(
        advisory.evidence_refs == (PRICE_REF,)
        for advisory in packet.advisories
    )


def test_incomplete_evidence_pack_performs_zero_inference_calls():
    provider = Provider()
    packet = generate_grounded_specialist_advisory_packet(
        plan=plan(),
        task=task(),
        evidence_pack=evidence_pack(ready=False, include_objective=False),
        provider=provider,
    )
    assert provider.calls == []
    assert packet.inference_performed is False
    assert packet.inference_provider_key is None
    assert packet.response_context_ready is False
    assert packet.unresolved_domains == (
        "predictive_revenue",
        "sales",
    )
    assert all(
        advisory.blockers == ("specialist_evidence_pack_not_ready",)
        for advisory in packet.advisories
    )
def test_unapproved_specialist_citation_blocks_that_lane():
    provider = Provider({
        "sales": {
            "summary": "Use secret evidence.",
            "truth_class": "INFERRED",
            "evidence_refs": ["evidence:not-approved"],
        }
    })
    packet = generate_grounded_specialist_advisory_packet(
        plan=plan(),
        task=task(),
        evidence_pack=evidence_pack(),
        provider=provider,
    )
    sales = next(x for x in packet.advisories if x.domain == "sales")
    assert sales.available is False
    assert sales.blockers == ("specialist_uses_unapproved_evidence",)
    assert packet.response_context_ready is False
    assert "sales" in packet.unresolved_domains


def test_model_generated_verified_truth_is_rejected_as_specialist_synthesis():
    provider = Provider({
        "sales": {
            "summary": "This is definitely verified.",
            "truth_class": "VERIFIED",
            "evidence_refs": [PRICE_REF],
        }
    })
    packet = generate_grounded_specialist_advisory_packet(
        plan=plan(),
        task=task(),
        evidence_pack=evidence_pack(),
        provider=provider,
    )
    sales = next(x for x in packet.advisories if x.domain == "sales")
    assert sales.available is False
    assert sales.blockers == (
        "specialist_generated_truth_must_be_inferred_or_forecast",
    )
def test_provider_failure_becomes_unavailable_lane_not_fabricated_summary():
    provider = Provider(fail_domain="predictive_revenue")
    packet = generate_grounded_specialist_advisory_packet(
        plan=plan(),
        task=task(),
        evidence_pack=evidence_pack(),
        provider=provider,
    )
    failed = next(
        x for x in packet.advisories
        if x.domain == "predictive_revenue"
    )
    assert failed.available is False
    assert failed.summary == ""
    assert failed.evidence_refs == ()
    assert failed.blockers == ("specialist_inference_failed",)
    assert packet.response_context_ready is False


class Gateway:
    def __init__(self):
        self.calls = []

    def structured_chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {
            "summary": "Use the buyer-safe verified price as context.",
            "truth_class": "INFERRED",
            "evidence_refs": [PRICE_REF],
        }


def test_gateway_specialist_provider_receives_resolved_evidence_only():
    gateway = Gateway()
    provider = GroundedGatewaySpecialistInferenceProvider(gateway)
    packet = generate_grounded_specialist_advisory_packet(
        plan=AvatarSpecialistConsultationPlan(
            tenant_id="tenant-a",
            meeting_id="meeting-001",
            avatar_id="avatar-a",
            mode=AvatarMeetingMode.COPILOT.value,
            requested_domains=("sales",),
            selected_lanes=(lane("sales", "sales_revenue"),),
            truncated_domains=(),
            evidence_refs=(QUESTION_REF, OBJECTIVE_REF),
        ),
        task=task(),
        evidence_pack=evidence_pack(),
        provider=provider,
    )
    assert packet.response_context_ready is True
    assert len(gateway.calls) == 1
    content = gateway.calls[0][0][0]["content"]
    assert PRICE_REF in content
    assert "Verified buyer-safe price is available." in content
    assert gateway.calls[0][1]["stakes"] == "high"
