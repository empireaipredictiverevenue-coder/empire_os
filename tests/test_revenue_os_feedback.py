from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.revenue_os_feedback import (
    RevenueOsOutcomeEvidence,
    review_revenue_os_outcome,
)


def evidence(**overrides):
    values = {
        "packet_key": "packet-1",
        "outcome_observed": True,
        "revenue_recognized": True,
        "recognized_revenue_cents": 26000,
        "observed_cost_cents": 6000,
        "observed_at": "2026-09-20T16:00:00+00:00",
        "evidence_refs": (
            "outcome:1",
            "revenue:recognized:1",
            "cost:observed:1",
        ),
    }
    values.update(overrides)
    return RevenueOsOutcomeEvidence(**values)


def test_complete_real_outcome_is_learning_ready_only():
    result = review_revenue_os_outcome(evidence())
    assert result.learning_evidence_complete is True
    assert result.realized_gross_profit_cents == 20000
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.model_weight_mutation is False
    assert result.capital_reallocation is False
    assert result.spend_execution is False


def test_missing_cost_preserves_unknown_profit():
    result = review_revenue_os_outcome(
        evidence(observed_cost_cents=None)
    )
    assert result.learning_evidence_complete is False
    assert result.realized_gross_profit_cents is None
    assert result.blockers == ("observed_cost_evidence_missing",)


def test_unrecognized_revenue_amount_is_rejected():
    try:
        review_revenue_os_outcome(
            evidence(
                revenue_recognized=False,
                recognized_revenue_cents=26000,
            )
        )
    except ValueError as exc:
        assert str(exc) == (
            "recognized revenue amount requires revenue_recognized=true"
        )
    else:
        raise AssertionError("expected ValueError")


def test_feedback_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_revenue_os_router())
    response = TestClient(app).post(
        "/v1/revenue-os/feedback/preview",
        json={
            "packet_key": "packet-1",
            "outcome_observed": True,
            "revenue_recognized": True,
            "recognized_revenue_cents": 26000,
            "observed_cost_cents": 6000,
            "observed_at": "2026-09-20T16:00:00+00:00",
            "evidence_refs": [
                "outcome:1",
                "revenue:recognized:1",
                "cost:observed:1",
            ],
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
    assert body["feedback"]["learning_evidence_complete"] is True
    assert body["feedback"]["realized_gross_profit_cents"] == 20000
