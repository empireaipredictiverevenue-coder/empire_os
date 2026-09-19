import pytest

from empire_os.revenue_exchange import normalise_exchange_snapshot


def test_exchange_snapshot_uses_observed_capacity_and_prices():
    snapshot = normalise_exchange_snapshot({
        "niche": "roofing",
        "metro": "London",
        "qualified_inventory_count": 12,
        "active_buyer_capacity": 6,
        "verified_price_per_lead_cents": [7500, 10000, 12500],
        "observed_at": "2026-09-19T20:00:00+00:00",
        "source": "canonical_exchange_projection",
    })
    assert snapshot.supply_demand_ratio == 2.0
    assert snapshot.observed_price_floor_cents == 7500
    assert snapshot.observed_price_ceiling_cents == 12500


def test_zero_capacity_does_not_invent_ratio():
    snapshot = normalise_exchange_snapshot({
        "niche": "roofing",
        "metro": "London",
        "qualified_inventory_count": 12,
        "active_buyer_capacity": 0,
        "verified_price_per_lead_cents": [],
        "observed_at": "2026-09-19T20:00:00+00:00",
        "source": "canonical_exchange_projection",
    })
    assert snapshot.supply_demand_ratio is None
    assert snapshot.observed_price_floor_cents is None


def test_unverified_or_nonpositive_prices_are_rejected():
    with pytest.raises(ValueError, match="verified prices must be positive"):
        normalise_exchange_snapshot({
            "niche": "roofing",
            "metro": "London",
            "qualified_inventory_count": 1,
            "active_buyer_capacity": 1,
            "verified_price_per_lead_cents": [0],
            "observed_at": "2026-09-19T20:00:00+00:00",
            "source": "canonical_exchange_projection",
        })


def test_missing_market_identity_fails_closed():
    with pytest.raises(ValueError, match="niche, metro"):
        normalise_exchange_snapshot({
            "qualified_inventory_count": 1,
            "active_buyer_capacity": 1,
            "observed_at": "2026-09-19T20:00:00+00:00",
            "source": "canonical_exchange_projection",
        })
