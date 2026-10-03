import pytest

from empire_os.digital_avatar_response_draft import (
    GatewayAvatarDraftProvider,
    response_draft_to_turn,
    validate_avatar_response_draft,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask


def task():
    return AvatarRealtimeResponseTask(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        latest_buyer_utterance="Can you show me proof?",
        objective="qualify fit and agree next step",
        recommended_action_key="present_verified_case_evidence",
        approved_evidence_refs=(
            "conversation:turn:7",
            "evidence:case:7",
            "terms:pilot:v1",
        ),
        commercial_terms_ref="terms:pilot:v1",
        constraints=("Return a private draft.",),
    )


def test_valid_draft_uses_only_approved_evidence():
    draft = validate_avatar_response_draft(
        task=task(),
        payload={
            "text": "Yes. I can show you the verified case evidence.",
            "claims": [{
                "text": "Verified case evidence is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:case:7"],
            }],
        },
        provider_key="fake",
        source_ref="test:1",
    )
    assert draft.ready_for_human_review is True
    assert draft.blockers == ()
    assert draft.speech_execution_allowed is False
    assert draft.transmission_performed is False


def test_unapproved_evidence_blocks_draft():
    draft = validate_avatar_response_draft(
        task=task(),
        payload={
            "text": "I can show you another result.",
            "claims": [{
                "text": "Another result exists.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:not-approved"],
            }],
        },
        provider_key="fake",
        source_ref="test:2",
    )
    assert draft.ready_for_human_review is False
    assert "claim_uses_unapproved_evidence" in draft.blockers


def test_claim_without_evidence_blocks_draft():
    draft = validate_avatar_response_draft(
        task=task(),
        payload={
            "text": "We should be able to improve this.",
            "claims": [{
                "text": "We should be able to improve this.",
                "truth_class": "FORECAST",
                "evidence_refs": [],
            }],
        },
        provider_key="fake",
        source_ref="test:3",
    )
    assert draft.ready_for_human_review is False
    assert "claim_evidence_missing" in draft.blockers


def test_ready_draft_converts_to_existing_turn_contract():
    draft = validate_avatar_response_draft(
        task=task(),
        payload={
            "text": "I can show you the verified evidence.",
            "claims": [{
                "text": "Verified case evidence is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:case:7"],
            }],
        },
        provider_key="fake",
        source_ref="test:4",
    )
    turn = response_draft_to_turn(draft=draft)
    assert turn.meeting_id == "meeting-001"
    assert turn.avatar_id == "avatar-phil-v1"
    assert turn.strategy_evidence_refs == ("evidence:case:7",)


class FakeGateway:
    def __init__(self):
        self.calls = []

    def structured_chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {
            "text": "I can show you the verified evidence.",
            "claims": [{
                "text": "Verified case evidence is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:case:7"],
            }],
        }


def test_gateway_provider_uses_existing_structured_gateway_contract():
    gateway = FakeGateway()
    provider = GatewayAvatarDraftProvider(gateway)
    payload = provider.generate(task())
    assert payload["text"]
    assert len(gateway.calls) == 1
    messages, kwargs = gateway.calls[0]
    assert kwargs["task"] == "reasoning"
    assert kwargs["stakes"] == "high"
    assert kwargs["temperature"] == 0.1
    assert "Can you show me proof?" in messages[0]["content"]


def test_provider_requires_structured_gateway():
    provider = GatewayAvatarDraftProvider(object())
    with pytest.raises(RuntimeError, match="structured_chat required"):
        provider.generate(task())


def evidence_pack():
    from empire_os.digital_avatar_evidence_pack import (
        AvatarEvidenceItem,
        AvatarEvidencePack,
    )
    from empire_os.digital_avatar_turn import AvatarClaimTruth

    return AvatarEvidencePack(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        items=(
            AvatarEvidenceItem(
                evidence_ref="conversation:turn:7",
                content="Buyer asked: Can you show me proof?",
                truth_class=AvatarClaimTruth.OBSERVED,
                source_kind="meeting_transcript",
                provenance="recall:transcript:456",
                verified=True,
            ),
            AvatarEvidenceItem(
                evidence_ref="evidence:case:7",
                content="Verified case evidence is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                source_kind="commercial_evidence",
                provenance="empire:evidence:7",
                verified=True,
            ),
        ),
        unresolved_refs=(),
        ready_for_drafting=True,
    )


class GroundedFakeGateway:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "text": "Yes. I can show you the verified case evidence.",
            "claims": [{
                "text": "Verified case evidence is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:case:7"],
            }],
        }

    def structured_chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.result


def test_grounded_gateway_receives_evidence_content_not_just_refs():
    from empire_os.digital_avatar_response_draft import (
        GroundedGatewayAvatarDraftProvider,
    )

    gateway = GroundedFakeGateway()
    provider = GroundedGatewayAvatarDraftProvider(gateway)
    payload = provider.generate_grounded(task(), evidence_pack())
    assert payload["text"]
    content = gateway.calls[0][0][0]["content"]
    assert "Verified case evidence is available." in content
    assert "evidence:case:7" in content
    assert gateway.calls[0][1]["stakes"] == "high"


def test_grounded_draft_is_validated_against_task_approved_refs():
    from empire_os.digital_avatar_response_draft import (
        GroundedGatewayAvatarDraftProvider,
        generate_validated_grounded_avatar_response_draft,
    )

    provider = GroundedGatewayAvatarDraftProvider(GroundedFakeGateway())
    draft = generate_validated_grounded_avatar_response_draft(
        task=task(),
        evidence_pack=evidence_pack(),
        provider=provider,
        source_ref="draft:meeting-001:1",
    )
    assert draft.ready_for_human_review is True
    assert draft.transmission_performed is False
    assert draft.speech_execution_allowed is False
    assert draft.execution_authority == "none"


def test_grounded_draft_rejects_unapproved_model_citation():
    from empire_os.digital_avatar_response_draft import (
        GroundedGatewayAvatarDraftProvider,
        generate_validated_grounded_avatar_response_draft,
    )

    gateway = GroundedFakeGateway({
        "text": "I can show another result.",
        "claims": [{
            "text": "Another result exists.",
            "truth_class": "VERIFIED",
            "evidence_refs": ["evidence:not-approved"],
        }],
    })
    draft = generate_validated_grounded_avatar_response_draft(
        task=task(),
        evidence_pack=evidence_pack(),
        provider=GroundedGatewayAvatarDraftProvider(gateway),
        source_ref="draft:meeting-001:2",
    )
    assert draft.ready_for_human_review is False
    assert "claim_uses_unapproved_evidence" in draft.blockers


def specialist_task(*, ready=True):
    from dataclasses import replace

    base = task()
    return replace(
        base,
        specialist_context=({
            "domain": "pricing",
            "source_component": "empire.pricing",
            "summary": "Use the verified price evidence.",
            "truth_class": "VERIFIED",
            "evidence_refs": ["evidence:case:7"],
            "available": ready,
            "blockers": [] if ready else ["price_missing"],
        },),
        specialist_context_ready=ready,
        specialist_context_blockers=(
            () if ready else ("specialist_domain_unresolved:pricing",)
        ),
    )


def test_grounded_gateway_receives_specialist_context_separate_from_evidence():
    import json
    from empire_os.digital_avatar_response_draft import (
        GroundedGatewayAvatarDraftProvider,
    )

    gateway = GroundedFakeGateway()
    provider = GroundedGatewayAvatarDraftProvider(gateway)
    provider.generate_grounded(specialist_task(), evidence_pack())
    content = json.loads(gateway.calls[0][0][0]["content"])
    assert content["specialist_context"][0]["domain"] == "pricing"
    assert content["specialist_context"][0]["summary"] == (
        "Use the verified price evidence."
    )
    evidence_refs = {
        item["evidence_ref"]
        for item in content["evidence"]
    }
    assert "evidence:case:7" in evidence_refs
    assert all(
        not ref.startswith("specialist:")
        for ref in evidence_refs
    )


def test_ungrounded_provider_refuses_specialist_context():
    gateway = FakeGateway()
    provider = GatewayAvatarDraftProvider(gateway)
    with pytest.raises(
        RuntimeError,
        match="specialist context requires grounded",
    ):
        provider.generate(specialist_task())
    assert gateway.calls == []


def test_unresolved_specialist_context_blocks_grounded_provider():
    from empire_os.digital_avatar_response_draft import (
        GroundedGatewayAvatarDraftProvider,
    )

    gateway = GroundedFakeGateway()
    provider = GroundedGatewayAvatarDraftProvider(gateway)
    with pytest.raises(ValueError, match="specialist context is not ready"):
        provider.generate_grounded(
            specialist_task(ready=False),
            evidence_pack(),
        )
    assert gateway.calls == []


def test_specialist_summary_cannot_be_cited_as_evidence():
    from empire_os.digital_avatar_response_draft import (
        GroundedGatewayAvatarDraftProvider,
        generate_validated_grounded_avatar_response_draft,
    )

    gateway = GroundedFakeGateway({
        "text": "The specialist says the price is approved.",
        "claims": [{
            "text": "The specialist says the price is approved.",
            "truth_class": "VERIFIED",
            "evidence_refs": ["specialist:pricing:summary"],
        }],
    })
    draft = generate_validated_grounded_avatar_response_draft(
        task=specialist_task(),
        evidence_pack=evidence_pack(),
        provider=GroundedGatewayAvatarDraftProvider(gateway),
        source_ref="draft:meeting-001:specialist",
    )
    assert draft.ready_for_human_review is False
    assert "claim_uses_unapproved_evidence" in draft.blockers
