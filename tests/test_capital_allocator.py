import pytest

from empire_os.capital_allocator import (
    CapitalCandidate,
    assess_capital_candidate,
    rank_capital_candidates,
)


def candidate(candidate_id, expected, required, downside, confidence, days):
    return CapitalCandidate(
        candidate_id=candidate_id,
        expected_return_cents=expected,
        required_capital_cents=required,
        downside_loss_cents=downside,
        confidence=confidence,
        time_to_revenue_days=days,
        evidence_refs=(f"evidence:{candidate_id}",),
    )


def test_assessment_is_recommendation_only():
    result = assess_capital_candidate(
        candidate("a", 30000, 10000, 2000, 0.8, 30)
    )
    assert result.expected_return_multiple == 3.0
    assert result.downside_ratio == 0.2
    assert result.recommendation_only is True
    assert result.execution_authority == "none"


def test_ranking_is_deterministic_by_score():
    ranked = rank_capital_candidates([
        candidate("slower", 30000, 10000, 1000, 0.8, 90),
        candidate("faster", 30000, 10000, 1000, 0.8, 15),
    ])
    assert ranked[0].candidate_id == "faster"
    assert ranked[0].risk_adjusted_score > ranked[1].risk_adjusted_score


def test_candidate_requires_evidence():
    bad = CapitalCandidate(
        candidate_id="a",
        expected_return_cents=100,
        required_capital_cents=100,
        downside_loss_cents=0,
        confidence=0.5,
        time_to_revenue_days=10,
        evidence_refs=(),
    )
    with pytest.raises(ValueError, match="requires evidence"):
        bad.validate()


def test_invalid_confidence_fails_closed():
    with pytest.raises(ValueError, match="between 0 and 1"):
        candidate("a", 100, 100, 0, 1.1, 10).validate()
