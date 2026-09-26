from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_api import create_revenue_exchange_router
from empire_os.revenue_exchange_reconciliation import (
    ExchangeEvidenceSnapshot,
    reconcile_exchange_snapshot,
)


def snapshot():
    return ExchangeSnapshot(
        niche="roofing",
        metro="London",
        qualified_inventory_count=12,
        active_buyer_capacity=8,
        verified_price_per_lead_cents=(12000, 15000),
        observed_at="2026-09-19T21:00:00+00:00",
        source="canonical_market_snapshot",
    )


def evidence(**overrides):
    values = {
        "inventory_count": 12,
        "buyer_capacity": 8,
        "verified_prices_cents": (12000, 15000),
        "evidence_refs": (
            "inventory:canonical_prospects",
            "capacity:canonical_buyers",
            "pricing:verified_terms",
        ),
    }
    values.update(overrides)
    return ExchangeEvidenceSnapshot(**values)


def test_exact_canonical_reconciliation_is_review_ready():
    result = reconcile_exchange_snapshot(snapshot(), evidence())
    assert result.review_ready is True
    assert result.inventory_reconciled is True
    assert result.capacity_reconciled is True
    assert result.pricing_reconciled is True
    assert result.blockers == ()
    assert result.allocation_authority == "none"


def test_inventory_mismatch_blocks_review():
    result = reconcile_exchange_snapshot(
        snapshot(),
        evidence(inventory_count=11),
    )
    assert result.review_ready is False
    assert "inventory_count_mismatch" in result.blockers


def test_missing_capacity_evidence_stays_explicit():
    result = reconcile_exchange_snapshot(
        snapshot(),
        evidence(buyer_capacity=None),
    )
    assert result.review_ready is False
    assert "buyer_capacity_evidence_missing" in result.blockers


def test_price_mismatch_blocks_review():
    result = reconcile_exchange_snapshot(
        snapshot(),
        evidence(verified_prices_cents=(12000,)),
    )
    assert result.review_ready is False
    assert "verified_price_mismatch" in result.blockers


def test_preview_endpoint_remains_non_executing():
    app = FastAPI()
    app.include_router(create_revenue_exchange_router())
    client = TestClient(app)
    response = client.post(
        "/v1/revenue-exchange/reconciliation/preview",
        json={
            "row": {
                "niche": "roofing",
                "metro": "London",
                "qualified_inventory_count": 12,
                "active_buyer_capacity": 8,
                "verified_price_per_lead_cents": [12000, 15000],
                "observed_at": "2026-09-19T21:00:00+00:00",
                "source": "canonical_market_snapshot",
            },
            "inventory_count": 12,
            "buyer_capacity": 8,
            "verified_prices_cents": [12000, 15000],
            "evidence_refs": [
                "inventory:canonical_prospects",
                "capacity:canonical_buyers",
                "pricing:verified_terms",
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reconciliation"]["review_ready"] is True
    assert body["allocation_authority"] == "none"
    assert body["pricing_authority"] == "none"
    assert body["settlement_authority"] == "none"
