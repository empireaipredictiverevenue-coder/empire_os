from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.capital_api import create_capital_router
from empire_os.capital_outcome import (
    CapitalOutcomeEvidence,
    review_capital_outcome,
)


def evidence(**overrides):
    values = {
        "candidate_id": "candidate-1",
        "expected_return_cents": 30000,
        "required_capital_cents": 10000,
        "recognized_revenue_cents": 26000,
        "observed_cost_cents": 6000,
        "observed_at": "2026-09-20T15:00:00+00:00",
        "evidence_refs": (
            "revenue:recognized:1",
            "cost:observed:1",
        ),
    }
    values.update(overrides)
    return CapitalOutcomeEvidence(**values)


def test_realized_return_compares_expected_and_observed_profit():
    result = review_capital_outcome(evidence())
    assert result.outcome_available is True
    assert result.realized_gross_profit_cents == 20000
    assert result.expected_vs_realized_delta_cents == -10000
    assert result.realized_return_multiple == 2.0
    assert result.execution_authority == "none"
    assert result.funds_movement is False
    assert result.budget_mutation is False


def test_missing_revenue_or_cost_stays_unknown():
    result = review_capital_outcome(
        evidence(recognized_revenue_cents=None)
    )
    assert result.outcome_available is False
    assert result.realized_gross_profit_cents is None
    assert result.realized_return_multiple is None
    assert result.blockers == (
        "recognized_revenue_or_cost_evidence_missing",
    )


def test_api_preview_never_moves_funds():
    app = FastAPI()
    app.include_router(create_capital_router())
    response = TestClient(app).post(
        "/v1/capital/outcome/preview",
        json={
            "candidate_id": "candidate-1",
            "expected_return_cents": 30000,
            "required_capital_cents": 10000,
            "recognized_revenue_cents": 26000,
            "observed_cost_cents": 6000,
            "observed_at": "2026-09-20T15:00:00+00:00",
            "evidence_refs": [
                "revenue:recognized:1",
                "cost:observed:1",
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["funds_movement"] is False
    assert body["budget_mutation"] is False
    assert body["outcome_review"]["outcome_available"] is True
