"""Cryptographic CRM read-scope authentication; no production issuer or DB."""
from __future__ import annotations

import base64
import json
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import (
    build_authenticated_revenue_crm_resolver, create_revenue_crm_router,
)
from empire_os.revenue_crm_signed_auth import (
    SignedCrmTenantVerifier, build_signed_crm_tenant_authenticator,
)

A = "00000000-0000-0000-0000-000000000101"
B = "00000000-0000-0000-0000-000000000102"
NOW = 1_800_000_000


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def token(private_key, *, claims=None, header=None):
    default_header = {"alg": "EdDSA", "typ": "JWT", "kid": "issuer-1"}
    default_claims = {
        "iss": "empire-os", "aud": "empire-revenue-crm",
        "sub": "founder:verified", "tenant_id": A, "scope": "crm:read",
        "iat": NOW - 3, "nbf": NOW - 3, "exp": NOW + 200,
        "jti": "trustedcrmread0001",
    }
    default_claims.update(claims or {})
    default_header.update(header or {})
    message = (
        b64(json.dumps(default_header, separators=(",", ":")).encode()) + "." +
        b64(json.dumps(default_claims, separators=(",", ":")).encode())
    )
    return message + "." + b64(private_key.sign(message.encode("ascii")))


@pytest.fixture
def signed():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, {"issuer-1": public}


def test_only_pinned_signature_for_read_scope(signed):
    private, keys = signed
    verifier = SignedCrmTenantVerifier(keys, now=lambda: NOW)
    assert verifier.authenticate(token(private)) == A
    assert verifier.authenticate(token(private, claims={"tenant_id": B})) == B


@pytest.mark.parametrize("overrides", [
    {"iss": "not-empire"}, {"aud": "empire-ops-mcp"},
    {"scope": "crm:write"}, {"scope": "crm:read crm:write"},
    {"tenant_id": "not-a-uuid"},
    {"tenant_id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"},
    {"sub": ""}, {"jti": "short"}, {"iat": NOW + 500},
    {"nbf": NOW + 500}, {"exp": NOW - 100},
    {"exp": NOW + 901}, {"exp": NOW - 3}, {"exp": "never"},
    {"iat": True},
])
def test_invalid_claim_is_rejected(signed, overrides):
    private, keys = signed
    verifier = SignedCrmTenantVerifier(keys, now=lambda: NOW)
    with pytest.raises(ValueError):
        verifier.authenticate(token(private, claims=overrides))


def test_unsigned_tampered_and_wrong_issuer_keys_rejected(signed):
    private, keys = signed
    verifier = SignedCrmTenantVerifier(keys, now=lambda: NOW)
    good = token(private)
    for corrupted in (
        good.replace("e", "f", 1),
        good.rsplit(".", 1)[0] + ".",
        good + ".extra",
        good.replace(".", " ", 1),
        token(Ed25519PrivateKey.generate()),
        token(private, header={"alg": "none"}),
        token(private, header={"kid": "untrusted"}),
        good + "!",
    ):
        with pytest.raises(ValueError):
            verifier.authenticate(corrupted)


def test_no_trusted_key_or_invalid_key_configuration():
    with pytest.raises(ValueError):
        SignedCrmTenantVerifier({})
    with pytest.raises(ValueError):
        SignedCrmTenantVerifier({"bad/key": b"x" * 32})
    with pytest.raises(ValueError):
        SignedCrmTenantVerifier({"issuer-1": b"not-32-bytes"})


def test_duplicate_signed_claim_property_rejected(signed):
    private, keys = signed
    header = b64(b'{"alg":"EdDSA","typ":"JWT","kid":"issuer-1"}')
    original_claims = json.loads(
        base64.urlsafe_b64decode(token(private).split(".")[1] + "==")
    )
    payload = json.dumps(original_claims)[:-1] + ',"tenant_id":"' + B + '"}'
    message = header + "." + b64(payload.encode())
    forged = message + "." + b64(private.sign(message.encode()))
    with pytest.raises(ValueError, match="invalid token JSON"):
        SignedCrmTenantVerifier(keys, now=lambda: NOW).authenticate(forged)


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [type("Column", (), {"name": "tenant_id"})()]
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params=None): self.calls.append(sql)
    def fetchone(self): return (UUID(A),)
    def fetchall(self): return [(UUID(A),)]

class Connection:
    def __init__(self, cursor): self.cursor_obj = cursor
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return self.cursor_obj


def test_real_router_blocks_headers_until_signed_identity_and_db_session(signed):
    private, keys = signed
    cursor = Cursor()
    auth = build_signed_crm_tenant_authenticator(keys, now=lambda: NOW)
    repo_resolver = build_authenticated_revenue_crm_resolver(
        auth, {A: "dedicated-tenant-fixture-only"},
        connect_factory=lambda _: Connection(cursor),
    )
    app = FastAPI()
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=repo_resolver
    ))
    client = TestClient(app)
    for headers in (
        {"X-Tenant-ID": A},
        {"Authorization": "Bearer invalid", "X-Tenant-ID": A},
        {"Authorization": "Basic invalid", "X-Tenant-ID": A},
        {"Authorization": f"Bearer {token(Ed25519PrivateKey.generate())}"},
    ):
        response = client.get("/v1/revenue-crm/prospects", headers=headers)
        assert response.status_code == 401
    assert cursor.calls == []

    response = client.get(
        "/v1/revenue-crm/prospects?tenant_id=" + B,
        headers={"Authorization": "Bearer " + token(private), "X-Tenant-ID": B},
    )
    assert response.status_code == 200
    assert any("SELECT public.empire_current_tenant_id()" in sql
               for sql in cursor.calls)


def test_signed_identity_unprovisioned_tenant_fails_closed(signed):
    private, keys = signed
    auth = build_signed_crm_tenant_authenticator(keys, now=lambda: NOW)
    resolver = build_authenticated_revenue_crm_resolver(
        auth, {A: "dedicated-tenant-fixture-only"},
        connect_factory=lambda _: Connection(Cursor()),
    )
    app = FastAPI()
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=resolver
    ))
    response = TestClient(app).get("/v1/revenue-crm/prospects", headers={
        "Authorization": "Bearer " + token(private, claims={"tenant_id": B})
    })
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"


def test_default_unconfigured_hub_does_not_load_issuer():
    from pathlib import Path
    source = Path("empire_os/hub.py").read_text()
    assert "app.include_router(create_revenue_crm_router())" in source
