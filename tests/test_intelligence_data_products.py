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
