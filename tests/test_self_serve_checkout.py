from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import empire_os.self_serve_checkout as checkout


CATALOG = {
    "active": True,
    "version": 1,
    "currency": "USD",
    "product_id": "11111111-1111-1111-1111-111111111111",
    "product_code": "competitor_search_gap",
    "product_name": "Competitor Search Gap",
    "billing_model": "one_time",
    "catalog_state": "VERIFIED",
    "version_state": "VERIFIED",
    "binding_terms_ready": True,
    "price_basis": {
        "state": "VERIFIED",
        "currency": "USD",
        "amount_cents": 19900,
        "unit": "per_report",
    },
    "acquisition_cost_basis": {
        "state": "VERIFIED",
        "amount_cents": 2000,
    },
    "fulfilment_cost_basis": {
        "state": "VERIFIED",
        "amount_cents": 3000,
    },
    "margin_policy": {
        "state": "VERIFIED",
        "minimum_margin_bps": 6500,
    },
}


class FakeRequest:
    def __init__(self):
        self.buyers = {}
        self.orders = {}

    def __call__(self, method, path, payload=None, prefer=None):
        if path == "/rest/v1/rpc/get_commercial_product_catalog":
            return [dict(CATALOG)]
        if path.startswith("/rest/v1/buyers?select=id,email,buyer_name&email="):
            email = path.split("email=eq.", 1)[1].split("&", 1)[0]
            email = email.replace("%40", "@")
            return [
                row for row in self.buyers.values()
                if row["email"] == email
            ][:1]
        if path.startswith("/rest/v1/buyers?select=id&id=eq."):
            buyer_id = path.split("id=eq.", 1)[1].split("&", 1)[0]
            return [self.buyers[buyer_id]] if buyer_id in self.buyers else []
        if method == "POST" and path == "/rest/v1/buyers":
            self.buyers[payload["id"]] = dict(payload)
            return [dict(payload)]
        if path.startswith("/rest/v1/fulfilment_orders?select="):
            order_id = path.split("&id=eq.", 1)[1].split("&", 1)[0]
            return [self.orders[order_id]] if order_id in self.orders else []
        if method == "POST" and path == "/rest/v1/fulfilment_orders":
            self.orders[payload["id"]] = dict(payload)
            return [dict(payload)]
        raise AssertionError((method, path))


def test_prepare_checkout_order_is_real_catalog_and_idempotent():
    request = FakeRequest()
    params = dict(
        product_code="competitor_search_gap",
        business_name="Example Ltd",
        email="buyer@example.com",
        target_domain="example.com",
        payer_wallet="0x" + "1" * 40,
        terms_accepted=True,
        idempotency_key="checkout-test-001",
        request=request,
        now=datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    first = checkout.prepare_checkout_order(**params)
    second = checkout.prepare_checkout_order(**params)

    assert first["decision"] == "order_created"
    assert second["decision"] == "existing_order"
    assert first["product"]["amount_cents"] == 19900
    assert len(request.buyers) == 1
    assert len(request.orders) == 1
    order = next(iter(request.orders.values()))
    assert order["state"] == "accepted"
    assert order["price_cents"] == 19900
    assert order["expected_margin_cents"] == 14900
    assert order["commercial_payload"]["actual_revenue"] is False


def test_prepare_checkout_requires_terms_acceptance():
    request = FakeRequest()
    with pytest.raises(checkout.CheckoutError, match="terms acceptance"):
        checkout.prepare_checkout_order(
            product_code="competitor_search_gap",
            business_name="Example Ltd",
            email="buyer@example.com",
            target_domain="example.com",
            payer_wallet="0x" + "1" * 40,
            terms_accepted=False,
            idempotency_key="checkout-test-002",
            request=request,
        )


def test_non_usd_or_high_value_products_fail_closed():
    request = FakeRequest()
    original = dict(CATALOG)
    try:
        CATALOG["currency"] = "GBP"
        CATALOG["price_basis"] = {
            "state": "VERIFIED",
            "currency": "GBP",
            "amount_cents": 24900,
        }
        with pytest.raises(checkout.CheckoutError, match="USD"):
            checkout.prepare_checkout_order(
                product_code="competitor_search_gap",
                business_name="Example Ltd",
                email="buyer@example.com",
                target_domain="example.com",
                payer_wallet="0x" + "1" * 40,
                terms_accepted=True,
                idempotency_key="checkout-test-003",
                request=request,
            )
    finally:
        CATALOG.clear()
        CATALOG.update(original)


def test_payment_request_stays_gated_without_standing_authority():
    order = {
        "order_id": "22222222-2222-2222-2222-222222222222",
        "payer_wallet": "0x" + "1" * 40,
        "product": {"amount_cents": 19900},
        "actual_revenue": False,
    }
    result = checkout.create_payment_request_for_order(
        order,
        standing_authority=False,
    )
    assert result["payment_request_created"] is False
    assert result["payment_request_status"] == "standing_authority_required"
    assert result["actual_revenue"] is False
