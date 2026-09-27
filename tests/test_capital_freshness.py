from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.capital_api import create_capital_router
from empire_os.capital_freshness import review_capital_outcome_calibration
from empire_os.capital_outcome import CapitalOutcomeEvidence


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def evidence(**overrides):
    values = {
        "candidate_id": "candidate-1",
        "expected_return_cents": 30000,
        "required_capital_cents": 10000,
        "recognized_revenue_cents": 26000,
        "observed_cost_cents": 6000,
        "observed_at": "2026-09-20T11:00:00+00:00",
        "evidence_refs": (
            "revenue:recognized:1",
            "cost:observed:1",
        ),
    }
    values.update(overrides)
    return CapitalOutcomeEvidence(**values)


def test_fresh_realized_outcome_exposes_calibration_only():
    result = review_capital_outcome_calibration(
        evidence(),
        recommendation_recorded_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert result.calibration_available is True
    assert result.expected_return_multiple == 3.0
    assert result.realized_return_multiple == 2.0
    assert result.return_multiple_error == -1.0
    assert result.realized_gross_profit_cents == 20000
    assert result.execution_authority == "none"
    assert result.funds_movement is False
    assert result.budget_mutation is False
    assert result.recommendation_mutation is False


def test_missing_revenue_or_cost_keeps_calibration_unknown():
    result = review_capital_outcome_calibration(
        evidence(recognized_revenue_cents=None),
        recommendation_recorded_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert result.calibration_available is False
    assert result.realized_return_multiple is None
    assert result.return_multiple_error is None
    assert (
        "recognized_revenue_or_cost_evidence_missing"
        in result.blockers
    )


def test_outcome_before_recommendation_is_blocked():
    result = review_capital_outcome_calibration(
        evidence(observed_at="2026-09-19T11:00:00+00:00"),
        recommendation_recorded_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert result.calibration_available is False
    assert result.outcome_after_recommendation is False
    assert "outcome_not_after_recommendation" in result.blockers


def test_stale_and_future_outcomes_are_explicit():
    stale = review_capital_outcome_calibration(
        evidence(observed_at="2026-09-18T12:00:00+00:00"),
        recommendation_recorded_at="2026-09-17T12:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    future = review_capital_outcome_calibration(
        evidence(observed_at="2026-09-20T12:05:00+00:00"),
        recommendation_recorded_at="2026-09-19T12:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert "outcome_evidence_stale" in stale.blockers
    assert "outcome_evidence_future" in future.blockers


def test_api_preview_never_mutates_capital():
    app = FastAPI()
    app.include_router(create_capital_router())
    response = TestClient(app).post(
        "/v1/capital/outcome/calibration/preview",
        json={
            "candidate_id": "candidate-1",
            "expected_return_cents": 30000,
            "required_capital_cents": 10000,
            "recognized_revenue_cents": 26000,
            "observed_cost_cents": 6000,
            "observed_at": "2026-09-20T11:00:00+00:00",
            "evidence_refs": [
                "revenue:recognized:1",
                "cost:observed:1",
            ],
            "recommendation_recorded_at": "2026-09-19T12:00:00+00:00",
            "now_utc": "2026-09-20T12:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["funds_movement"] is False
    assert body["budget_mutation"] is False
    assert body["recommendation_mutation"] is False
    assert body["calibration"]["calibration_available"] is True
    assert body["calibration"]["return_multiple_error"] == -1.0


def test_api_rejects_naive_now_timestamp():
    app = FastAPI()
    app.include_router(create_capital_router())
    response = TestClient(app).post(
        "/v1/capital/outcome/calibration/preview",
        json={
            "candidate_id": "candidate-1",
            "expected_return_cents": 30000,
            "required_capital_cents": 10000,
            "recognized_revenue_cents": 26000,
            "observed_cost_cents": 6000,
            "observed_at": "2026-09-20T11:00:00+00:00",
            "evidence_refs": ["revenue:1", "cost:1"],
            "recommendation_recorded_at": "2026-09-19T12:00:00+00:00",
            "now_utc": "2026-09-20T12:00:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
