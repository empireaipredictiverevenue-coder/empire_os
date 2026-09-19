from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_allocation_readiness import (
    assess_exchange_allocation_readiness,
)
from empire_os.revenue_exchange_api import create_revenue_exchange_router
from empire_os.revenue_exchange_reconciliation import (
    ExchangeEvidenceSnapshot,
    reconcile_exchange_snapshot,
)


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def snapshot(**overrides):
    values = {
        "niche": "roofing",
        "metro": "London",
        "qualified_inventory_count": 12,
        "active_buyer_capacity": 8,
        "verified_price_per_lead_cents": (12000, 15000),
        "observed_at": "2026-09-20T11:00:00+00:00",
        "source": "canonical_market_snapshot",
    }
    values.update(overrides)
    return ExchangeSnapshot(**values)


def reconciliation(item, **overrides):
    values = {
        "inventory_count": item.qualified_inventory_count,
        "buyer_capacity": item.active_buyer_capacity,
        "verified_prices_cents": item.verified_price_per_lead_cents,
        "evidence_refs": ("exchange:canonical:1",),
    }
    values.update(overrides)
    return reconcile_exchange_snapshot(
        item,
        ExchangeEvidenceSnapshot(**values),
    )


def test_fresh_reconciled_market_is_operator_review_ready_only():
    item = snapshot()
    result = assess_exchange_allocation_readiness(
        snapshot=item,
        reconciliation=reconciliation(item),
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.ready_for_operator_allocation_review is True
    assert result.blockers == ()
    assert result.allocation_authority == "none"
    assert result.pricing_authority == "none"
    assert result.settlement_authority == "none"
    assert result.exclusivity_authority == "none"


def test_zero_capacity_blocks_allocation_review():
    item = snapshot(active_buyer_capacity=0)
    result = assess_exchange_allocation_readiness(
        snapshot=item,
        reconciliation=reconciliation(item),
        now=NOW,
    )
    assert result.ready_for_operator_allocation_review is False
    assert "verified_buyer_capacity_not_available" in result.blockers


def test_stale_snapshot_blocks_allocation_review():
    item = snapshot(observed_at="2026-09-20T08:00:00+00:00")
    result = assess_exchange_allocation_readiness(
        snapshot=item,
        reconciliation=reconciliation(item),
        now=NOW,
        max_age_seconds=7200,
    )
    assert result.ready_for_operator_allocation_review is False
    assert "current_snapshot_stale" in result.blockers


def test_reconciliation_mismatch_blocks_allocation_review():
    item = snapshot()
    result = assess_exchange_allocation_readiness(
        snapshot=item,
        reconciliation=reconciliation(item, inventory_count=11),
        now=NOW,
    )
    assert result.ready_for_operator_allocation_review is False
    assert "inventory_count_mismatch" in result.blockers
    assert "canonical_reconciliation_not_ready" in result.blockers


def test_api_preview_never_allocates_or_settles():
    app = FastAPI()
    app.include_router(create_revenue_exchange_router())
    response = TestClient(app).post(
        "/v1/revenue-exchange/allocation/readiness/preview",
        json={
            "row": {
                "niche": "roofing",
                "metro": "London",
                "qualified_inventory_count": 12,
                "active_buyer_capacity": 8,
                "verified_price_per_lead_cents": [12000, 15000],
                "observed_at": "2026-09-20T11:00:00+00:00",
                "source": "canonical_market_snapshot",
            },
            "inventory_count": 12,
            "buyer_capacity": 8,
            "verified_prices_cents": [12000, 15000],
            "evidence_refs": ["exchange:canonical:1"],
            "now_utc": "2026-09-20T12:00:00+00:00",
            "max_age_seconds": 7200,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["allocation_authority"] == "none"
    assert body["settlement_authority"] == "none"
    assert body["pricing_authority"] == "none"
    assert body["exclusivity_authority"] == "none"
    assert body["readiness"]["ready_for_operator_allocation_review"] is True
