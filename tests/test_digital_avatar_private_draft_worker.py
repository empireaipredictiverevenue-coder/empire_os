import json

from empire_os.digital_avatar_evidence_resolver import MappingAvatarEvidenceResolver
from empire_os.digital_avatar_private_draft_worker import (
    materialize_private_avatar_draft,
)


def guidance_payload():
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
            "recommended_action_key": "present_verified_case_evidence",
            "approved_evidence_refs": [
                "recall:turn:7",
                "evidence:case:7",
                "terms:pilot:v1",
            ],
            "commercial_terms_ref": "terms:pilot:v1",
            "constraints": [
                "Use only supplied evidence.",
                "Return a private draft.",
            ],
            "mode": "COPILOT_PREVIEW",
            "output_channel": "private_draft",
            "requires_human_approval": True,
            "speech_execution_allowed": False,
            "execution_authority": "none",
        },
    }


def resolver(include_terms=True, include_case=True):
    values = {
        "recall:turn:7": {
            "evidence_ref": "recall:turn:7",
            "content": "Can you show me proof?",
            "truth_class": "OBSERVED",
            "source_kind": "meeting_transcript",
            "provenance": "recall-verification:1",
            "verified": True,
        },
    }
    if include_case:
        values["evidence:case:7"] = {
            "evidence_ref": "evidence:case:7",
            "content": "Verified case evidence is available.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_evidence",
            "provenance": "evidence-registry:7",
            "verified": True,
        }
    if include_terms:
        values["terms:pilot:v1"] = {
            "evidence_ref": "terms:pilot:v1",
            "content": "Approved pilot terms are available.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_terms",
            "provenance": "terms-registry:v1",
            "verified": True,
        }
    return MappingAvatarEvidenceResolver(values)


class Provider:
    provider_key = "fake-grounded"

    def __init__(self):
        self.calls = 0

    def generate_grounded(self, task, evidence_pack):
        self.calls += 1
        return {
            "text": "Yes. I can show you the verified case evidence.",
            "claims": [{
                "text": "Verified case evidence is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:case:7"],
            }],
        }


def write_guidance(tmp_path):
    path = tmp_path / "guidance.json"
    path.write_text(json.dumps(guidance_payload()), encoding="utf-8")
    return path


def test_incomplete_evidence_blocks_without_provider_call(tmp_path):
    provider = Provider()
    result = materialize_private_avatar_draft(
        guidance_path=write_guidance(tmp_path),
        evidence_resolver=resolver(include_terms=False),
        provider=provider,
        output_root=tmp_path / "drafts",
    )
    assert result.status == "blocked_evidence"
    assert result.unresolved_refs == ("terms:pilot:v1",)
    assert result.provider_call_performed is False
    assert result.transmission_performed is False
    assert provider.calls == 0


def test_complete_evidence_materializes_private_review_draft(tmp_path):
    provider = Provider()
    result = materialize_private_avatar_draft(
        guidance_path=write_guidance(tmp_path),
        evidence_resolver=resolver(),
        provider=provider,
        output_root=tmp_path / "drafts",
    )
    assert result.status == "ready_for_human_review"
    assert result.provider_call_performed is True
    assert result.draft.ready_for_human_review is True
    assert result.human_approval_required is True
    assert result.transmission_performed is False
    assert result.speech_execution_allowed is False
    assert result.execution_authority == "none"
    assert provider.calls == 1
    latest = tmp_path / "drafts" / "meeting-001" / "latest.json"
    assert latest.is_file()
    assert oct(latest.stat().st_mode & 0o777) == "0o600"


def test_unchanged_task_is_deduplicated_without_second_provider_call(tmp_path):
    provider = Provider()
    kwargs = {
        "guidance_path": write_guidance(tmp_path),
        "evidence_resolver": resolver(),
        "provider": provider,
        "output_root": tmp_path / "drafts",
    }
    first = materialize_private_avatar_draft(**kwargs)
    second = materialize_private_avatar_draft(**kwargs)
    assert first.status == "ready_for_human_review"
    assert second.status == "existing"
    assert second.duplicate is True
    assert second.provider_call_performed is False
    assert provider.calls == 1


def test_unsafe_guidance_authority_is_rejected(tmp_path):
    payload = guidance_payload()
    payload["execution_authority"] = "live"
    path = tmp_path / "guidance.json"
    path.write_text(json.dumps(payload))
    provider = Provider()
    try:
        materialize_private_avatar_draft(
            guidance_path=path,
            evidence_resolver=resolver(),
            provider=provider,
            output_root=tmp_path / "drafts",
        )
    except ValueError as exc:
        assert "authority invariant" in str(exc)
    else:
        raise AssertionError("unsafe guidance must fail")
    assert provider.calls == 0


def test_unresolved_specialist_context_blocks_without_provider_call(tmp_path):
    payload = guidance_payload()
    task = payload["response_task"]
    task["specialist_context"] = [{
        "domain": "technical",
        "source_component": "empire.technical",
        "summary": "",
        "truth_class": "OBSERVED",
        "evidence_refs": [],
        "available": False,
        "blockers": ["technical_evidence_missing"],
    }]
    task["specialist_context_ready"] = False
    task["specialist_context_blockers"] = [
        "specialist_domain_unresolved:technical"
    ]
    path = tmp_path / "guidance-specialist-blocked.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    provider = Provider()
    result = materialize_private_avatar_draft(
        guidance_path=path,
        evidence_resolver=resolver(),
        provider=provider,
        output_root=tmp_path / "drafts",
    )
    assert result.status == "blocked_specialist_context"
    assert result.provider_call_performed is False
    assert result.specialist_context_blockers == (
        "specialist_domain_unresolved:technical",
    )
    assert provider.calls == 0


def test_specialist_context_changes_draft_content_digest(tmp_path):
    provider = Provider()

    first_payload = guidance_payload()
    first_payload["response_task"]["specialist_context"] = [{
        "domain": "pricing",
        "source_component": "empire.pricing",
        "summary": "Use verified case evidence.",
        "truth_class": "VERIFIED",
        "evidence_refs": ["evidence:case:7"],
        "available": True,
        "blockers": [],
    }]
    first_path = tmp_path / "guidance-a.json"
    first_path.write_text(json.dumps(first_payload), encoding="utf-8")

    second_payload = guidance_payload()
    second_payload["response_task"]["specialist_context"] = [{
        "domain": "pricing",
        "source_component": "empire.pricing",
        "summary": "Use verified case evidence and keep the answer concise.",
        "truth_class": "VERIFIED",
        "evidence_refs": ["evidence:case:7"],
        "available": True,
        "blockers": [],
    }]
    second_path = tmp_path / "guidance-b.json"
    second_path.write_text(json.dumps(second_payload), encoding="utf-8")

    first = materialize_private_avatar_draft(
        guidance_path=first_path,
        evidence_resolver=resolver(),
        provider=provider,
        output_root=tmp_path / "drafts",
    )
    second = materialize_private_avatar_draft(
        guidance_path=second_path,
        evidence_resolver=resolver(),
        provider=provider,
        output_root=tmp_path / "drafts",
    )
    assert first.task_sha256 != second.task_sha256
    assert first.status == "ready_for_human_review"
    assert second.status == "ready_for_human_review"
    assert provider.calls == 2
