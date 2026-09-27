from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_retention import RevenueCrmRetentionEvidence
from empire_os.revenue_crm_retention_freshness import (
    RevenueCrmRetentionTiming,
    assess_retention_expansion_freshness,
)


NOW = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)


def evidence(**overrides):
    values = {
        "buyer_id": "buyer-1",
        "buyer_activated": True,
        "buyer_evidence_ref": "buyer:1",
        "payment_verified": True,
        "payment_evidence_ref": "payment:1",
        "fulfilment_delivered": True,
        "fulfilment_evidence_ref": "fulfilment:1",
        "outcome_observed": True,
        "outcome_success_verified": True,
        "outcome_evidence_ref": "outcome:1",
        "buyer_available_capacity": 4,
        "capacity_evidence_ref": "capacity:1",
    }
    values.update(overrides)
    return RevenueCrmRetentionEvidence(**values)


def timing(**overrides):
    values = {
        "buyer_observed_at": "2026-09-20T12:00:00+00:00",
        "payment_observed_at": "2026-09-20T13:00:00+00:00",
        "fulfilment_observed_at": "2026-09-20T14:00:00+00:00",
        "outcome_observed_at": "2026-09-20T15:00:00+00:00",
        "capacity_observed_at": "2026-09-20T16:00:00+00:00",
    }
    values.update(overrides)
    return RevenueCrmRetentionTiming(**values)


def test_fresh_chronological_evidence_is_review_ready():
    result = assess_retention_expansion_freshness(
        evidence=evidence(),
        timing=timing(),
        now=NOW,
        max_age_seconds=86400,
    )
    assert result.retention_fresh_for_review is True
    assert result.expansion_fresh_for_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.follow_up_execution is False


def test_payment_before_buyer_activation_blocks_review():
    result = assess_retention_expansion_freshness(
        evidence=evidence(),
        timing=timing(
            payment_observed_at="2026-09-20T11:00:00+00:00",
        ),
        now=NOW,
    )
    assert result.retention_fresh_for_review is False
    assert result.expansion_fresh_for_review is False
    assert "payment_before_buyer" in result.blockers


def test_stale_outcome_blocks_retention_and_expansion():
    result = assess_retention_expansion_freshness(
        evidence=evidence(),
        timing=timing(
            buyer_observed_at="2026-09-19T02:00:00+00:00",
            payment_observed_at="2026-09-19T03:00:00+00:00",
            fulfilment_observed_at="2026-09-19T04:00:00+00:00",
            outcome_observed_at="2026-09-19T05:00:00+00:00",
            capacity_observed_at="2026-09-20T16:00:00+00:00",
        ),
        now=NOW,
        max_age_seconds=86400,
    )
    assert result.retention_fresh_for_review is False
    assert result.expansion_fresh_for_review is False
    assert "outcome_evidence_stale" in result.blockers


def test_missing_capacity_only_blocks_expansion():
    result = assess_retention_expansion_freshness(
        evidence=evidence(
            buyer_available_capacity=None,
            capacity_evidence_ref=None,
        ),
        timing=timing(capacity_observed_at=None),
        now=NOW,
    )
    assert result.retention_fresh_for_review is True
    assert result.expansion_fresh_for_review is False
    assert "verified_buyer_capacity_missing" in result.blockers


def test_api_preview_never_executes_follow_up_or_payment():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    response = TestClient(app).post(
        "/v1/revenue-crm/retention-expansion/freshness/preview",
        json={
            "buyer_id": "buyer-1",
            "buyer_activated": True,
            "buyer_evidence_ref": "buyer:1",
            "payment_verified": True,
            "payment_evidence_ref": "payment:1",
            "fulfilment_delivered": True,
            "fulfilment_evidence_ref": "fulfilment:1",
            "outcome_observed": True,
            "outcome_success_verified": True,
            "outcome_evidence_ref": "outcome:1",
            "buyer_available_capacity": 4,
            "capacity_evidence_ref": "capacity:1",
            "buyer_observed_at": "2026-09-20T12:00:00+00:00",
            "payment_observed_at": "2026-09-20T13:00:00+00:00",
            "fulfilment_observed_at": "2026-09-20T14:00:00+00:00",
            "outcome_observed_at": "2026-09-20T15:00:00+00:00",
            "capacity_observed_at": "2026-09-20T16:00:00+00:00",
            "now_utc": "2026-09-20T18:00:00+00:00",
            "max_age_seconds": 86400,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
    assert body["follow_up_execution"] is False
    assert body["payment_execution"] is False
    assert body["crm_mutation"] is False
    assert body["offer_mutation"] is False
    assert body["freshness"]["retention_fresh_for_review"] is True
    assert body["freshness"]["expansion_fresh_for_review"] is True
