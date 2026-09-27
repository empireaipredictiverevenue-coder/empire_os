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


def test_legacy_agi_sales_tick_is_retired():
    response = client.post("/v1/agi/sales/tick")
    assert response.status_code == 410


def test_legacy_tenant_signup_is_retired():
    response = client.post(
        "/v1/tenants/signup",
        json={"name": "Acme", "email": "owner@example.com", "plan": "free"},
    )
    assert response.status_code == 410


def test_legacy_billing_subscribe_is_retired():
    response = client.post(
        "/v1/billing/subscribe",
        json={
            "tenant_id": "tenant-1",
            "plan": "pro",
            "billing_cycle": "monthly",
            "seats": 1,
            "payment_method": "crypto_usdc",
        },
    )
    assert response.status_code == 410


def test_legacy_crypto_subscription_verify_is_retired():
    response = client.post(
        "/v1/billing/crypto/verify",
        json={
            "subscription_id": "sub-1",
            "tx_signature": "sig",
            "sender_wallet": "wallet",
        },
    )
    assert response.status_code == 410


def test_legacy_payout_execution_routes_are_retired():
    cases = [
        ("/v1/payouts/process-all", {}),
        ("/v1/payouts/batch-tx", {}),
        ("/v1/payouts/verify", {
            "payout_id": "payout-1",
            "tx_signature": "sig",
            "sender_wallet": "wallet",
        }),
        ("/v1/payouts/submit", {
            "signed_tx_base64": "Zm9v",
            "batch_index": 0,
        }),
        ("/v1/payouts/verify-batch", {
            "tx_signature": "sig",
        }),
    ]
    for path, payload in cases:
        response = client.post(path, json=payload)
        assert response.status_code == 410, path


def test_legacy_lane_mutation_routes_are_retired():
    seat = client.post(
        "/v1/lanes/lane-1/seat",
        json={
            "firm_name": "Firm",
            "firm_slug": "firm",
            "tier": "raw",
            "price_monthly": 100,
        },
    )
    release = client.post("/v1/lanes/lane-1/release")
    route = client.post(
        "/v1/lanes/route",
        json={"prospect_id": "prospect-1"},
    )
    route_batch = client.post(
        "/v1/lanes/route-batch",
        json={"leads": [{"prospect_id": "prospect-1"}]},
    )
    assert seat.status_code == 410
    assert release.status_code == 410
    assert route.status_code == 410
    assert route_batch.status_code == 410


def test_legacy_ppc_mutation_routes_are_retired():
    assert client.post(
        "/v1/ppc/log_charge",
        json={"charge_id": "charge-1"},
    ).status_code == 410
    assert client.post(
        "/v1/ppc/log_invoice",
        json={"invoice_id": "invoice-1"},
    ).status_code == 410
    assert client.post(
        "/v1/ppc/charge",
        json={
            "buyer_id": "buyer-1",
            "head": 1,
            "reason": "test",
            "amount_cents": 100,
        },
    ).status_code == 410


def test_legacy_buyer_signup_routes_are_retired():
    assert client.post("/v1/buyers/signup-seat", json={}).status_code == 410
    assert client.post("/v1/buyers/signup", json={}).status_code == 410
    assert client.post("/v1/buyers/enterprise", json={}).status_code == 410


def test_legacy_outbox_mutations_are_retired():
    assert client.post("/v1/outbox/enqueue", json={}).status_code == 410
    assert client.post("/v1/outbox/1/mark", json={}).status_code == 410


def test_legacy_innovator_ship_is_retired():
    response = client.post(
        "/v1/innovator/ship",
        json={"ship_action": {"kind": "create_lane", "args": {}}},
    )
    assert response.status_code == 410


def test_legacy_a2a_catalog_and_product_reads_are_retired():
    assert client.get("/v1/a2a/catalog").status_code == 410
    assert client.get("/v1/products/pricing").status_code == 410
    assert client.get("/v1/products/example").status_code == 410


def test_legacy_outbox_reads_are_retired():
    assert client.get("/v1/outbox/pending").status_code == 410
    assert client.get("/v1/outbox/recent").status_code == 410


def test_legacy_outreach_pending_read_is_retired():
    response = client.get("/v1/outreach/prospects/pending")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_outreach_pending_retired_use_canonical_outbound_review_flow"
    )


def test_legacy_damage_consent_routes_are_retired():
    opt_in = client.get("/v1/damage/opt-in/prospect-1")
    status = client.get("/v1/damage/consent/prospect-1")
    assert opt_in.status_code == 410
    assert opt_in.json()["detail"] == (
        "legacy_damage_opt_in_retired_use_canonical_consent_api"
    )
    assert status.status_code == 410
    assert status.json()["detail"] == (
        "legacy_damage_consent_read_retired_use_canonical_consent_api"
    )
