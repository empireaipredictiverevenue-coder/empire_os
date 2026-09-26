from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.capital_api import create_capital_router
from empire_os.capital_feedback import build_capital_model_review_feedback
from empire_os.capital_freshness import CapitalOutcomeCalibration


def calibration(**overrides):
    values = {
        "candidate_id": "candidate-1",
        "outcome_age_seconds": 3600.0,
        "freshness": "fresh",
        "outcome_after_recommendation": True,
        "outcome_available": True,
        "expected_return_multiple": 3.0,
        "realized_return_multiple": 3.5,
        "return_multiple_error": 0.5,
        "realized_gross_profit_cents": 35000,
        "calibration_available": True,
        "blockers": (),
    }
    values.update(overrides)
    return CapitalOutcomeCalibration(**values)


def test_ready_calibration_yields_non_mutating_model_review_feedback():
    feedback = build_capital_model_review_feedback(calibration())
    assert feedback.eligible_for_model_review is True
    assert feedback.expectation_bias == "under_estimated_return"
    assert feedback.return_multiple_error == 0.5
    assert feedback.realized_gross_profit_cents == 35000
    assert feedback.execution_authority == "none"
    assert feedback.model_weight_mutation is False
    assert feedback.recommendation_mutation is False
    assert feedback.funds_movement is False
    assert feedback.budget_mutation is False


def test_negative_error_means_expected_return_was_overestimated():
    feedback = build_capital_model_review_feedback(
        calibration(
            realized_return_multiple=2.0,
            return_multiple_error=-1.0,
        )
    )
    assert feedback.expectation_bias == "over_estimated_return"


def test_blocked_calibration_stays_ineligible_and_unknown_when_no_error():
    feedback = build_capital_model_review_feedback(
        calibration(
            calibration_available=False,
            realized_return_multiple=None,
            return_multiple_error=None,
            realized_gross_profit_cents=None,
            blockers=("recognized_revenue_evidence_missing",),
        )
    )
    assert feedback.eligible_for_model_review is False
    assert feedback.expectation_bias == "unknown"
    assert "capital_calibration_not_ready_for_model_review" in feedback.blockers


def test_api_feedback_preview_never_moves_funds_or_mutates_models():
    app = FastAPI()
    app.include_router(create_capital_router())
    response = TestClient(app).post(
        "/v1/capital/outcome/feedback/preview",
        json={
            "candidate_id": "candidate-1",
            "expected_return_cents": 30000,
            "required_capital_cents": 10000,
            "recognized_revenue_cents": 40000,
            "observed_cost_cents": 5000,
            "observed_at": "2026-09-20T15:00:00+00:00",
            "evidence_refs": ["revenue:recognized:1", "cost:1"],
            "recommendation_recorded_at": "2026-09-20T12:00:00+00:00",
            "now_utc": "2026-09-20T16:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["model_weight_mutation"] is False
    assert body["recommendation_mutation"] is False
    assert body["funds_movement"] is False
    assert body["budget_mutation"] is False
    assert body["feedback"]["eligible_for_model_review"] is True
