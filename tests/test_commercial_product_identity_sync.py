from empire_os.commercial_product_identity_sync import (
    search_product_identity_rows,
    sync_commercial_product_identities,
)


def test_search_products_sync_identity_without_economics():
    rows = search_product_identity_rows()
    codes = {row["product_code"] for row in rows}
    assert {
        "technical_search_audit",
        "serp_intelligence_api",
        "search_growth_command",
        "geo_ai_visibility",
    } <= codes
    assert rows
    for row in rows:
        assert row["provenance"]["pricing_observed"] is False
        assert row["provenance"]["economics_state"] == "UNKNOWN"
        assert "price" not in row
        assert "cost" not in row


def test_identity_sync_calls_only_identity_rpc():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        return {
            "decision": "identity_synchronized",
            "product_id": f"id-{payload['p_product_code']}",
            "catalog_state": "UNKNOWN",
            "economics_mutated": False,
            "actual_revenue": False,
        }

    result = sync_commercial_product_identities(request)
    assert result["known_products"] == result["synchronized"]
    assert result["pricing_observed"] is False
    assert result["economics_mutated"] is False
    assert result["actual_revenue"] is False
    assert all(
        path == "/rest/v1/rpc/register_commercial_product_identity"
        for _method, path, _payload in calls
    )
    assert all(
        payload["p_provenance"]["pricing_observed"] is False
        for _method, _path, payload in calls
    )
