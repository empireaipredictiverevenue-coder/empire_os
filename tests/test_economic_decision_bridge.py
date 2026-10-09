import copy

import pytest

from empire_os.capital_allocator import CapitalCandidate
from empire_os.capital_registry import CapitalReviewRecord
from empire_os.capital_review import (
    CapitalReview,
    CapitalReviewPolicy,
    review_capital_candidate,
)
from empire_os.department_work_queue import DepartmentWorkQueueError
from empire_os.economic_decision_bridge import (
    SCHEMA_VERSION,
    build_economic_decision_work_proposal,
    enqueue_economic_decision_work,
)


TENANT = "tenant:test"
KEY = "opportunity:test"
OPPORTUNITY_ID = "opp:test"
PREDICTION = "quant_prediction:test"
STATE = "state:economic:test"
SOURCE = "capital_review:test"


def record(*, candidate_id=KEY):
    candidate = CapitalCandidate(
        candidate_id=candidate_id,
        expected_return_cents=25000,
        required_capital_cents=5000,
        downside_loss_cents=1000,
        confidence=0.8,
        time_to_revenue_days=14,
        evidence_refs=("capital:evidence:1",),
    )
    policy = CapitalReviewPolicy()
    review = review_capital_candidate(candidate, policy=policy)
    return CapitalReviewRecord(
        review_key="review:test",
        candidate=candidate,
        policy=policy,
        review=review,
        evidence={"source": "test"},
    )


def proposal(**overrides):
    values = {
        "capital_record": record(),
        "tenant_id": TENANT,
        "opportunity_key": KEY,
        "opportunity_id": OPPORTUNITY_ID,
        "prediction_ref": PREDICTION,
        "state_ref": STATE,
        "source_ref": SOURCE,
        "department_keys": ("finance_capital",),
        "target_component": "capital_allocator",
        "action": "review_economic_recommendation",
        "evidence_refs": ("opportunity:evidence:1",),
    }
    values.update(overrides)
    return build_economic_decision_work_proposal(**values)


def test_valid_recommendation_builds_shadow_governed_work_proposal():
    result = proposal()
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["mode"] == "OBSERVE"
    assert result["recommendation_only"] is True
    assert result["shadow_only"] is True
    assert result["execution_authority"] == "none"
    assert result["capital_execution"] is False
    assert result["funds_movement"] is False
    assert result["budget_mutation"] is False

    provenance = result["work_step"]["commercial_decision_provenance"]
    assert provenance["tenant_id"] == TENANT
    assert provenance["opportunity_key"] == KEY
    assert provenance["opportunity_id"] == OPPORTUNITY_ID
    assert provenance["candidate_id"] == KEY
    assert provenance["prediction_ref"] == PREDICTION
    assert provenance["state_ref"] == STATE
    assert provenance["source_ref"] == SOURCE
    assert provenance["shadow_only"] is True
    assert provenance["selection_authority_ref"] is None
    assert provenance["execution_authority"] == "none"


def test_enqueue_uses_existing_department_queue_identity(tmp_path):
    result = proposal()
    item, created = enqueue_economic_decision_work(
        tmp_path,
        plan_id="economic_plan_test",
        proposal=result,
    )
    assert created is True
    assert item.tenant_id == TENANT
    assert item.decision_identity["candidate_id"] == KEY
    assert item.decision_identity["prediction_ref"] == PREDICTION
    assert item.decision_identity["shadow_only"] is True
    assert item.decision_identity["selection_authority_ref"] is None
    assert item.decision_identity["execution_authority"] == "none"
    assert item.decision_identity["execution_performed"] is False
    assert item.decision_identity["execution_ref"] is None
    assert item.decision_identity["causal_eligible"] is False


def test_missing_prediction_ref_fails_closed():
    with pytest.raises(ValueError, match="prediction_ref"):
        proposal(prediction_ref="")


def test_candidate_opportunity_mismatch_fails_closed():
    with pytest.raises(ValueError, match="candidate/opportunity"):
        proposal(capital_record=record(candidate_id="opportunity:other"))


def test_missing_explicit_evidence_fails_closed():
    with pytest.raises(ValueError, match="evidence_refs"):
        proposal(evidence_refs=())


def test_capital_review_cannot_grant_execution_authority():
    base = record()
    bad_review = CapitalReview(
        candidate_id=base.review.candidate_id,
        assessment=base.review.assessment,
        review_eligible=True,
        blockers=(),
        recommendation_only=True,
        execution_authority="execute",
    )
    bad = CapitalReviewRecord(
        review_key=base.review_key,
        candidate=base.candidate,
        policy=base.policy,
        review=bad_review,
        evidence=base.evidence,
    )
    with pytest.raises(ValueError, match="execution authority"):
        proposal(capital_record=bad)


def test_recommendation_only_is_preserved():
    result = proposal()
    assert result["recommendation_only"] is True
    assert result["work_step"]["intelligence_request"]["recommendation_only"] is True


def test_shadow_proposal_cannot_silently_become_executable(tmp_path):
    result = proposal()
    tampered = copy.deepcopy(result)
    tampered["shadow_only"] = False
    with pytest.raises(ValueError, match="shadow_only"):
        enqueue_economic_decision_work(
            tmp_path,
            plan_id="economic_plan_test",
            proposal=tampered,
        )


def test_selection_authority_cannot_be_invented(tmp_path):
    result = proposal()
    tampered = copy.deepcopy(result)
    tampered["work_step"]["commercial_decision_provenance"][
        "selection_authority_ref"
    ] = "authority:invented"
    with pytest.raises(ValueError, match="selection authority"):
        enqueue_economic_decision_work(
            tmp_path,
            plan_id="economic_plan_test",
            proposal=tampered,
        )


def test_tenant_scope_survives_queue_and_conflict_fails_closed(tmp_path):
    result = proposal()
    item, _ = enqueue_economic_decision_work(
        tmp_path,
        plan_id="economic_plan_test",
        proposal=result,
    )
    assert item.tenant_id == TENANT

    tampered = copy.deepcopy(result)
    tampered["work_step"]["commercial_decision_provenance"][
        "tenant_id"
    ] = "tenant:other"

    with pytest.raises(DepartmentWorkQueueError, match="conflicting"):
        enqueue_economic_decision_work(
            tmp_path,
            plan_id="economic_plan_test",
            proposal=tampered,
        )


def test_duplicate_same_identity_is_idempotent(tmp_path):
    result = proposal()
    first, created = enqueue_economic_decision_work(
        tmp_path,
        plan_id="economic_plan_test",
        proposal=result,
    )
    second, created_again = enqueue_economic_decision_work(
        tmp_path,
        plan_id="economic_plan_test",
        proposal=result,
    )
    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert first.decision_identity == second.decision_identity


def test_ineligible_capital_review_fails_closed():
    candidate = CapitalCandidate(
        candidate_id=KEY,
        expected_return_cents=1000,
        required_capital_cents=5000,
        downside_loss_cents=5000,
        confidence=0.1,
        time_to_revenue_days=90,
        evidence_refs=("capital:evidence:bad",),
    )
    policy = CapitalReviewPolicy(minimum_confidence=0.5)
    review = review_capital_candidate(candidate, policy=policy)
    bad = CapitalReviewRecord(
        review_key="review:blocked",
        candidate=candidate,
        policy=policy,
        review=review,
        evidence={"source": "test"},
    )
    assert review.review_eligible is False
    with pytest.raises(ValueError, match="not review eligible"):
        proposal(capital_record=bad)
