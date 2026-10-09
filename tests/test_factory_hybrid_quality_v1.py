"""Fail-closed unit tests for additive Hybrid V1 quality gate."""
import pytest
from empire_os.factory_hybrid_quality_v1 import (
    BLOCK, ESCALATE, FOUNDER, REPAIR, VERIFIED, WAIT,
    evaluate_hybrid_quality,
)


def fixture():
    req = dict(request_id="test-001", authority="internal_write", risk_class="low",
               builder_id="builder-a", persona_id="backend", soul_id="souls/backend:v1",
               proposal_branch="agent/test-001", founder_gate_required=False)
    gate = dict(schema_version="empire.execution-plane-candidate-gate.v1",
                proposal_branch="agent/test-001",
                candidate_verification={"passed": True, "candidate_patch_path": "proof/patch"},
                promptfoo_required=False, candidate_gate_passed=True,
                awaiting_promptfoo=False, production_promotion_allowed=False,
                execution_authority="none")
    self_review = dict(builder_id="builder-a", proposal_branch="agent/test-001",
                       passed=True, evidence_ref="proof/self-review")
    independent_review = dict(reviewer_id="independent-model-b", proposal_branch="agent/test-001",
                              advisory_only=True, verdict="PASS", evidence_ref="proof/review")
    return dict(request=req, proposal_gate=gate, self_review=self_review,
                independent_review=independent_review)


def verdict(data):
    result = evaluate_hybrid_quality(**data).as_dict()
    for flag in ("production_promotion_allowed", "production_merge", "production_deploy",
                 "external_send", "payment_action", "revenue_recognition", "task_done"):
        assert result[flag] is False
    assert result["execution_authority"] == "none"
    return result["status"]


def test_low_risk_review_ready():
    assert verdict(fixture()) == VERIFIED


@pytest.mark.parametrize("field", ["production_deploy", "external_send", "payment_action",
                                   "revenue_recognition", "database_migration",
                                   "commercial_terms_acceptance", "tenant_authority_change"])
def test_consequential_actions_blocked(field):
    d = fixture(); d["request"][field] = True
    assert verdict(d) == BLOCK


def test_failed_candidate_repair():
    d = fixture(); d["proposal_gate"]["candidate_verification"]["passed"] = False
    assert verdict(d) == REPAIR


def test_unfinished_candidate_waits():
    d = fixture(); d["proposal_gate"]["candidate_verification"]["passed"] = None
    assert verdict(d) == WAIT


def test_builder_self_review_mandatory():
    d = fixture(); d["self_review"] = None
    assert verdict(d) == WAIT


def test_self_review_failure():
    d = fixture(); d["self_review"]["passed"] = False
    assert verdict(d) == REPAIR


def test_self_approval_blocked():
    d = fixture(); d["independent_review"]["reviewer_id"] = "builder-a"
    assert verdict(d) == BLOCK


def test_model_advisory_cannot_be_authority():
    d = fixture(); d["independent_review"]["advisory_only"] = False
    assert verdict(d) == BLOCK


def test_model_rejection_escalated():
    d = fixture(); d["independent_review"]["verdict"] = "FAIL"
    assert verdict(d) == ESCALATE


def test_wrong_review_branch_blocked():
    d = fixture(); d["independent_review"]["proposal_branch"] = "wrong"
    assert verdict(d) == BLOCK


def test_promptfoo_queued_not_pass():
    d = fixture(); g = d["proposal_gate"]
    g.update(promptfoo_required=True, awaiting_promptfoo=True, candidate_gate_passed=False,
             promptfoo_request={"status": "QUEUED"})
    assert verdict(d) == WAIT


def test_promptfoo_independent_completed_pass():
    d = fixture(); g = d["proposal_gate"]
    g.update(promptfoo_required=True, awaiting_promptfoo=True, candidate_gate_passed=False)
    d["promptfoo_result"] = dict(status="PASS", proposal_branch="agent/test-001",
                                verifier_id="promptfoo-runner", evidence_ref="proof/promptfoo")
    assert verdict(d) == VERIFIED


def test_promptfoo_failed_repair():
    d = fixture(); g = d["proposal_gate"]
    g.update(promptfoo_required=True, awaiting_promptfoo=True, candidate_gate_passed=False)
    d["promptfoo_result"] = {"status": "FAIL"}
    assert verdict(d) == REPAIR


def test_high_risk_council_escalation():
    d = fixture(); d["request"]["risk_class"] = "high"
    assert verdict(d) == ESCALATE


def test_council_cannot_grant_deploy():
    d = fixture(); d["request"]["risk_class"] = "high"
    d["council_result"] = dict(status="RECOMMEND_APPROVE", proposal_branch="agent/test-001",
                               voter_ids=["security", "architect"], evidence_ref="proof/council")
    assert verdict(d) == VERIFIED


def test_council_self_vote_blocked():
    d = fixture(); d["request"]["risk_class"] = "high"
    d["council_result"] = dict(status="RECOMMEND_APPROVE", proposal_branch="agent/test-001",
                               voter_ids=["builder-a", "architect"], evidence_ref="proof/council")
    assert verdict(d) == BLOCK


def test_founder_gate_not_auto_approved():
    d = fixture(); d["request"]["founder_gate_required"] = True
    assert verdict(d) == FOUNDER


def test_persona_and_soul_required():
    d = fixture(); d["request"]["soul_id"] = ""
    assert verdict(d) == BLOCK


def test_candidate_promote_claim_blocks():
    d = fixture(); d["proposal_gate"]["production_promotion_allowed"] = True
    assert verdict(d) == BLOCK


def test_branch_mismatch_blocks():
    d = fixture(); d["request"]["proposal_branch"] = "other"
    assert verdict(d) == BLOCK


def test_malformed_council_votes_fail_closed_not_exception():
    d = fixture(); d["request"]["risk_class"] = "high"
    d["council_result"] = dict(status="RECOMMEND_APPROVE", proposal_branch="agent/test-001",
                               voter_ids=[{"bad": "shape"}, "architect"], evidence_ref="proof/council")
    assert verdict(d) == BLOCK


def test_integer_founder_gate_flag_rejected():
    d = fixture(); d["request"]["founder_gate_required"] = 0
    assert verdict(d) == BLOCK


def test_promptfoo_self_attestation_blocked():
    d = fixture(); g = d["proposal_gate"]
    g.update(promptfoo_required=True, awaiting_promptfoo=True, candidate_gate_passed=False)
    d["promptfoo_result"] = dict(status="PASS", proposal_branch="agent/test-001",
                                verifier_id="builder-a", evidence_ref="proof/promptfoo")
    assert verdict(d) == BLOCK
