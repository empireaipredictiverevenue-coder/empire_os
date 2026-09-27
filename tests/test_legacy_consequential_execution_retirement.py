from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_damage_scan_execution_routes_are_retired():
    assert client.post(
        "/v1/damage/scan",
        json={"postcode": "75201"},
    ).status_code == 410
    assert client.get("/v1/damage/scan-all").status_code == 410


def test_legacy_resend_webhook_is_retired():
    response = client.post(
        "/v1/resend/webhook",
        json={"type": "email.delivered", "data": {}},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_resend_webhook_retired_use_signed_canonical_webhook_service"
    )


def test_sweep_execution_is_retired():
    response = client.post("/v1/sweep/run", json={})
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_sweep_run_retired_use_governed_source_mesh"
    )


def test_strike_pack_delivery_is_retired():
    response = client.post(
        "/v1/strike-pack/claim",
        json={"tenant": "tenant-1", "niche": "roofing", "size": 10},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_strike_pack_claim_retired_use_revenue_exchange_and_governed_fulfilment"
    )


def test_funnel_transition_is_retired():
    response = client.post(
        "/v1/funnel/prospect-1/transition",
        json={"to_state": "claimed"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_funnel_transition_retired_use_revenue_crm_and_governed_state_flow"
    )


def test_telegram_send_routes_are_retired():
    assert client.post("/v1/telegram/brief", json={}).status_code == 410
    assert client.post(
        "/v1/telegram/alert",
        json={},
        params={"message": "hello"},
    ).status_code == 410


def test_direct_enrichment_is_retired():
    response = client.post(
        "/v1/leads/enrich",
        json={"company": "Acme Roofing"},
    )
    assert response.status_code == 410
