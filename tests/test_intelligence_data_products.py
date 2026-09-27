from empire_os.intelligence_data_products import (
    data_product_catalog,
    get_data_product,
)


def test_catalog_has_core_data_products_without_invented_pricing():
    catalog = data_product_catalog()
    keys = {row["key"] for row in catalog}
    assert {
        "opportunity_feed",
        "market_signal_feed",
        "forecast_snapshot",
        "entity_graph_export",
        "spatial_physical_intelligence",
    } <= keys
    assert all(row["pricing_cents"] is None for row in catalog)
    assert all(row["execution_authority"] == "none" for row in catalog)


def test_product_lookup_is_explicit():
    assert get_data_product("forecast_snapshot") is not None
    assert get_data_product("unknown") is None



def test_vertical_product_contracts_are_read_only_and_unpriced():
    rows = {row["key"]: row for row in data_product_catalog()}

    for key in (
        "permit_intelligence_feed",
        "property_intelligence_monitor",
        "private_capital_intelligence",
    ):
        assert key in rows
        assert rows[key]["pricing_cents"] is None
        assert rows[key]["execution_authority"] == "none"
        assert rows[key]["commercial_model"] == "terms_required"

    assert "api" in rows["permit_intelligence_feed"]["delivery_modes"]
    assert "property" in rows["property_intelligence_monitor"]["source_nodes"]
    assert "private_capital" in rows["private_capital_intelligence"]["source_nodes"]
