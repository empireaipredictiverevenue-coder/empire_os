from empire_os.commercial_recovery_registry import (
    RECOVERY_PRODUCTS,
    VALID_STATES,
    recovery_product_catalog,
    recovery_summary,
)


def test_recovery_registry_keys_are_unique_and_states_valid():
    keys = [product.key for product in RECOVERY_PRODUCTS]
    assert len(keys) == len(set(keys))
    assert all(product.state in VALID_STATES for product in RECOVERY_PRODUCTS)


def test_recovery_registry_has_no_commercial_authority_or_fake_pricing():
    assert all(product.execution_authority == "none" for product in RECOVERY_PRODUCTS)
    assert all(product.pricing_observed is False for product in RECOVERY_PRODUCTS)
    summary = recovery_summary()
    assert summary["pricing_observed_count"] == 0
    assert summary["actual_revenue"] is False
    assert summary["execution_authority"] == "none"


def test_core_recovered_families_are_preserved():
    rows = {row["key"]: row for row in recovery_product_catalog()}
    assert rows["permit_intelligence"]["state"] == "ACTIVE_BUILD"
    assert rows["property_intelligence"]["state"] == "ACTIVE_BUILD"
    assert rows["private_capital_rollup"]["state"] == "ACTIVE_BUILD"
    assert rows["oil_gas_intelligence"]["state"] == "INCUBATE"
    assert rows["revenue_pulse"]["state"] == "ACTIVE_BUILD"
    assert rows["lane_seat_corridor_exchange"]["state"] == "ACTIVE_BUILD"
    assert "buyer_seats" in rows["lane_seat_corridor_exchange"]["surfaces"]
    assert rows["intel_hourly"]["state"] == "FOUNDER_GATE"


def test_mrr_is_not_the_only_revenue_model():
    models = {
        model
        for product in RECOVERY_PRODUCTS
        for model in product.revenue_models
    }
    assert "subscription" in models
    assert "transactional" in models
    assert "usage" in models
    assert "enterprise" in models
    assert "managed_service" in models
    assert "white_label" in models
    assert "performance" in models
