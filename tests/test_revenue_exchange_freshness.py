from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_api import create_revenue_exchange_router
from empire_os.revenue_exchange_freshness import review_exchange_drift
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


def reconciliation(current, **overrides):
    values = {
        "inventory_count": current.qualified_inventory_count,
        "buyer_capacity": current.active_buyer_capacity,
        "verified_prices_cents": current.verified_price_per_lead_cents,
        "evidence_refs": ("exchange:canonical:1",),
    }
    values.update(overrides)
    return reconcile_exchange_snapshot(
        current,
        ExchangeEvidenceSnapshot(**values),
    )


def test_reconciled_fresh_market_produces_observed_drift():
    baseline = snapshot(
        qualified_inventory_count=10,
        active_buyer_capacity=10,
        verified_price_per_lead_cents=(10000, 14000),
        observed_at="2026-09-19T12:00:00+00:00",
    )
    current = snapshot()
    result = review_exchange_drift(
        baseline=baseline,
        current=current,
        reconciliation=reconciliation(current),
        now=NOW,
    )
    assert result.drift.drift_available is True
    assert result.drift.inventory_delta == 2
    assert result.drift.buyer_capacity_delta == -2
    assert result.drift.supply_demand_ratio_delta == 0.5
    assert result.drift.price_floor_delta_cents == 2000
    assert result.drift.price_ceiling_delta_cents == 1000
    assert result.drift.verified_price_set_changed is True
    assert result.drift.allocation_authority == "none"
    assert result.drift.settlement_authority == "none"


def test_stale_current_snapshot_blocks_drift():
    baseline = snapshot(observed_at="2026-09-19T12:00:00+00:00")
    current = snapshot(observed_at="2026-09-20T08:00:00+00:00")
    result = review_exchange_drift(
        baseline=baseline,
        current=current,
        reconciliation=reconciliation(current),
        now=NOW,
        max_current_age_seconds=7200,
    )
    assert result.drift.drift_available is False
    assert "current_snapshot_stale" in result.drift.blockers


def test_unreconciled_current_snapshot_blocks_drift():
    baseline = snapshot(observed_at="2026-09-19T12:00:00+00:00")
    current = snapshot()
    result = review_exchange_drift(
        baseline=baseline,
        current=current,
        reconciliation=reconciliation(current, inventory_count=11),
        now=NOW,
    )
    assert result.drift.drift_available is False
    assert "current_snapshot_not_reconciled" in result.drift.blockers
    assert (
        "reconciliation_inventory_count_mismatch"
        in result.drift.blockers
    )


def test_baseline_must_be_older_than_current():
    current = snapshot(observed_at="2026-09-20T11:00:00+00:00")
    baseline = snapshot(observed_at="2026-09-20T11:30:00+00:00")
    result = review_exchange_drift(
        baseline=baseline,
        current=current,
        reconciliation=reconciliation(current),
        now=NOW,
    )
    assert result.drift.drift_available is False
    assert "baseline_not_older_than_current" in result.drift.blockers


def test_market_identity_mismatch_is_rejected():
    baseline = snapshot(
        metro="Manchester",
        observed_at="2026-09-19T12:00:00+00:00",
    )
    current = snapshot()
    with pytest.raises(
        ValueError,
        match="matching market identity",
    ):
        review_exchange_drift(
            baseline=baseline,
            current=current,
            reconciliation=reconciliation(current),
            now=NOW,
        )


def test_missing_price_sets_do_not_invent_price_drift():
    baseline = snapshot(
        verified_price_per_lead_cents=(),
        observed_at="2026-09-19T12:00:00+00:00",
    )
    current = snapshot(verified_price_per_lead_cents=())
    result = review_exchange_drift(
        baseline=baseline,
        current=current,
        reconciliation=reconciliation(current),
        now=NOW,
    )
    assert result.drift.drift_available is True
    assert result.drift.price_floor_delta_cents is None
    assert result.drift.price_ceiling_delta_cents is None
    assert result.drift.verified_price_set_changed is None


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_revenue_exchange_router())
    response = TestClient(app).post(
        "/v1/revenue-exchange/drift/preview",
        json={
            "baseline_row": {
                "niche": "roofing",
                "metro": "London",
                "qualified_inventory_count": 10,
                "active_buyer_capacity": 10,
                "verified_price_per_lead_cents": [10000, 14000],
                "observed_at": "2026-09-19T12:00:00+00:00",
                "source": "canonical_market_snapshot",
            },
            "current_row": {
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
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["allocation_authority"] == "none"
    assert body["pricing_authority"] == "none"
    assert body["settlement_authority"] == "none"
    assert body["review"]["drift"]["drift_available"] is True


def test_api_rejects_naive_now_timestamp():
    app = FastAPI()
    app.include_router(create_revenue_exchange_router())
    response = TestClient(app).post(
        "/v1/revenue-exchange/drift/preview",
        json={
            "baseline_row": {
                "niche": "roofing",
                "metro": "London",
                "qualified_inventory_count": 10,
                "active_buyer_capacity": 10,
                "verified_price_per_lead_cents": [10000],
                "observed_at": "2026-09-19T12:00:00+00:00",
                "source": "canonical_market_snapshot",
            },
            "current_row": {
                "niche": "roofing",
                "metro": "London",
                "qualified_inventory_count": 12,
                "active_buyer_capacity": 8,
                "verified_price_per_lead_cents": [12000],
                "observed_at": "2026-09-20T11:00:00+00:00",
                "source": "canonical_market_snapshot",
            },
            "inventory_count": 12,
            "buyer_capacity": 8,
            "verified_prices_cents": [12000],
            "evidence_refs": ["exchange:canonical:1"],
            "now_utc": "2026-09-20T12:00:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
