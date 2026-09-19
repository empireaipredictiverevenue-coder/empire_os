import pytest

from empire_os.capital_allocator import CapitalCandidate
from empire_os.capital_review import (
    CapitalReviewPolicy,
    review_capital_candidate,
)


def candidate(
    *,
    confidence=0.8,
    expected=30000,
    required=10000,
    downside=2000,
    days=30,
):
    return CapitalCandidate(
        candidate_id="candidate-1",
        expected_return_cents=expected,
        required_capital_cents=required,
        downside_loss_cents=downside,
        confidence=confidence,
        time_to_revenue_days=days,
        evidence_refs=("evidence:1",),
    )


def test_candidate_can_be_eligible_for_operator_review_only():
    result = review_capital_candidate(candidate())
    assert result.review_eligible is True
    assert result.blockers == ()
    assert result.recommendation_only is True
    assert result.execution_authority == "none"


def test_low_confidence_blocks_review():
    result = review_capital_candidate(
        candidate(confidence=0.2),
        policy=CapitalReviewPolicy(minimum_confidence=0.5),
    )
    assert result.review_eligible is False
    assert "confidence_below_policy" in result.blockers


def test_high_downside_blocks_review():
    result = review_capital_candidate(
        candidate(downside=15000),
        policy=CapitalReviewPolicy(maximum_downside_ratio=1.0),
    )
    assert result.review_eligible is False
    assert "downside_above_policy" in result.blockers


def test_low_risk_adjusted_score_blocks_review():
    result = review_capital_candidate(
        candidate(
            confidence=0.5,
            expected=10000,
            required=10000,
            downside=9000,
            days=120,
        ),
        policy=CapitalReviewPolicy(
            minimum_risk_adjusted_score=0.0,
        ),
    )
    assert result.review_eligible is False
    assert "risk_adjusted_score_below_policy" in result.blockers


def test_invalid_policy_fails_closed():
    with pytest.raises(ValueError, match="between 0 and 1"):
        review_capital_candidate(
            candidate(),
            policy=CapitalReviewPolicy(minimum_confidence=1.5),
        )
