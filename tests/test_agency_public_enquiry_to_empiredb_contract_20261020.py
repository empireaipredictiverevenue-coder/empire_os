"""No-write production-code HTTP contract: public gateway -> checkout -> EmpireDB RPC.

Synthetic TEST payloads never leave the FastAPI TestClient/ASGI memory transport.
This is not a genuine buyer, live CRM delivery, tenant binding or revenue test.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from empire_os import first_party_sales_interest as domain
from empire_os import public_gateway as gateway
from empire_os import self_serve_checkout_api as checkout

CANONICAL_SOURCE = "first_party_commercial_sales_enquiry"
PRODUCT = "competitor_search_gap"


def synthetic_post():
    return {
        "product_code": PRODUCT,
        "business_name": "Synthetic Sample LLC",
        "email": "only-for-tests@synthetic.example",
        "domain": "synthetic.example",
        "industry": "Synthetic services",
        "geography": "Synthetic USA test region",
        "desired_outcome": "We need a source-backed competitor search gap report.",
        "contact_consent": True,
        "website": "",
        "idempotency_key": "synthetic-contract-20261020-v1",
    }


@pytest.fixture
def internal_route(monkeypatch, tmp_path):
    rpc_calls = []

    def stubbed_empiredb(method, path, *, payload):
        # No database client or live EmpireDB is used by this fixture.
        rpc_calls.append((method, path, payload))
        return {"decision": "created", "prospect": {"id": "synthetic-prospect-only"}}

    def fake_approved_catalogue(*, root):
        return {
            "offers": [{
                "product_code": PRODUCT,
                "offer_family": "search_intelligence",
                "approved_price_cents": 19900,
                "currency": "USD",
                "price_interval": "one_time",
                "founder_price_approval_reference": "synthetic-owner-price-fixture",
            }]
        }

    monkeypatch.setattr(domain, "founder_led_commercial_offers", fake_approved_catalogue)

    def real_domain_with_synthetic_gateway(**kwargs):
        return domain.record_founder_led_interest(
            request=stubbed_empiredb, root=tmp_path, **kwargs
        )

    monkeypatch.setattr(checkout, "record_founder_led_interest",
                        real_domain_with_synthetic_gateway)
    real_async_client = httpx.AsyncClient

    def in_process_checkout_http(*args, **kwargs):
        return real_async_client(
            transport=httpx.ASGITransport(app=checkout.app),
            timeout=kwargs.get("timeout", 20),
        )
    monkeypatch.setattr(gateway.httpx, "AsyncClient", in_process_checkout_http)
    headers = {
        "Origin": "https://empire-ai.co.uk",
        "Sec-Fetch-Site": "same-origin",
        "Content-Type": "application/json",
    }
    with TestClient(gateway.app) as client:
        yield client, headers, rpc_calls


def test_real_gateway_and_checkout_handlers_emit_only_canonical_rpc(internal_route):
    client, headers, captured = internal_route
    result = client.post(
        "/v1/checkout/commercial/interests",
        headers=headers,
        json=synthetic_post(),
    )
    assert result.status_code == 200, result.text[:200]
    body = result.json()
    assert body["decision"] == "commercial_enquiry_recorded"
    assert body["product_code"] == PRODUCT
    assert body["next_step"] == "FOUNDER_REVIEW"
    assert body["automated_contact_sent"] is False
    assert body["binding_commercial_terms"] is False
    assert body["checkout_authorized"] is False
    assert body["payment_action"] is False
    assert body["actual_revenue"] is False
    assert len(captured) == 1
    method, path, payload = captured[0]
    assert (method, path) == ("POST", "/rest/v1/rpc/ingest_prospect_atomic")
    assert payload["p_prospect"]["contact_source"] == CANONICAL_SOURCE
    assert payload["p_prospect"]["contacted_status"] == "not_contacted"
    assert payload["p_evidence"]["requested_product_code"] == PRODUCT
    assert payload["p_evidence"]["approved_price_cents"] == 19900
    assert payload["p_evidence"]["contact_consent_evidence"]["consent_to_contact"] is True
    assert payload["p_evidence"]["automatic_followup_authorized"] is False
    assert payload["p_evidence"]["payment_action"] is False
    assert payload["p_ingest_key"].startswith("commercial-sales:")
    assert payload["p_identity_keys"][0] == "domain:synthetic.example"
    assert "only-for-tests@" not in str(payload["p_identity_keys"])


@pytest.mark.parametrize("consent,origin,expect", [
    (False, "https://empire-ai.co.uk", 422),
    (True, "https://untrusted.example", 403),
])
def test_unconsented_or_wrong_origin_never_reaches_db_rpc(internal_route, consent, origin, expect):
    client, headers, captured = internal_route
    payload = synthetic_post()
    payload["contact_consent"] = consent
    headers["Origin"] = origin
    result = client.post(
        "/v1/checkout/commercial/interests", headers=headers, json=payload
    )
    assert result.status_code == expect
    assert captured == []


def test_honeypot_never_reaches_db_rpc(internal_route):
    client, headers, captured = internal_route
    payload = synthetic_post()
    payload["website"] = "do-not-contact.example"
    result = client.post(
        "/v1/checkout/commercial/interests", headers=headers, json=payload
    )
    assert result.status_code == 422
    assert captured == []


def test_unknown_product_cannot_create_acquisition(internal_route):
    client, headers, captured = internal_route
    payload = synthetic_post()
    payload["product_code"] = "invented_fake_free_offer"
    result = client.post(
        "/v1/checkout/commercial/interests", headers=headers, json=payload
    )
    assert result.status_code == 422
    assert captured == []
