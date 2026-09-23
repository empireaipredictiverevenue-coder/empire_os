from empire_os.phase4_exchange_mrr_products import (
    build_exchange_mrr_product_plan,
)


def test_phase4_exchange_mrr_products_modernize_legacy_seats():
    result = build_exchange_mrr_product_plan()
    rows = {row["product_code"]: row for row in result["products"]}

    assert result["phase"] == "4"
    assert result["product_count"] == 4
    assert rows["exchange_seat_starter"]["corridor_limit"] == 1
    assert rows["exchange_seat_growth"]["corridor_limit"] == 5
    assert rows["exchange_seat_pro"]["corridor_limit"] == 25
    assert rows["exchange_seat_enterprise"]["corridor_limit"] is None


def test_exchange_mrr_products_keep_pricing_at_founder_gate():
    result = build_exchange_mrr_product_plan()

    assert result["pricing_authority"] == "none"
    assert result["binding_terms_ready"] is False
    assert all(
        row["pricing_state"] == "FOUNDER_GATE"
        and row["binding_terms_ready"] is False
        for row in result["products"]
    )


def test_exchange_mrr_products_preserve_current_truth_rules():
    result = build_exchange_mrr_product_plan()
    upgrades = result["upgrades_from_legacy"]

    assert upgrades["capacity_is_verified_not_assumed"] is True
    assert upgrades["acquisition_continues_when_capacity_full"] is True
    assert upgrades["overflow_remains_empire_owned"] is True
    assert upgrades["pricing_is_governed_not_hardcoded"] is True
    assert upgrades["legacy_sqlite_not_used"] is True
    assert upgrades["legacy_usdc_solana_not_used"] is True
    assert result["canonical_settlement_rail"] == "USDT_BSC"
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"
