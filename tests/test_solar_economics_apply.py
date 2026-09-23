import empire_os.solar_economics_apply as apply


def test_apply_market_economics_proposes_then_deterministically_verifies(monkeypatch):
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((path, payload))
        if path.endswith("/get_commercial_product_catalog"):
            return [{
                "version_state": "PENDING",
                "catalog_state": "UNKNOWN",
                "binding_terms_ready": False,
            }]
        if path.endswith("/propose_commercial_product_version"):
            assert payload["p_product_code"] == "solar_opportunity_map_gb"
            assert payload["p_acquisition_cost_basis"]["state"] == "VERIFIED"
            assert payload["p_acquisition_cost_basis"]["observed_cost_claim"] is False
            assert payload["p_fulfilment_cost_basis"]["state"] == "VERIFIED"
            assert payload["p_margin_policy"]["basis_type"] == "founder_policy"
            return {"version_id": "version-2", "decision": "proposed"}
        if path.endswith("/auto_verify_commercial_product_version"):
            assert payload == {"p_version_id": "version-2"}
            return {
                "decision": "verified",
                "authority": "deterministic_catalog_verification_only",
                "payment_mutation": False,
                "revenue_recognition": False,
            }
        raise AssertionError(path)

    result = apply.apply_market_economics("GB", request=request)

    assert result["decision"] == "verified"
    assert result["binding_terms_ready"] is True
    assert result["payment_mutation"] is False
    assert result["recognized_revenue"] is False


def test_apply_market_economics_is_idempotent_when_binding_ready():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append(path)
        if path.endswith("/get_commercial_product_catalog"):
            return [{
                "version_id": "verified-v2",
                "version_state": "VERIFIED",
                "catalog_state": "VERIFIED",
                "binding_terms_ready": True,
            }]
        raise AssertionError(path)

    result = apply.apply_market_economics("US", request=request)

    assert result["decision"] == "existing_verified"
    assert result["binding_terms_ready"] is True
    assert len(calls) == 1
