from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.revenue_os_feedback import RevenueOsOutcomeEvidence
from empire_os.revenue_os_learning import assess_revenue_os_learning


NOW = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)


def evidence(**overrides):
    values = {
        "packet_key": "packet-1",
        "outcome_observed": True,
        "revenue_recognized": True,
        "recognized_revenue_cents": 26000,
        "observed_cost_cents": 6000,
        "observed_at": "2026-09-20T16:00:00+00:00",
        "evidence_refs": ("outcome:1", "revenue:1", "cost:1"),
    }
    values.update(overrides)
    return RevenueOsOutcomeEvidence(**values)


def test_fresh_post_packet_outcome_is_learning_ready():
    result = assess_revenue_os_learning(
        evidence=evidence(),
        packet_created_at="2026-09-20T12:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.learning_ready is True
    assert result.blockers == ()
    assert result.outcome_age_seconds == 7200.0
    assert result.feedback.realized_gross_profit_cents == 20000
    assert result.execution_authority == "none"
    assert result.model_weight_mutation is False
    assert result.capital_reallocation is False


def test_outcome_before_packet_is_blocked():
    result = assess_revenue_os_learning(
        evidence=evidence(observed_at="2026-09-20T10:00:00+00:00"),
        packet_created_at="2026-09-20T12:00:00+00:00",
        now=NOW,
        max_age_seconds=43200,
    )
    assert result.learning_ready is False
    assert "outcome_not_after_decision_packet" in result.blockers


def test_stale_outcome_is_blocked():
    result = assess_revenue_os_learning(
        evidence=evidence(observed_at="2026-09-20T08:00:00+00:00"),
        packet_created_at="2026-09-20T07:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.learning_ready is False
    assert "outcome_evidence_stale" in result.blockers


def test_future_outcome_is_blocked():
    result = assess_revenue_os_learning(
        evidence=evidence(observed_at="2026-09-20T18:05:00+00:00"),
        packet_created_at="2026-09-20T12:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.learning_ready is False
    assert "outcome_evidence_from_future" in result.blockers


def test_api_readiness_preview_has_no_execution_authority():
    app = FastAPI()
    app.include_router(create_revenue_os_router())
    response = TestClient(app).post(
        "/v1/revenue-os/feedback/readiness/preview",
        json={
            "packet_key": "packet-1",
            "outcome_observed": True,
            "revenue_recognized": True,
            "recognized_revenue_cents": 26000,
            "observed_cost_cents": 6000,
            "observed_at": "2026-09-20T16:00:00+00:00",
            "evidence_refs": ["outcome:1", "revenue:1", "cost:1"],
            "packet_created_at": "2026-09-20T12:00:00+00:00",
            "now_utc": "2026-09-20T18:00:00+00:00",
            "max_age_seconds": 21600,
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
    assert body["readiness"]["learning_ready"] is True
