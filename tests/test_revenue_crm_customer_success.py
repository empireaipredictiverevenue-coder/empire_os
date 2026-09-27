from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_customer_success import route_customer_success_review
from empire_os.revenue_crm_retention import (
    RevenueCrmRetentionExpansionReadiness,
)
from empire_os.revenue_crm_retention_freshness import (
    RevenueCrmRetentionFreshness,
)


def freshness(
    *,
    retention=True,
    expansion=True,
    blockers=(),
    base_expansion=True,
):
    base = RevenueCrmRetentionExpansionReadiness(
        buyer_id="buyer-1",
        retention_review_ready=True,
        expansion_review_ready=base_expansion,
        retention_blockers=(),
        expansion_blockers=(),
        evidence_refs=(
            "buyer:1",
            "payment:1",
            "fulfilment:1",
            "outcome:1",
            "capacity:1",
        ),
    )
    return RevenueCrmRetentionFreshness(
        buyer_id="buyer-1",
        retention_fresh_for_review=retention,
        expansion_fresh_for_review=expansion,
        base_readiness=base,
        blockers=tuple(blockers),
        ages_seconds={},
    )


def test_expansion_route_requires_fresh_expansion_readiness():
    route = route_customer_success_review(freshness())
    assert route.available is True
    assert route.review_type == "expansion_review"
    assert route.blockers == ()
    assert route.execution_authority == "none"
    assert route.follow_up_execution is False
    assert route.offer_mutation is False


def test_retention_route_preserves_expansion_only_blocker():
    route = route_customer_success_review(
        freshness(
            expansion=False,
            blockers=("buyer_capacity_not_available",),
            base_expansion=False,
        )
    )
    assert route.available is True
    assert route.review_type == "retention_review"
    assert route.blockers == ("buyer_capacity_not_available",)


def test_stale_retention_has_no_customer_success_route():
    route = route_customer_success_review(
        freshness(
            retention=False,
            expansion=False,
            blockers=("outcome_evidence_stale",),
            base_expansion=False,
        )
    )
    assert route.available is False
    assert route.review_type is None
    assert route.blockers == ("outcome_evidence_stale",)


def test_api_customer_success_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    response = TestClient(app).post(
        "/v1/revenue-crm/customer-success/preview",
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
            "buyer_available_capacity": 3,
            "capacity_evidence_ref": "capacity:1",
            "buyer_observed_at": "2026-09-20T12:00:00+00:00",
            "payment_observed_at": "2026-09-20T13:00:00+00:00",
            "fulfilment_observed_at": "2026-09-20T14:00:00+00:00",
            "outcome_observed_at": "2026-09-20T15:00:00+00:00",
            "capacity_observed_at": "2026-09-20T15:30:00+00:00",
            "now_utc": "2026-09-20T16:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["follow_up_execution"] is False
    assert body["payment_execution"] is False
    assert body["crm_mutation"] is False
    assert body["offer_mutation"] is False
    assert body["customer_success"]["review_type"] == "expansion_review"
