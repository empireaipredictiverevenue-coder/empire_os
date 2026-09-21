from empire_os.commercial_product_catalog import (
    assess_catalog_item,
    fetch_catalog,
    public_catalog_projection,
    summarize_catalog,
    write_catalog_snapshot,
)


def base_row():
    return {
        "product_code": "managed_service",
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
        "acquisition_cost_basis": {
            "state": "VERIFIED",
            "amount_cents": 1500,
            "unit": "per_lead",
            "currency": "USD",
        },
        "fulfilment_cost_basis": {
            "state": "VERIFIED",
            "amount_cents": 1000,
            "unit": "per_lead",
            "currency": "USD",
        },
        "margin_policy": {
            "state": "VERIFIED",
            "minimum_margin_bps": 3000,
        },
    }


def test_unknown_basis_blocks_binding_terms_even_when_legacy_zero_exists():
    row = base_row()
    row["monthly_price_cents"] = 0
    row["price_basis"] = {"state": "UNKNOWN"}
    result = assess_catalog_item(row)
    assert result["binding_terms_ready"] is False
    assert "price_basis_unverified" in result["readiness_blockers"]


def test_verified_catalog_item_is_binding_terms_ready():
    result = assess_catalog_item(base_row())
    assert result["binding_terms_ready"] is True
    assert result["readiness_blockers"] == []
    assert result["actual_revenue"] is False


def test_summary_counts_blockers_without_inventing_products():
    good = base_row()
    blocked = base_row()
    blocked["product_code"] = "unknown_cost"
    blocked["acquisition_cost_basis"] = {"state": "UNKNOWN"}
    result = summarize_catalog([good, blocked])
    assert result["product_count"] == 2
    assert result["binding_terms_ready_count"] == 1
    assert result["blocker_counts"] == {
        "acquisition_cost_basis_unverified": 1
    }


def test_fetch_catalog_uses_bounded_read_only_rpc():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        return [base_row()]

    result = fetch_catalog(
        request,
        product_code="managed_service",
        limit=900,
    )
    assert result["binding_terms_ready_count"] == 1
    assert calls == [(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        {"p_product_code": "managed_service", "p_limit": 500},
    )]


def test_public_projection_exposes_only_verified_active_catalog_items():
    verified = base_row()
    draft = base_row()
    draft["product_code"] = "draft"
    draft["version_state"] = "DRAFT"
    result = public_catalog_projection({
        "products": [verified, draft],
    })
    assert result["count"] == 1
    assert result["products"][0]["product_code"] == "managed_service"
    assert result["products"][0]["price"]["amount_cents"] == 7500


def test_snapshot_write_is_read_only_projection(tmp_path):
    path = tmp_path / "catalog.json"
    result = summarize_catalog([])
    written = write_catalog_snapshot(result, path)
    assert written == path
    assert path.exists()
    assert '"product_count": 0' in path.read_text()


def test_database_effective_window_can_block_otherwise_verified_item():
    row = base_row()
    row["binding_terms_ready"] = False
    result = assess_catalog_item(row)
    assert result["binding_terms_ready"] is False
    assert result["readiness_blockers"] == [
        "catalog_effective_window_inactive"
    ]


def test_public_projection_hides_verified_but_inactive_economics_window():
    row = base_row()
    row["binding_terms_ready"] = False
    result = public_catalog_projection({"products": [row]})
    assert result["count"] == 0
    assert result["products"] == []
