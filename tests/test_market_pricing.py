import empire_os.market_pricing as pricing


def test_native_currency_pricing_matrix_covers_empire_markets():
    matrix = pricing.pricing_matrix()
    rows = {
        row["country_code"]: row
        for row in matrix["markets"]
    }

    assert set(rows) == {
        "GB", "US", "CA", "AU", "NZ", "IE",
        "DE", "FR", "ES", "IT", "NL", "BE", "PT",
    }
    assert rows["GB"]["currency"] == "GBP"
    assert rows["US"]["currency"] == "USD"
    assert rows["CA"]["currency"] == "CAD"
    assert rows["AU"]["currency"] == "AUD"
    assert rows["NZ"]["currency"] == "NZD"
    for code in ("IE", "DE", "FR", "ES", "IT", "NL", "BE", "PT"):
        assert rows[code]["currency"] == "EUR"

    assert rows["GB"]["approval_state"] == "FOUNDER_APPROVED"
    assert all(
        rows[code]["approval_state"] == "PROPOSED"
        for code in rows
        if code != "GB"
    )
    assert matrix["fx_conversion_used"] is False
    assert matrix["binding_terms_ready"] is False


def test_country_inference_prefers_explicit_then_source_then_location():
    assert pricing.infer_country_code(
        country_code="CA",
        source="recc_solar",
        metro="United Kingdom",
    ) == "CA"
    assert pricing.infer_country_code(
        source="recc_solar",
    ) == "GB"
    assert pricing.infer_country_code(
        metro="Berlin, Germany",
    ) == "DE"
    assert pricing.infer_country_code(
        address="Sydney, Australia",
    ) == "AU"
    assert pricing.infer_country_code(
        metro="Unknown Place",
    ) is None


def test_founder_approved_market_price_enters_verified_price_basis_only():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if path.endswith("/get_commercial_product_catalog"):
            return []
        if path.endswith("/register_commercial_product_identity"):
            return {
                "decision": "identity_synchronized",
                "product_id": "gb-product",
            }
        if path.endswith("/propose_commercial_product_version"):
            assert payload["p_product_code"] == "solar_opportunity_map_gb"
            assert payload["p_price_basis"]["state"] == "VERIFIED"
            assert payload["p_price_basis"]["amount_cents"] == 24900
            assert payload["p_price_basis"]["currency"] == "GBP"
            assert payload["p_acquisition_cost_basis"]["state"] == "UNKNOWN"
            assert payload["p_fulfilment_cost_basis"]["state"] == "UNKNOWN"
            assert payload["p_margin_policy"]["state"] == "UNKNOWN"
            return {
                "decision": "proposed",
                "version_id": "gb-version",
                "version_state": "PENDING",
            }
        raise AssertionError(path)

    result = pricing.sync_market_price(
        pricing.market_price("GB"),
        request=request,
    )

    assert result["approval_state"] == "FOUNDER_APPROVED"
    assert result["binding_terms_ready"] is False
    assert result["actual_revenue"] is False


def test_unapproved_market_price_stays_proposed_and_nonbinding():
    def request(method, path, payload=None, **kwargs):
        if path.endswith("/get_commercial_product_catalog"):
            return []
        if path.endswith("/register_commercial_product_identity"):
            return {
                "decision": "identity_synchronized",
                "product_id": "us-product",
            }
        if path.endswith("/propose_commercial_product_version"):
            assert payload["p_product_code"] == "solar_opportunity_map_us"
            assert payload["p_price_basis"]["state"] == "PROPOSED"
            assert payload["p_price_basis"]["source_type"] == "empire_pricing_draft"
            return {
                "decision": "proposed",
                "version_id": "us-version",
                "version_state": "PENDING",
            }
        raise AssertionError(path)

    result = pricing.sync_market_price(
        pricing.market_price("US"),
        request=request,
    )
    assert result["approval_state"] == "PROPOSED"
    assert result["binding_terms_ready"] is False


def test_matching_market_version_is_idempotent():
    price = pricing.market_price("AU")
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append(path)
        if path.endswith("/get_commercial_product_catalog"):
            return [{
                "product_code": price.product_code,
                "billing_model": "one_time",
                "version_id": "v1",
                "version_state": "PENDING",
                "price_basis": {
                    "state": "PROPOSED",
                    "amount_cents": price.amount_minor,
                    "currency": price.currency,
                    "unit": "per_map",
                },
                "binding_terms_ready": False,
            }]
        raise AssertionError(path)

    result = pricing.sync_market_price(price, request=request)

    assert result["decision"] == "existing"
    assert len(calls) == 1
