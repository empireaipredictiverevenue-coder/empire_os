import empire_os.agent_web_runtime as runtime


def verified_product(code="managed_service"):
    return {
        "product_code": code,
        "product_name": "Managed Service",
        "product_family": "services",
        "billing_model": "per_lead",
        "currency": "USD",
        "active": True,
        "catalog_state": "VERIFIED",
        "version": 1,
        "version_state": "VERIFIED",
        "binding_terms_ready": True,
        "price_basis": {
            "state": "VERIFIED",
            "amount_cents": 7500,
            "unit": "per_lead",
            "currency": "USD",
        },
    }


def test_public_product_catalog_exposes_only_verified_products(monkeypatch):
    draft = verified_product("draft_product")
    draft["version_state"] = "DRAFT"

    monkeypatch.setattr(
        runtime,
        "load_snapshot",
        lambda: {
            "generated_at": "2026-09-21T20:00:00+00:00",
            "source": "canonical_supabase",
            "privacy": "aggregated_public_safe",
            "commercial_catalog": {
                "products": [verified_product(), draft],
            },
        },
    )
    result = runtime.execute_public_capability("product.catalog", {})
    assert result["capability"] == "product.catalog"
    assert result["count"] == 1
    assert result["products"][0]["product_code"] == "managed_service"
    assert result["products"][0]["price"]["amount_cents"] == 7500


def test_public_product_catalog_is_empty_when_catalog_is_unverified(monkeypatch):
    unknown = verified_product()
    unknown["catalog_state"] = "UNKNOWN"

    monkeypatch.setattr(
        runtime,
        "load_snapshot",
        lambda: {
            "generated_at": None,
            "commercial_catalog": {"products": [unknown]},
        },
    )
    result = runtime.execute_public_capability("product.catalog", {})
    assert result["count"] == 0
    assert result["products"] == []
    assert result["status"] == "canonical_catalog_empty"
