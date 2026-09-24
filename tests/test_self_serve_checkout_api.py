from fastapi.testclient import TestClient

import empire_os.self_serve_checkout_api as api


def test_checkout_health_defaults_payment_proposal_off(monkeypatch):
    monkeypatch.delenv(
        "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED",
        raising=False,
    )
    client = TestClient(api.app)
    body = client.get("/health").json()
    assert body["status"] == "online"
    assert body["payment_proposal_authorized"] is False
    assert body["payment_execution"] is False


def test_order_endpoint_keeps_proposal_gated(monkeypatch):
    monkeypatch.setattr(
        api,
        "prepare_checkout_order",
        lambda **kwargs: {
            "order_id": "o-1",
            "payer_wallet": "0x" + "1" * 40,
            "product": {"amount_cents": 19900},
            "actual_revenue": False,
        },
    )
    monkeypatch.setattr(
        api,
        "create_payment_request_for_order",
        lambda order, standing_authority: {
            **order,
            "payment_request_created": standing_authority,
        },
    )
    monkeypatch.delenv(
        "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED",
        raising=False,
    )
    client = TestClient(api.app)
    response = client.post(
        "/v1/orders",
        json={
            "product_code": "competitor_search_gap",
            "business_name": "Example Ltd",
            "email": "buyer@example.com",
            "target_domain": "example.com",
            "payer_wallet": "0x" + "1" * 40,
            "terms_accepted": True,
            "idempotency_key": "checkout-test-004",
        },
    )
    assert response.status_code == 200
    assert response.json()["payment_request_created"] is False
