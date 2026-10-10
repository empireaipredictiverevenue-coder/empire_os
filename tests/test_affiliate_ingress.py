"""Affiliate-subdomain HTTP boundary / release holds.

Uses the EXISTING FastAPI public gateway. Tests are local TestClient requests;
no public DNS, Cloudflare route, traffic, signup, commissions or funds.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from empire_os.affiliate_ingress import (
    AFFILIATE_HOST,
    INGRESS_SCHEMA,
    review_affiliate_ingress,
)
from empire_os.affiliate_tracking import AffiliateBinding, mint_tracking_token
from empire_os.public_gateway import app


PARTNERS = f"https://{AFFILIATE_HOST}"
PRIMARY = "https://empire-ai.co.uk"
NOW = datetime(2026, 10, 10, 18, tzinfo=timezone.utc)
KEY = b"affiliate-subdomain-test-signing-key-0123456789"
NONCE = "safeNonce1234567_ABC"


def binding(**kwargs) -> AffiliateBinding:
    base = AffiliateBinding(
        tenant_ref="tenant:founder-test",
        source_ref="publisher:roofingmate.com",
        source_domain="roofingmate.com",
        programme_ref="programme:us-roofing-proposal",
        offer_format="PUBLISHER_PPC",
        country_code="US",
    )
    return replace(base, **kwargs)


def signed(b=None):
    return mint_tracking_token(
        b or binding(), hmac_key=KEY,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(days=1),
        nonce=NONCE,
    )


def assert_private_held(response):
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    assert "location" not in response.headers
    assert "set-cookie" not in response.headers
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"].startswith("no-store")
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("path", [
    "/",
    "/roofing",
    "/buy",
    "/health",
    "/robots.txt",
    "/v1/checkout/catalog",
    "/a2a/v1/discovery",
    "/trust",
    "/_next/static/not-present",
])
def test_affiliate_host_never_falls_through_to_primary_gateway(path):
    client = TestClient(app, base_url=PARTNERS)
    assert_private_held(client.get(path))


def test_affiliate_host_rejects_nontracking_post_endpoints():
    client = TestClient(app, base_url=PARTNERS)
    for path in ("/v1/checkout/orders", "/api/research/enquiry"):
        assert_private_held(client.post(path, json={}))


def test_private_subdomain_status_is_read_only_with_protective_headers():
    client = TestClient(app, base_url=PARTNERS)
    response = client.get("/v1/affiliate/status")
    assert response.status_code == 200
    value = response.json()
    assert value["schema_version"] == INGRESS_SCHEMA
    assert value["status"] == "PREACTIVATION"
    for key in ("tracking_enabled", "publisher_registration_enabled",
                "live_referrals_enabled", "click_storage_enabled",
                "conversion_postback_enabled", "payout_enabled"):
        assert value[key] is False
    assert value["execution_authority"] == "none"
    assert response.headers["cache-control"].startswith("no-store")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "set-cookie" not in response.headers
    assert "location" not in response.headers
    head = client.head("/v1/affiliate/status")
    assert head.status_code == 200 and not head.content


def test_status_rejected_on_primary_and_arbitrary_hosts():
    for base in (PRIMARY, "https://other.empire-ai.co.uk", "https://testserver"):
        assert_private_held(
            TestClient(app, base_url=base).get("/v1/affiliate/status")
        )


@pytest.mark.parametrize("token", [
    "not-even-signed",
    "af1." + "x" * 1480,
    "",
    "malicious%40email.com",
    "user%2Fprivate",
])
def test_referral_entrypoint_never_redirects_or_echoes_tokens(token):
    for domain in (PARTNERS, PRIMARY):
        client = TestClient(app, base_url=domain)
        response = client.get("/r/" + token, follow_redirects=False)
        assert_private_held(response)
        if token:
            assert token not in response.text


def test_even_valid_test_signed_referral_cannot_activate_traffic():
    t = signed()
    for domain in (PARTNERS, PRIMARY):
        response = TestClient(app, base_url=domain).get(
            "/r/" + t, follow_redirects=False
        )
        assert_private_held(response)
        assert t not in response.text


def test_forwarded_host_header_cannot_impersonate_subdomain():
    client = TestClient(app, base_url=PRIMARY)
    response = client.get(
        "/v1/affiliate/status",
        headers={
            "x-forwarded-host": AFFILIATE_HOST,
            "forwarded": f"host={AFFILIATE_HOST}",
        },
    )
    assert_private_held(response)


def test_duplicate_host_header_rejected():
    client = TestClient(app, base_url=PARTNERS)
    response = client.get(
        "/v1/affiliate/status",
        headers=[
            ("host", AFFILIATE_HOST),
            ("host", "empire-ai.co.uk"),
        ],
    )
    assert_private_held(response)


def test_referral_policy_is_buyer_and_tenant_bound_but_nonexecuting():
    b = binding()
    value = review_affiliate_ingress(
        binding=b, token=signed(b), signing_key=KEY,
        now=NOW, host=AFFILIATE_HOST,
    )
    assert value["signed_tracking_token_verified"] is True
    assert value["source_ref"] == b.source_ref
    assert value["tenant_ref"] == b.tenant_ref
    assert value["candidate_same_origin_path"] == "/roofing"
    assert not value["redirect_allowed"]
    assert not value["click_saved"]
    assert "trusted_canonical_source_lookup_missing" in value["blockers"]
    assert "idempotent_canonical_click_writer_missing" in value["blockers"]
    assert "live_affiliate_dispatch_not_authorized" in value["blockers"]
    assert value["execution_authority"] == "none"


def test_even_all_flags_and_claimed_writer_never_activate_route():
    b = binding(
        source_owner_verified=True,
        terms_approved=True,
        source_and_subaffiliate_approved=True,
        consent_and_privacy_approved=True,
        founder_live_authorized=True,
        commission_bps=1000,
    )
    value = review_affiliate_ingress(
        binding=b, token=signed(b), signing_key=KEY,
        now=NOW, host=AFFILIATE_HOST,
        source_reader_verified=True, durable_writer_verified=True,
    )
    assert value["blockers"] == ["live_affiliate_dispatch_not_authorized"]
    assert value["approved_destination_resolved"] is False
    assert value["redirect_allowed"] is False
    assert value["click_saved"] is False


@pytest.mark.parametrize("change", [
    {"tenant_ref": "tenant:someone-else"},
    {"source_ref": "publisher:wrong-domain"},
    {"programme_ref": "programme:different"},
    {"country_code": "UK"},
    {"offer_format": "PUBLISHER_PPL"},
])
def test_other_tenant_campaign_or_offer_fails_closed(change):
    b = binding()
    with pytest.raises(ValueError, match="token source"):
        review_affiliate_ingress(
            binding=binding(**change), token=signed(b),
            signing_key=KEY, now=NOW, host=AFFILIATE_HOST,
        )


def test_not_a_trusted_host_or_expired_token():
    b = binding()
    with pytest.raises(ValueError, match="host mismatch"):
        review_affiliate_ingress(
            binding=b, token=signed(b), signing_key=KEY,
            now=NOW, host="empire-ai.co.uk",
        )
    with pytest.raises(ValueError, match="not currently valid"):
        review_affiliate_ingress(
            binding=b, token=signed(b), signing_key=KEY,
            now=NOW + timedelta(days=3), host=AFFILIATE_HOST,
        )


def test_core_public_gateway_security_contracts_still_work():
    client = TestClient(app, base_url=PRIMARY)
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/v1/affiliate/status").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_unrecognised_hosts_fail_closed_across_primary_and_affiliate_routes():
    for hostname in (
        "wrong.example", "partners.empire-ai.co.uk.evil.test",
        "evil-partners.empire-ai.co.uk", "empire-ai.co.uk.evil.test",
    ):
        client = TestClient(app, base_url="https://" + hostname)
        for path in ("/", "/health", "/v1/checkout/catalog",
                     "/v1/affiliate/status", "/r/candidate"):
            assert_private_held(client.get(path))


def test_duplicated_host_headers_cannot_serve_primary_landing():
    client = TestClient(app, base_url=PRIMARY)
    for headers in (
        [("host", "empire-ai.co.uk"), ("host", AFFILIATE_HOST)],
        [("host", AFFILIATE_HOST), ("host", "empire-ai.co.uk")],
        [("host", "empire-ai.co.uk"), ("host", "empire-ai.co.uk")],
    ):
        assert_private_held(client.get("/", headers=headers))


def test_loopback_or_standard_tls_host_ports_are_explicitly_accepted():
    # Preserve internal health and primary-domain endpoints; keep business
    # approval separate from this noncommercial HTTP Host check.
    for base in ("http://localhost:80", "http://127.0.0.1:80",
                 "https://empire-ai.co.uk:443"):
        client = TestClient(app, base_url=base)
        assert client.get("/health").status_code == 200


def test_affiliate_hostname_cannot_access_avatar_websocket_even_with_cookie():
    from starlette.websockets import WebSocketDisconnect
    client = TestClient(app, base_url=PARTNERS)
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            "/avatar/presence/ws",
            headers={"host": AFFILIATE_HOST, "cookie": "empire_avatar_presence=fake-token"},
        ):
            pass
    assert error.value.code == 4404
