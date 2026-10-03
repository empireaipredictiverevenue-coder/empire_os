import json

from empire_os.digital_avatar_evidence_resolver import (
    MappingAvatarEvidenceResolver,
)
from empire_os.digital_avatar_private_draft_service import (
    process_guidance_once,
    run_once,
)


def guidance_payload(refs=None):
    refs = refs or ["recall:turn:7"]
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "private_to_owner": True,
        "speech_execution": False,
        "execution_authority": "none",
        "response_task": {
            "meeting_id": "meeting-001",
            "avatar_id": "avatar-phil-v1",
            "latest_buyer_utterance": "Can you show me proof?",
            "objective": "qualify fit and agree next step",
            "recommended_action_key": "answer_buyer_question",
            "approved_evidence_refs": refs,
            "commercial_terms_ref": None,
            "constraints": ["Use only supplied evidence."],
            "mode": "COPILOT_PREVIEW",
            "output_channel": "private_draft",
            "requires_human_approval": True,
            "speech_execution_allowed": False,
            "execution_authority": "none",
        },
    }


class Provider:
    provider_key = "fake"

    def __init__(self):
        self.calls = 0

    def generate_grounded(self, task, evidence_pack):
        self.calls += 1
        ref = evidence_pack.items[0].evidence_ref
        return {
            "text": "I can answer that from the verified meeting evidence.",
            "claims": [{
                "text": "The buyer asked for proof.",
                "truth_class": "OBSERVED",
                "evidence_refs": [ref],
            }],
        }


def test_process_guidance_once_materializes_one_private_draft(tmp_path):
    guidance = tmp_path / "guidance"
    guidance.mkdir()
    (guidance / "meeting-001.json").write_text(
        json.dumps(guidance_payload())
    )
    resolver = MappingAvatarEvidenceResolver({
        "recall:turn:7": {
            "evidence_ref": "recall:turn:7",
            "content": "Can you show me proof?",
            "truth_class": "OBSERVED",
            "source_kind": "meeting_transcript",
            "provenance": "recall-verification:1",
            "verified": True,
        }
    })
    provider = Provider()

    result = process_guidance_once(
        guidance_root=guidance,
        draft_root=tmp_path / "drafts",
        evidence_resolver=resolver,
        provider=provider,
        max_items=3,
    )
    assert result["scanned"] == 1
    assert result["ready_for_human_review"] == 1
    assert result["provider_calls"] == 1
    assert result["failed"] == 0
    assert provider.calls == 1


def test_disabled_run_never_constructs_gateway_or_llm():
    calls = []

    def gateway_factory(_env):
        calls.append("gateway")
        raise AssertionError("must not construct gateway")

    def llm_factory():
        calls.append("llm")
        raise AssertionError("must not construct llm")

    result = run_once(
        environ={"EMPIRE_AVATAR_PRIVATE_DRAFT_ENABLED": "false"},
        gateway_factory=gateway_factory,
        llm_factory=llm_factory,
    )
    assert result["enabled"] is False
    assert result["provider_calls"] == 0
    assert result["execution_authority"] == "none"
    assert result["transmission_performed"] is False
    assert calls == []


class FakeGateway:
    pass


class FakeLlm:
    def __init__(self):
        self.calls = 0

    def structured_chat(self, messages, **kwargs):
        self.calls += 1
        return {
            "text": "You asked whether we can show proof.",
            "claims": [{
                "text": "You asked whether we can show proof.",
                "truth_class": "OBSERVED",
                "evidence_refs": ["recall:bot-1:transcript-1:abc"],
            }],
        }


def test_enabled_run_uses_signed_recall_observation_and_stays_private(tmp_path):
    guidance = tmp_path / "guidance"
    observations = tmp_path / "observations"
    drafts = tmp_path / "drafts"
    guidance.mkdir()
    observations.mkdir()

    recall_ref = "recall:bot-1:transcript-1:abc"
    (guidance / "meeting-001.json").write_text(
        json.dumps(guidance_payload([recall_ref]))
    )
    (observations / "q1.json").write_text(json.dumps({
        "verification_ref": "recall-verification:msg:1:abc",
        "observation": {
            "evidence_ref": recall_ref,
            "text": "Can you show me proof?",
        },
    }))

    llm = FakeLlm()
    result = run_once(
        environ={
            "EMPIRE_AVATAR_PRIVATE_DRAFT_ENABLED": "true",
            "EMPIRE_RECALL_GUIDANCE_ROOT": str(guidance),
            "EMPIRE_RECALL_OBSERVATION_ROOT": str(observations),
            "EMPIRE_AVATAR_PRIVATE_DRAFT_ROOT": str(drafts),
            "EMPIRE_AVATAR_PRIVATE_DRAFT_MAX_PER_SCAN": "3",
        },
        gateway_factory=lambda _env: FakeGateway(),
        llm_factory=lambda: llm,
    )
    assert result["enabled"] is True
    assert result["ready_for_human_review"] == 1
    assert result["provider_calls"] == 1
    assert result["transmission_performed"] is False
    assert result["speech_execution_allowed"] is False
    assert result["execution_authority"] == "none"
    assert llm.calls == 1


def test_service_counts_unresolved_specialist_context_without_model_call(tmp_path):
    guidance = tmp_path / "guidance"
    guidance.mkdir()
    payload = guidance_payload()
    payload["response_task"]["specialist_context"] = [{
        "domain": "technical",
        "source_component": "empire.technical",
        "summary": "",
        "truth_class": "OBSERVED",
        "evidence_refs": [],
        "available": False,
        "blockers": ["technical_evidence_missing"],
    }]
    payload["response_task"]["specialist_context_ready"] = False
    payload["response_task"]["specialist_context_blockers"] = [
        "specialist_domain_unresolved:technical"
    ]
    (guidance / "meeting-001.json").write_text(json.dumps(payload))

    provider = Provider()
    resolver = MappingAvatarEvidenceResolver({
        "recall:turn:7": {
            "evidence_ref": "recall:turn:7",
            "content": "Can you show me proof?",
            "truth_class": "OBSERVED",
            "source_kind": "meeting_transcript",
            "provenance": "recall-verification:1",
            "verified": True,
        }
    })
    result = process_guidance_once(
        guidance_root=guidance,
        draft_root=tmp_path / "drafts",
        evidence_resolver=resolver,
        provider=provider,
        max_items=3,
    )
    assert result["blocked_specialist_context"] == 1
    assert result["provider_calls"] == 0
    assert result["failed"] == 0
    assert provider.calls == 0
