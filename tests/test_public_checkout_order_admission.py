"""Public direct-USDT order proxy admission is a security gate, not a write relay.

Mocked internal requests only: ZERO buyer/order/payment or finance mutations.
"""
import json

from fastapi.testclient import TestClient
import empire_os.public_gateway as gateway

CLIENT = TestClient(gateway.app)
PATH = "/v1/checkout/orders"
ORIGIN = "https://empire-ai.co.uk"


class FakeCheckout:
    calls = []

    def __init__(self, *, timeout):
        assert timeout == 20.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, *, content, headers):
        self.calls.append((url, content, headers))
        assert url == "http://127.0.0.1:8098/v1/orders"
        assert headers == {"Content-Type": "application/json"}
        return type("FakeResponse", (), {
            "content": b'{"detail":"binding_orders_not_authorized"}',
            "status_code": 503,
            "headers": {"content-type": "application/json"},
        })()


def arrange(monkeypatch, *, allowed=True):
    FakeCheckout.calls = []
    seen = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeCheckout)
    def limiter(peer, kind):
        seen.append((peer, kind))
        return allowed
    monkeypatch.setattr(gateway.FIRST_PARTY_INTAKE_LIMITER, "allow", limiter)
    return seen


def legit(body=None, *, origin=ORIGIN, fetch="same-origin"):
    return CLIENT.post(PATH, json=body or {"buyer": "test-offline"},
                       headers={"Origin": origin, "Sec-Fetch-Site": fetch})


def test_valid_first_party_post_forwards_only_to_internal_held_checkout(monkeypatch):
    seen = arrange(monkeypatch)
    result = legit()
    assert result.status_code == 503
    assert result.json()["detail"] == "binding_orders_not_authorized"
    assert result.headers["cache-control"] == "no-store"
    assert len(FakeCheckout.calls) == 1
    assert json.loads(FakeCheckout.calls[0][1]) == {"buyer": "test-offline"}
    assert len(seen) == 1 and seen[0][1] == "enquiry"


def test_missing_foreign_or_mismatched_origin_not_forwarded(monkeypatch):
    seen = arrange(monkeypatch)
    for heads in (
        {},
        {"Origin": "https://evil.example"},
        {"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"},
        {"Origin": ORIGIN, "Sec-Fetch-Site": "same-site"},
        {"Origin": "https://empire-ai.co.uk.evil.example"},
        {"Origin": "http://empire-ai.co.uk"},
    ):
        result = CLIENT.post(PATH, headers=heads, json={"test": True})
        assert result.status_code == 403
        assert result.json() == {"error": "same_origin_required"}
        assert result.headers["cache-control"] == "no-store"
    assert not FakeCheckout.calls and not seen


def test_json_media_type_is_exact_not_substring(monkeypatch):
    seen = arrange(monkeypatch)
    for media in ("text/plain", "application/json-evil", "application/x-www-form-urlencoded"):
        response = CLIENT.post(PATH, content=b"test",
                               headers={"Origin": ORIGIN, "Content-Type": media})
        assert response.status_code == 415
        assert response.json() == {"error": "application_json_required"}
        assert response.headers["cache-control"] == "no-store"
    assert seen == [] and FakeCheckout.calls == []


def test_rate_limit_fail_closed_before_db_or_checkout(monkeypatch):
    seen = arrange(monkeypatch, allowed=False)
    response = legit()
    assert response.status_code == 429
    assert response.json() == {"error": "rate_limited"}
    assert response.headers["cache-control"] == "no-store"
    assert len(seen) == 1 and seen[0][1] == "enquiry"
    assert FakeCheckout.calls == []


def test_streamed_oversize_denied_without_forwarding_or_pii_echo(monkeypatch):
    seen = arrange(monkeypatch)
    response = legit({"sensitive_data": "secret-buyer-test-" * 1200})
    assert response.status_code == 413
    assert response.json() == {"error": "checkout_payload_too_large"}
    assert response.headers["cache-control"] == "no-store"
    assert "secret-buyer-test-" not in response.text
    assert len(seen) == 1 and FakeCheckout.calls == []


def test_json_content_type_with_charset_still_supported(monkeypatch):
    seen = arrange(monkeypatch)
    response = CLIENT.post(PATH, content=b'{"buyer":"valid"}',
                           headers={"Origin": ORIGIN, "Sec-Fetch-Site": "none",
                                    "Content-Type": "application/json; charset=utf-8"})
    assert response.status_code == 503
    assert len(FakeCheckout.calls) == 1
    assert seen[0][1] == "enquiry"


def test_provider_network_error_is_generic_and_not_cached(monkeypatch):
    arrange(monkeypatch)
    async def fail(*args, **kwargs):
        raise gateway.httpx.ConnectError("internal secret must not leak")
    monkeypatch.setattr(FakeCheckout, "post", fail)
    response = legit()
    assert response.status_code == 503
    assert response.json() == {"error": "checkout_unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "secret" not in response.text


def test_security_headers_on_denied_order(monkeypatch):
    arrange(monkeypatch)
    response = CLIENT.post(PATH, json={"test": True})
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.status_code == 403
