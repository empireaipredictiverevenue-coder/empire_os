from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.digital_twin_api import create_digital_twin_router
from empire_os.digital_twin_calibration import DigitalTwinCalibrationReadiness
from empire_os.digital_twin_feedback import build_digital_twin_model_review_feedback
from empire_os.digital_twin_realization import ScenarioRealizationReview


def realization(**overrides):
    values = {
        "scenario_id": "scenario-1",
        "projected_served_units": 10,
        "observed_served_units": 12,
        "served_unit_error": 2,
        "projected_revenue_cents": 10000,
        "observed_revenue_cents": 12000,
        "revenue_error_cents": 2000,
        "revenue_error_ratio": 0.2,
        "revenue_comparison_available": True,
        "blockers": (),
    }
    values.update(overrides)
    return ScenarioRealizationReview(**values)


def calibration(**overrides):
    values = {
        "scenario_id": "scenario-1",
        "ready_for_model_review": True,
        "outcome_age_seconds": 3600.0,
        "blockers": (),
        "realization": realization(),
    }
    values.update(overrides)
    return DigitalTwinCalibrationReadiness(**values)


def test_ready_calibration_becomes_feedback_not_weight_mutation():
    feedback = build_digital_twin_model_review_feedback(calibration())
    assert feedback.eligible_for_model_review is True
    assert feedback.served_unit_bias == "under_predicted"
    assert feedback.revenue_bias == "under_predicted"
    assert feedback.revenue_error_cents == 2000
    assert feedback.simulation_only is True
    assert feedback.actual_revenue is False
    assert feedback.model_weight_mutation is False
    assert feedback.execution_authority == "none"


def test_negative_error_is_classified_as_over_prediction():
    item = calibration(
        realization=realization(
            served_unit_error=-3,
            revenue_error_cents=-2500,
            revenue_error_ratio=-0.25,
        )
    )
    feedback = build_digital_twin_model_review_feedback(item)
    assert feedback.served_unit_bias == "over_predicted"
    assert feedback.revenue_bias == "over_predicted"


def test_blocked_calibration_stays_ineligible():
    item = calibration(
        ready_for_model_review=False,
        blockers=("outcome_evidence_stale",),
    )
    feedback = build_digital_twin_model_review_feedback(item)
    assert feedback.eligible_for_model_review is False
    assert "calibration_not_ready_for_model_review" in feedback.blockers
    assert "outcome_evidence_stale" in feedback.blockers


def test_missing_revenue_comparison_keeps_revenue_bias_unknown():
    item = calibration(
        ready_for_model_review=False,
        blockers=("recognized_revenue_comparison_unavailable",),
        realization=realization(
            observed_revenue_cents=None,
            revenue_error_cents=None,
            revenue_error_ratio=None,
            revenue_comparison_available=False,
            blockers=("recognized_revenue_evidence_missing",),
        ),
    )
    feedback = build_digital_twin_model_review_feedback(item)
    assert feedback.revenue_bias == "unknown"
    assert feedback.revenue_error_cents is None


def test_api_feedback_preview_never_mutates_model_or_executes():
    app = FastAPI()
    app.include_router(create_digital_twin_router())
    response = TestClient(app).post(
        "/v1/digital-twin/realization/feedback/preview",
        json={
            "baseline": {
                "niche": "roofing",
                "metro": "Austin, TX",
                "observed_demand_units": 10,
                "observed_capacity_units": 10,
                "observed_price_per_unit_cents": 1000,
                "observed_at": "2026-09-20T12:00:00+00:00",
                "evidence_ref": "baseline:1",
            },
            "scenario": {
                "scenario_id": "scenario-1",
                "demand_multiplier": 1.0,
                "capacity_multiplier": 1.0,
                "price_multiplier": 1.0,
            },
            "observed_served_units": 12,
            "observed_revenue_cents": 12000,
            "revenue_recognized": True,
            "observed_at": "2026-09-20T15:00:00+00:00",
            "evidence_refs": ["outcome:1", "revenue:recognized:1"],
            "now_utc": "2026-09-20T16:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["simulation_only"] is True
    assert body["actual_revenue"] is False
    assert body["execution_authority"] == "none"
    assert body["model_weight_mutation"] is False
    assert body["capital_execution"] is False
    assert body["campaign_execution"] is False
    assert body["pricing_execution"] is False
    assert body["feedback"]["eligible_for_model_review"] is True
