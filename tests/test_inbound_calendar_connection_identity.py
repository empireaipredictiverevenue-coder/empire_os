"""Signed calendar-only scope + fresh canonical EmpireDB membership."""
from datetime import datetime, timezone
from uuid import UUID
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from empire_os.inbound_calendar_connection_identity import (
    CalendarIdentityDenied, SignedCalendarConnectionVerifier,
    resolve_calendar_connection_principal,
)
from empire_os.saas_scale import TenantMembership

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
NOW = 1_800_000_000


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def jwt(private, **changes):
    claims = {
        "iss": "empire-os", "aud": "empire-inbound-recovery-calendar",
        "sub": "customer-owner-1", "tenant_id": TENANT,
        "scope": "recovery:calendar:connect",
        "iat": NOW - 5, "nbf": NOW - 5, "exp": NOW + 180,
        "jti": "calendarconnectiontestid0123456",
    }
    claims.update(changes)
    first = b64(b'{"alg":"EdDSA","typ":"JWT","kid":"pinned"}')
    second = b64(json.dumps(claims, separators=(",", ":")).encode())
    signed = first + "." + second
    return signed + "." + b64(private.sign(signed.encode()))


def setup(role="owner"):
    private = Ed25519PrivateKey.generate()
    current = {"role": role, "status": "active"}
    calls = []

    def lookup(subject, tenant):
        calls.append((subject, tenant))
        return TenantMembership(tenant, subject, current["role"], current["status"])

    verifier = SignedCalendarConnectionVerifier(
        {"pinned": private.public_key()}, load_membership=lookup,
        now=lambda: NOW,
    )
    return private, verifier, current, calls


def test_canonical_owner_or_admin_can_connect_and_uses_fresh_membership():
    for role in ("owner", "admin"):
        private, verifier, current, calls = setup(role)
        identity = verifier.authenticate(jwt(private))
        assert identity.tenant_id == TENANT
        assert identity.subject == "customer-owner-1"
        assert identity.role == role
        assert calls == [("customer-owner-1", TENANT)]
        current["status"] = "disabled"
        with pytest.raises(CalendarIdentityDenied):
            verifier.authenticate(jwt(private))
        assert len(calls) == 2


@pytest.mark.parametrize("role", ["operator", "viewer", "analyst", "gtm_research_reviewer"])
def test_nonadmin_roles_cannot_connect(role):
    private, verifier, _, _ = setup(role)
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(jwt(private))


@pytest.mark.parametrize("changes", [
    {"aud": "empire-revenue-crm", "scope": "crm:read"},
    {"scope": "crm:read"},
    {"aud": "empire-inbound-recovery-management"},
    {"iss": "some-other-idp"},
    {"tenant_id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"},
    {"tenant_id": "bad"},
    {"exp": NOW + 1000},
    {"exp": NOW - 1},
    {"iat": NOW + 10},
    {"nbf": NOW + 10},
    {"jti": "x"},
    {"sub": ""},
    {"exp": True},
    {"role": "owner"},
])
def test_wrong_token_claims_or_scope_fail_closed(changes):
    private, verifier, _, calls = setup()
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(jwt(private, **changes))
    assert calls == []


def test_wrong_signing_key_invalid_and_no_membership_leak():
    private, verifier, _, calls = setup()
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(jwt(Ed25519PrivateKey.generate()))
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(jwt(private) + ".extra")
    assert calls == []


def test_http_authorization_header_has_no_client_role_or_tenant_override():
    private, verifier, _, calls = setup()
    app = FastAPI()

    @app.get("/private")
    def read_private(request: Request):
        principal = resolve_calendar_connection_principal(request, verifier=verifier)
        return {"tenant": principal.tenant_id, "role": principal.role}

    client = TestClient(app)
    response = client.get(
        "/private?tenant=some-other-tenant",
        headers={
            "Authorization": "Bearer " + jwt(private),
            "X-Role": "owner", "X-Tenant": OTHER,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"tenant": TENANT, "role": "owner"}
    assert calls == [("customer-owner-1", TENANT)]
    with pytest.raises(CalendarIdentityDenied):
        client.get("/private", headers={"Authorization": "Bearer nonsense"})


def test_membership_storage_failure_blocks_identity():
    private = Ed25519PrivateKey.generate()

    def raise_db_failure(*_):
        raise RuntimeError("db-down")

    verifier = SignedCalendarConnectionVerifier(
        {"pinned": private.public_key()},
        load_membership=raise_db_failure,
        now=lambda: NOW,
    )
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(jwt(private))


def test_signed_crm_auth_is_not_a_calendar_connection_token():
    private, verifier, _, _ = setup()
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(jwt(private, aud="empire-revenue-crm", scope="crm:read"))
