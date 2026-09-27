import pytest

from empire_os.predictive_cloud_formula import (
    compare_cloud_snapshots,
    predictive_cloud_formula,
)


def _factors(**overrides):
    base = {
        "intelligence_quality": 0.9,
        "evidence_coverage": 0.8,
        "signal_freshness": 0.9,
        "calibration_confidence": 0.7,
        "causal_confidence": 0.6,
        "runtime_reliability": 0.95,
        "governance_readiness": 1.0,
        "learning_readiness": 0.75,
        "portfolio_fit": 0.8,
        "scalability_readiness": 0.7,
    }
    base.update(overrides)
    return base


def _constraints(**overrides):
    base = {
        "capacity": True,
        "compliance": True,
        "inventory": True,
        "cash": True,
        "authority": True,
        "fulfilment": True,
    }
    base.update(overrides)
    return base


def test_cloud_formula_preserves_unknown_inputs():
    factors = _factors()
    factors["causal_confidence"] = None
    result = predictive_cloud_formula(
        factors=factors,
        residual_uncertainty=0.2,
        opportunities=[],
        constraints=_constraints(),
    )
    assert result["status"] == "UNAVAILABLE"
    assert "causal_confidence" in result["missing_fields"]
    assert result["unknown_is_zero"] is False
    assert result["actual_revenue"] is False


def test_cloud_formula_builds_current_operating_score():
    result = predictive_cloud_formula(
        factors=_factors(),
        residual_uncertainty=0.2,
        opportunities=[
            {
                "opportunity_key": "opp-1",
                "status": "AVAILABLE",
                "expected_revenue_value_cents": 100000,
            },
            {
                "opportunity_key": "opp-2",
                "status": "UNAVAILABLE",
                "expected_revenue_value_cents": None,
            },
        ],
        constraints=_constraints(),
    )
    assert result["status"] == "AVAILABLE"
    assert 0 < result["cloud_operating_score"] <= 100
    assert (
        result["portfolio"]["portfolio_expected_revenue_value_cents"]
        == 100000
    )
    assert result["future_trend_context"]["available"] is False
    assert result["forward_outlook"]["status"] == "UNAVAILABLE"
    assert result["predicted_revenue_is_verified_revenue"] is False


def test_observed_zero_factor_collapses_cloud_trust_not_unknown():
    result = predictive_cloud_formula(
        factors=_factors(runtime_reliability=0.0),
        residual_uncertainty=0.1,
        opportunities=[],
        constraints=_constraints(),
    )
    assert result["status"] == "AVAILABLE"
    assert result["trust_multiplier"] == 0
    assert result["cloud_operating_score"] == 0
    assert result["weakest_cloud_factor"]["name"] == "runtime_reliability"


def test_constraints_are_separate_from_prediction_math():
    result = predictive_cloud_formula(
        factors=_factors(),
        residual_uncertainty=0.2,
        opportunities=[],
        constraints=_constraints(compliance=False),
    )
    assert result["status"] == "AVAILABLE"
    assert result["constraints"]["state"] == "BLOCKED"
    assert result["constraint_clear_for_review"] is False
    assert "compliance" in result["constraints"]["blockers"]


def test_future_trend_is_specialist_context_not_revenue_truth():
    result = predictive_cloud_formula(
        factors=_factors(),
        residual_uncertainty=0.2,
        opportunities=[{
            "opportunity_key": "opp-1",
            "status": "AVAILABLE",
            "expected_revenue_value_cents": 100000,
        }],
        constraints=_constraints(),
        trend_intelligence={
            "status": "AVAILABLE",
            "future_opportunity_status": "AVAILABLE",
            "direction": "up",
            "velocity_per_day": 2.0,
            "acceleration_per_day": 0.5,
            "persistence": 1.0,
            "trend_confidence": 0.8,
            "trend_opportunity_alignment": 0.75,
            "evidence_refs": ["trend:1", "trend:2"],
        },
    )
    assert result["future_trend_context"]["available"] is True
    assert result["forward_outlook"]["status"] == "AVAILABLE"
    assert 0 < result["forward_outlook"]["cloud_forward_score"] <= 100
    assert result["actual_revenue"] is False
    assert result["future_trend_context"]["forecast_context_only"] is True


def test_cloud_delta_is_descriptive_not_causal():
    result = compare_cloud_snapshots(
        {
            "cloud_operating_score": 50,
            "cloud_adjusted_portfolio_value_cents": 100000,
            "trust_multiplier": 0.7,
            "residual_uncertainty": 0.3,
        },
        {
            "cloud_operating_score": 60,
            "cloud_adjusted_portfolio_value_cents": 120000,
            "trust_multiplier": 0.8,
            "residual_uncertainty": 0.2,
        },
    )
    assert result["status"] == "AVAILABLE"
    assert result["deltas"]["cloud_operating_score"] == 10
    assert result["causal_claim"] is False
