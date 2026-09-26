import empire_os.solar_product_catalog as catalog


def test_legacy_solar_product_sync_delegates_to_gb_market_price(monkeypatch):
    seen = {}

    monkeypatch.setattr(
        catalog,
        "market_price",
        lambda code: (
            seen.update({"country": code})
            or type("Price", (), {"country_code": code})()
        ),
    )
    monkeypatch.setattr(
        catalog,
        "sync_market_price",
        lambda price, request=None: {
            "product_code": "solar_opportunity_map_gb",
            "country_code": "GB",
            "currency": "GBP",
            "display_price": "£249",
            "approval_state": "FOUNDER_APPROVED",
            "binding_terms_ready": False,
            "actual_revenue": False,
        },
    )

    result = catalog.sync_solar_opportunity_map_product(
        request=lambda *args, **kwargs: None,
    )

    assert seen["country"] == "GB"
    assert result["compatibility_wrapper"] is True
    assert result["parent_product_code"] == "solar_opportunity_map"
    assert result["product_code"] == "solar_opportunity_map_gb"
    assert result["currency"] == "GBP"
    assert result["binding_terms_ready"] is False
    assert result["actual_revenue"] is False
