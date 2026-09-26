from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.revenue_os_feedback import RevenueOsLearningFeedback
from empire_os.revenue_os_learning import RevenueOsLearningReadiness
from empire_os.revenue_os_model_review import (
    build_revenue_os_model_review_feedback,
)


def readiness(*, gp=20000, ready=True, blockers=()):
    feedback = RevenueOsLearningFeedback(
        packet_key="packet-1",
        outcome_observed=True,
        revenue_recognized=True,
        recognized_revenue_cents=50000,
        observed_cost_cents=(
            None if gp is None else (30000 if gp == 20000 else 50000 - gp)
        ),
        realized_gross_profit_cents=gp,
        learning_evidence_complete=ready,
        blockers=tuple(blockers),
    )
    return RevenueOsLearningReadiness(
        packet_key="packet-1",
        learning_ready=ready,
        outcome_age_seconds=3600.0,
        feedback=feedback,
        blockers=tuple(blockers),
    )


def test_learning_ready_positive_gp_is_model_review_feedback_only():
    result = build_revenue_os_model_review_feedback(readiness())
    assert result.eligible_for_model_review is True
    assert result.profitability_state == "positive_realized_gp"
    assert result.realized_gross_profit_cents == 20000
    assert result.side_effects == "none"
    assert result.execution_authority == "none"
    assert result.model_weight_mutation is False
    assert result.capital_reallocation is False
    assert result.spend_execution is False
    assert result.payment_execution is False


def test_negative_and_breakeven_profitability_are_descriptive_only():
    negative = build_revenue_os_model_review_feedback(readiness(gp=-5000))
    breakeven = build_revenue_os_model_review_feedback(readiness(gp=0))
    assert negative.profitability_state == "negative_realized_gp"
    assert breakeven.profitability_state == "breakeven_realized_gp"
    assert negative.capital_reallocation is False
    assert breakeven.model_weight_mutation is False


def test_blocked_learning_stays_ineligible_and_unknown_when_gp_missing():
    result = build_revenue_os_model_review_feedback(
        readiness(
            gp=None,
            ready=False,
            blockers=("recognized_revenue_evidence_missing",),
        )
    )
    assert result.eligible_for_model_review is False
    assert result.profitability_state == "unknown"
    assert "revenue_os_learning_not_ready_for_model_review" in result.blockers
    assert "recognized_revenue_evidence_missing" in result.blockers


def test_api_model_review_preview_cannot_execute_or_mutate():
    app = FastAPI()
    app.include_router(create_revenue_os_router())
    response = TestClient(app).post(
        "/v1/revenue-os/feedback/model-review/preview",
        json={
            "packet_key": "packet-1",
            "outcome_observed": True,
            "revenue_recognized": True,
            "recognized_revenue_cents": 50000,
            "observed_cost_cents": 30000,
            "observed_at": "2026-09-20T15:00:00+00:00",
            "evidence_refs": [
                "outcome:1",
                "revenue:recognized:1",
                "cost:1",
            ],
            "packet_created_at": "2026-09-20T12:00:00+00:00",
            "now_utc": "2026-09-20T16:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["model_weight_mutation"] is False
    assert body["capital_reallocation"] is False
    assert body["spend_execution"] is False
    assert body["outreach_execution"] is False
    assert body["payment_execution"] is False
    assert body["allocation_execution"] is False
    assert body["deployment_execution"] is False
    assert body["feedback"]["eligible_for_model_review"] is True
    assert body["feedback"]["profitability_state"] == "positive_realized_gp"
