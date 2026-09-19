from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_legacy_marketing_tick_is_retired():
    response = client.post("/v1/marketing/tick")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_marketing_tick_retired_use_search_intelligence_and_demand_genesis"
    )


def test_direct_aeo_deploy_is_retired():
    response = client.post("/v1/marketing/draft/hvac/deploy")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_aeo_deploy_retired_use_governed_search_content_flow"
    )


def test_direct_aeo_delete_is_retired():
    response = client.delete("/v1/aeo/pages/hvac")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_aeo_delete_retired_use_governed_search_content_flow"
    )


def test_legacy_a2a_negotiate_is_retired():
    response = client.post(
        "/v1/a2a/negotiate",
        json={"buyer_agent": "agent-1", "product": "lead_lane"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_a2a_negotiate_retired_use_governed_a2a_commerce_flow"
    )


def test_legacy_product_register_is_retired():
    response = client.post(
        "/v1/products/register",
        json={"sku": "example"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_product_register_retired_use_governed_product_catalog"
    )


def test_legacy_finance_replay_remains_retired():
    response = client.post("/v1/finance/replay", json={})
    assert response.status_code == 410


def test_legacy_price_and_settle_remains_retired():
    response = client.post(
        "/v1/funnel/price-and-settle",
        json={"prospect_id": "prospect-1", "settle": True},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_price_and_settle_retired_use_verified_bsc_usdt_commercial_flow"
    )


def test_legacy_agi_marketing_tick_is_retired():
    response = client.post("/v1/agi/marketing/tick")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_agi_marketing_tick_retired_use_governed_search_and_demand_flow"
    )
