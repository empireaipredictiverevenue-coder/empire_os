"""Customer result UX: useful progress without inventing verified sales."""
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_customer_results_experience import (
    review_customer_results_experience,
)
from empire_os.revenue_crm_customer_success import route_customer_success_review
from empire_os.revenue_crm_retention import RevenueCrmRetentionEvidence
from empire_os.revenue_crm_retention_freshness import (
    RevenueCrmRetentionTiming, assess_retention_expansion_freshness,
)

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def assertions(**changes):
    original = {
        "buyer_id": "PRIVATE-BUYER@example.com",
        "buyer_activated": True,
        "buyer_evidence_ref": "private-ref-buyer",
        "payment_verified": True,
        "payment_evidence_ref": "private-ref-payment",
        "fulfilment_delivered": True,
        "fulfilment_evidence_ref": "private-ref-fulfilment",
        "outcome_observed": True,
        "outcome_success_verified": True,
        "outcome_evidence_ref": "private-ref-outcome",
        "buyer_available_capacity": 5,
        "capacity_evidence_ref": "private-ref-capacity",
    }
    original.update(changes)
    return RevenueCrmRetentionEvidence(**original)


def review(evidence, *, dates=None):
    data = dates or {
        "buyer_observed_at": (NOW - timedelta(hours=5)).isoformat(),
        "payment_observed_at": (NOW - timedelta(hours=4)).isoformat(),
        "fulfilment_observed_at": (NOW - timedelta(hours=3)).isoformat(),
        "outcome_observed_at": (NOW - timedelta(hours=2)).isoformat(),
        "capacity_observed_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    freshness = assess_retention_expansion_freshness(
        evidence=evidence, timing=RevenueCrmRetentionTiming(**data),
        now=NOW, max_age_seconds=86400,
    )
    return review_customer_results_experience(
        evidence, freshness, route_customer_success_review(freshness),
    )


def test_all_true_caller_assertions_never_become_actual_customer_results():
    result = review(assertions())
    assert result["status"] == "CUSTOMER_RESULTS_AWAITING_INDEPENDENT_PROOF"
    assert result["source_claim_class"] == "CALLER_SUPPLIED_UNVERIFIED_ASSERTIONS"
    assert result["reported_milestones_with_valid_preview_timing"] == 5
    assert result["independently_verified_milestone_count"] == 0
    assert result["underlying_route_preview"] == "expansion_review"
    assert result["underlying_route_is_verified_customer_result"] is False
    assert result["verified_customer_outcome"] is None
    assert result["verified_realized_revenue_cents"] is None
    assert result["verified_customer_roi"] is None
    assert result["customer_visible_proof_authorized"] is False
    assert result["next_evidence_action"] == "INDEPENDENT_SOURCE_AUTHENTICATION_AND_TENANT_BINDING"
    assert len(result["milestones"]) == 5
    assert all(not x["independently_verified"] for x in result["milestones"])
    assert "PRIVATE-BUYER" not in json.dumps(result)
    assert "private-ref" not in json.dumps(result)


def test_missing_payment_halts_result_ladder_on_original_receipt():
    result = review(assertions(payment_verified=False,payment_evidence_ref=None))
    stage = next(x for x in result["milestones"] if x["stage"]=="payment")
    assert stage["state"] == "MISSING_OR_UNCONFIRMED_ASSERTION"
    assert stage["preview_claim_present"] is False
    assert result["next_evidence_action"] == "RECONCILE_ORIGINAL_PAYMENT_RECEIPT"
    assert result["independently_verified_milestone_count"] == 0


def test_failed_outcome_not_shown_as_success():
    result = review(assertions(outcome_success_verified=False))
    stage = next(x for x in result["milestones"] if x["stage"]=="outcome")
    assert stage["state"] == "UNSUCCESSFUL_OUTCOME_REPORTED_NOT_VERIFIED"
    assert result["next_evidence_action"] == "VERIFY_ORIGINAL_CUSTOMER_OUTCOME"
    assert result["verified_customer_outcome"] is None


def test_stale_temporal_evidence_cannot_become_reviewed_stage():
    evidence = assertions()
    dates = {
        "buyer_observed_at": (NOW - timedelta(days=4)).isoformat(),
        "payment_observed_at": (NOW - timedelta(hours=4)).isoformat(),
        "fulfilment_observed_at": (NOW - timedelta(hours=3)).isoformat(),
        "outcome_observed_at": (NOW - timedelta(hours=2)).isoformat(),
        "capacity_observed_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    result = review(evidence,dates=dates)
    assert result["milestones"][0]["state"] == "STALE_OR_INVALID_ASSERTION"
    assert result["next_evidence_action"] == "CONFIRM_CANONICAL_BUYER_AND_TENANT"


def test_buyer_mismatch_is_contract_hold():
    evidence = assertions()
    freshness = assess_retention_expansion_freshness(
        evidence=evidence,
        timing=RevenueCrmRetentionTiming(
            buyer_observed_at=(NOW-timedelta(hours=5)).isoformat(),
            payment_observed_at=None,fulfilment_observed_at=None,
            outcome_observed_at=None,capacity_observed_at=None,
        ),
        now=NOW,
    )
    route = route_customer_success_review(freshness)
    from dataclasses import replace
    with pytest.raises(ValueError,match="contract untrusted"):
        review_customer_results_experience(
            evidence, freshness, replace(route,buyer_id="not-the-same-buyer"),
        )


def test_existing_crm_api_includes_customer_experience_without_success_claim():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    payload = {
        "buyer_id": "secret-private-person@example.org",
        "buyer_activated": True, "buyer_evidence_ref": "secret-buyer-ref",
        "payment_verified": True, "payment_evidence_ref": "secret-money-ref",
        "fulfilment_delivered": True, "fulfilment_evidence_ref": "secret-delivery-ref",
        "outcome_observed": True,"outcome_success_verified": True,
        "outcome_evidence_ref": "secret-outcome-ref",
        "buyer_available_capacity": 3,"capacity_evidence_ref": "secret-capacity-ref",
        "buyer_observed_at": (NOW-timedelta(hours=5)).isoformat(),
        "payment_observed_at": (NOW-timedelta(hours=4)).isoformat(),
        "fulfilment_observed_at": (NOW-timedelta(hours=3)).isoformat(),
        "outcome_observed_at": (NOW-timedelta(hours=2)).isoformat(),
        "capacity_observed_at": (NOW-timedelta(hours=1)).isoformat(),
        "now_utc": NOW.isoformat(),
    }
    r = TestClient(app).post("/v1/revenue-crm/customer-success/preview",json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["customer_success"]["review_type"] == "expansion_review"
    assert body["source_assertions_independently_verified"] is False
    assert body["customer_visible_result_claim_authorized"] is False
    customer = body["customer_results_experience"]
    assert customer["reported_milestones_with_valid_preview_timing"] == 5
    assert customer["independently_verified_milestone_count"] == 0
    assert customer["customer_visible_proof_authorized"] is False
    assert customer["verified_realized_revenue_cents"] is None
    assert "secret-private" not in json.dumps(customer)
    assert "secret-money-ref" not in json.dumps(customer)
    assert body["execution_authority"] == "none"
