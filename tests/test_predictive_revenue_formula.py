import pytest

from empire_os.predictive_revenue_formula import (
    expected_revenue_value,
    next_best_action_value,
    predictive_revenue_formula,
    revenue_state_snapshot,
)


def test_predictive_revenue_preserves_unknown():
    result = predictive_revenue_formula({"demand": 0.8})
    assert result["status"] == "UNAVAILABLE"
    assert "payment" in result["missing_fields"]
    assert "ltv_cents" in result["missing_fields"]
    assert result["unknown_is_zero"] is False
    assert result["actual_revenue"] is False


def test_predictive_revenue_is_multiplicative():
    inputs = {
        "demand": 0.8,
        "quality": 0.9,
        "enrichment": 1.0,
        "omega_qualification": 0.7,
        "buyer_match": 0.8,
        "outreach": 0.5,
        "conversion": 0.4,
        "terms": 0.9,
        "payment": 0.95,
        "fulfilment": 0.98,
        "ltv_cents": 100000,
    }
    result = predictive_revenue_formula(inputs)
    expected_p = 1.0
    for key, value in inputs.items():
        if key != "ltv_cents":
            expected_p *= value
    assert result["status"] == "AVAILABLE"
    assert result["joint_success_probability"] == pytest.approx(expected_p)
    assert result["predicted_revenue_cents"] == pytest.approx(
        expected_p * 100000
    )


def test_known_zero_is_not_unknown():
    inputs = {
        "demand": 1.0,
        "quality": 1.0,
        "enrichment": 1.0,
        "omega_qualification": 1.0,
        "buyer_match": 1.0,
        "outreach": 1.0,
        "conversion": 0.0,
        "terms": 1.0,
        "payment": 1.0,
        "fulfilment": 1.0,
        "ltv_cents": 250000,
    }
    result = predictive_revenue_formula(inputs)
    assert result["status"] == "AVAILABLE"
    assert result["predicted_revenue_cents"] == 0
    assert result["weakest_factor"]["name"] == "conversion"


def test_erv_is_prediction_not_revenue_truth():
    result = expected_revenue_value({
        "probability_close": 0.5,
        "probability_payment_given_close": 0.9,
        "probability_fulfilment_given_payment": 0.95,
        "ltv_cents": 100000,
        "margin_factor": 0.7,
        "capacity_factor": 0.8,
        "recency_factor": 0.9,
        "confidence": 0.75,
        "time_discount_factor": 0.9,
        "acquisition_cost_cents": 5000,
        "fulfilment_cost_cents": 7000,
        "risk_cost_cents": 1000,
    })
    assert result["status"] == "AVAILABLE"
    assert result["prediction_only"] is True
    assert result["actual_revenue"] is False


def test_settled_is_not_recognized_revenue():
    settled = revenue_state_snapshot(
        "settled",
        {"settlement_evidence_ref": "bsc:tx:abc"},
    )
    assert settled["evidence_complete"] is True
    assert settled["actual_revenue"] is False

    recognized = revenue_state_snapshot(
        "revenue_recognized",
        {"revenue_recognition_evidence_ref": "commercial_event:1"},
    )
    assert recognized["actual_revenue"] is True


def test_next_best_action_uses_expected_incremental_value():
    result = next_best_action_value([
        {
            "action_key": "follow_up",
            "probability_action_changes_outcome": 0.5,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 1000,
            "confidence": 0.8,
        },
        {
            "action_key": "research_more",
            "probability_action_changes_outcome": 0.2,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 500,
            "confidence": 0.8,
        },
    ])
    assert result["recommended_action"]["action_key"] == "follow_up"
    assert result["execution_authority"] == "none"
