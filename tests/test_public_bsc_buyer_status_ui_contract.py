"""Buyer browser status must retain token in memory, never persist it."""
from pathlib import Path


def test_first_party_buyer_status_button_and_token_not_in_urls():
    path=Path("apps/empire-public-site/src/app/buy/page.tsx")
    source=path.read_text()
    block=source.split("function BuyerPaymentStatus(",1)[1].split("function ProductResult(",1)[0]
    assert 'fetch("/v1/checkout/payment-status", {' in block
    assert 'method: "POST"' in block
    assert 'cache: "no-store"' in block
    assert 'body: JSON.stringify({ token })' in block
    assert "localStorage" not in block
    assert "sessionStorage" not in block
    assert "searchParams" not in block
    assert "token=" not in block
    assert "history." not in block
    assert 'body.payment_instructions_ready === true' in block
    assert 'body.chain_id === 56' in block
    assert '"approved_payment_instructions"' in block
    assert 'typeof body.amount_usdt === "string"' in block
    assert 'Do not send USDT' in block
    assert 'buyer_status_token_delivered' in source
    assert '<BuyerPaymentStatus token={result.buyer_status_token} />' in source


def test_public_gateway_proxy_does_not_accept_order_id_lookups():
    source=Path("empire_os/public_gateway.py").read_text()
    route=source.split('@app.post("/v1/checkout/payment-status")',1)[1].split('@app.get("/v1/checkout/exchange/tiers")',1)[0]
    assert 'FIRST_PARTY_INTAKE_LIMITER.allow(peer,"buyer_status")' in route
    assert 'request.headers.get("origin") != PUBLIC_BASE_URL' in route
    assert 'Sec-Fetch-Site' in route
    assert 'len(part)>160-len(body)' in route
    assert '"Cache-Control": "no-store, max-age=0"' in route
    assert 'f"{CHECKOUT_INTERNAL_URL}/v1/checkout/payment-status"' in route
    assert "request.query_params" not in route
    assert "request.url" not in route
    assert "request_json" not in route
    assert "buyer_id" not in route
    assert "fulfilment_order_id" not in route
