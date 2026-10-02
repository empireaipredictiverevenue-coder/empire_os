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
