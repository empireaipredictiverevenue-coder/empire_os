import empire_os.solar_product_catalog as catalog


def test_solar_product_sync_proposes_founder_approved_price_without_fake_costs():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if path.endswith("/get_commercial_product_catalog"):
            return [{
                "product_code": "solar_opportunity_map",
                "currency": "USD",
                "version_id": None,
                "version": None,
                "version_state": "UNKNOWN",
                "price_basis": {"state": "UNKNOWN"},
                "binding_terms_ready": False,
            }]
        if path.endswith("/register_commercial_product_identity"):
            return {
                "decision": "identity_synchronized",
                "product_id": "product-1",
                "catalog_state": "UNKNOWN",
            }
        if path.endswith("/propose_commercial_product_version"):
            assert payload["p_currency"] == "GBP"
            assert payload["p_price_basis"] == {
                "state": "VERIFIED",
                "amount_cents": 24900,
                "currency": "GBP",
                "unit": "per_map",
                "billing_model": "one_time",
                "source_type": "founder_approved",
                "basis": "founder_agreed_solar_opportunity_map_offer",
            }
            assert payload["p_acquisition_cost_basis"]["state"] == "UNKNOWN"
            assert payload["p_fulfilment_cost_basis"]["state"] == "UNKNOWN"
            assert payload["p_margin_policy"]["state"] == "UNKNOWN"
            return {
                "decision": "proposed",
                "version_id": "version-1",
                "version": 1,
                "version_state": "PENDING",
            }
        raise AssertionError(path)

    result = catalog.sync_solar_opportunity_map_product(request)

    assert result["product_code"] == "solar_opportunity_map"
    assert result["price_cents"] == 24900
    assert result["currency"] == "GBP"
    assert result["binding_terms_ready"] is False
    assert result["economics_complete"] is False
    assert result["catalog_verification_attempted"] is False
    assert result["actual_revenue"] is False
    assert not any(
        path.endswith("/auto_verify_commercial_product_version")
        for _method, path, _payload in calls
    )


def test_solar_product_sync_is_idempotent_when_price_version_exists():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if path.endswith("/register_commercial_product_identity"):
            return {
                "decision": "identity_synchronized",
                "product_id": "product-1",
            }
        if path.endswith("/get_commercial_product_catalog"):
            return [{
                "product_code": "solar_opportunity_map",
                "currency": "USD",
                "billing_model": "one_time",
                "version_id": "version-1",
                "version": 1,
                "version_state": "PENDING",
                "price_basis": {
                    "state": "VERIFIED",
                    "amount_cents": 24900,
                    "currency": "GBP",
                    "unit": "per_map",
                },
                "binding_terms_ready": False,
            }]
        raise AssertionError(path)

    result = catalog.sync_solar_opportunity_map_product(request)

    assert result["price_version"]["decision"] == "existing"
    assert result["binding_terms_ready"] is False
    assert not any(
        path.endswith("/register_commercial_product_identity")
        for _method, path, _payload in calls
    )
    assert not any(
        path.endswith("/propose_commercial_product_version")
        for _method, path, _payload in calls
    )
