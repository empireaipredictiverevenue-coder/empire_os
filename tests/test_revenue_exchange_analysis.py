from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_analysis import assess_exchange_market


def snapshot(inventory, capacity, prices=(7500, 10000)):
    return ExchangeSnapshot(
        niche="roofing",
        metro="London",
        qualified_inventory_count=inventory,
        active_buyer_capacity=capacity,
        verified_price_per_lead_cents=prices,
        observed_at="2026-09-19T23:10:00+00:00",
        source="canonical_exchange_projection",
    )


def test_inventory_heavy_market_is_observed_not_executed():
    result = assess_exchange_market(snapshot(20, 10))
    assert result.market_state == "inventory_heavy"
    assert result.supply_demand_ratio == 2.0
    assert result.allocation_authority == "none"
    assert result.settlement_authority == "none"
    assert result.pricing_authority == "none"


def test_capacity_heavy_market_is_identified():
    result = assess_exchange_market(snapshot(5, 10))
    assert result.market_state == "capacity_heavy"
    assert result.supply_demand_ratio == 0.5


def test_balanced_range_is_identified():
    result = assess_exchange_market(snapshot(10, 10))
    assert result.market_state == "balanced_observed_range"
    assert result.review_reason == (
        "observed_inventory_and_capacity_are_within_balance_band"
    )


def test_zero_capacity_stays_explicit():
    result = assess_exchange_market(snapshot(10, 0))
    assert result.market_state == "no_verified_capacity"
    assert result.supply_demand_ratio is None


def test_zero_inventory_stays_explicit():
    result = assess_exchange_market(snapshot(0, 10))
    assert result.market_state == "no_qualified_inventory"
    assert result.supply_demand_ratio == 0.0
