"""Only explicit source + canonical CRM pilot may register Mautic routes.

All synthetic. No real DB, Mautic contact, email or outbound operations.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_pilot_activation import (
    ACTIVATION_MODE, CONFIG_SCHEMA,
    build_pilot_routers as _build_pilot_routers,
    create_crm_routers_for_hub,
)
from empire_os.mautic_crm_pilot_wiring import SOURCE_SCHEMA

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000201"
POST = "/v1/revenue-crm/integrations/mautic/mautic-uk-01/events/preview"
GET = "/v1/revenue-crm/integrations/mautic/inbox/reviews"


class SyntheticFirstPartyEvidenceVerifier:
    """Fixture-specific attestation; production must query a real owner."""

    def verify_source(
        self, *, source_id, tenant_id, source_evidence_ref,
        founder_approval_ref,
    ):
        return (
            source_id == "mautic-uk-01"
            and tenant_id == TENANT
            and source_evidence_ref == "source:reviewed-mautic-provider"
            and founder_approval_ref == "founder:separate-mautic-review-approval"
        )

    def verify_binding(
        self, *, source_id, tenant_id, contact_id, prospect_id,
        identity_evidence_ref,
    ):
        return (
            source_id == "mautic-uk-01"
            and tenant_id == TENANT
            and contact_id == 42
            and prospect_id == PROSPECT
            and identity_evidence_ref == "identity:exact-first-party-join"
        )


def build_pilot_routers(*args, **kwargs):
    # Pure synthetic tests must pass a separately provided trusted
    # attestor. The source config cannot declare itself verified.
    kwargs.setdefault(
        "mautic_evidence_verifier", SyntheticFirstPartyEvidenceVerifier()
    )
    return _build_pilot_routers(*args, **kwargs)


def dsn(user):
    return f"host=/var/run/postgresql port=5432 dbname=empiredb user={user}"


def private_file(path, content):
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    path.chmod(0o600)
    return path


def configs(tmp_path):
    key = Ed25519PrivateKey.generate()
    signing_path = private_file(
        tmp_path / "crm_signing.pem",
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    pilot = {
        "schema_version": CONFIG_SCHEMA,
        "founder_approval_ref": "founder:existing-crm-pilot",
        "key_id": "mautic-integration-uses-existing-crm",
        "signing_private_key_file": str(signing_path),
        "auth_dsn": dsn("empire_crm_auth_login"),
        "membership_dsn": dsn("empire_crm_membership_login"),
        "tenant_dsns": {TENANT: dsn("empire_crm_tenant_0123456789ab")},
    }
    pilot_path = private_file(tmp_path / "crm.json", json.dumps(pilot))
    secret = private_file(
        tmp_path / "mautic_hex_secret", b"1234567890abcdef" * 4,
    )
    source = {
        "schema_version": SOURCE_SCHEMA,
        "founder_approval_ref": "founder:separate-mautic-review-approval",
        "source_id": "mautic-uk-01",
        "tenant_id": TENANT,
        "source_evidence_ref": "source:reviewed-mautic-provider",
        "webhook_secret_file": str(secret),
        "writer_dsn": dsn("empire_mautic_tenant_aabbccddeeff"),
        "contact_bindings": {
            "42": {
                "prospect_id": PROSPECT,
                "identity_evidence_ref": "identity:exact-first-party-join",
            }
        },
    }
    path = private_file(tmp_path / "mautic_source.json", json.dumps(source))
    return pilot_path, path, source, secret


def app(routers):
    api = FastAPI()
    for route in routers:
        api.include_router(route)
    return TestClient(api)


def test_existing_approved_crm_pilot_remains_unchanged_without_mautic_optin(tmp_path):
    pilot, _source_path, _, _ = configs(tmp_path)
    routers = build_pilot_routers(pilot)
    assert len(routers) == 2
    client = app(routers)
    assert client.get(GET).status_code == 404
    assert client.post(POST, json={}).status_code == 404


def test_valid_separately_approved_source_creates_only_two_new_fail_closed_routes(tmp_path):
    pilot, source_path, _, _ = configs(tmp_path)
    routers = build_pilot_routers(pilot, mautic_config_path=source_path)
    assert len(routers) == 4
    client = app(routers)
    assert client.get(GET).status_code == 401
    assert client.get(GET, params={"tenant_id": OTHER}).status_code == 401
    assert client.post(POST, json={}, headers={"Webhook-Signature": "wrong"}).status_code == 401
    assert client.post(POST.replace("mautic-uk-01", "other-source"), json={}).status_code == 404
    assert client.post(POST, content=b"not-json",
                       headers={"content-type": "text/plain"}).status_code == 415
    assert client.post("/v1/revenue-crm/integrations/mautic/mautic-uk-01/send",
                       json={}).status_code == 404


def test_hub_never_activates_mautic_without_both_separate_gates(tmp_path, monkeypatch):
    pilot, source_path, _, _ = configs(tmp_path)
    monkeypatch.delenv("EMPIRE_CRM_PILOT_MODE", raising=False)
    monkeypatch.delenv("EMPIRE_CRM_PILOT_CONFIG_FILE", raising=False)
    monkeypatch.setenv("EMPIRE_CRM_MAUTIC_MODE", "APPROVED_READ_ONLY_MAUTIC_INBOX")
    monkeypatch.setenv("EMPIRE_CRM_MAUTIC_CONFIG_FILE", str(source_path))
    with pytest.raises(ValueError, match="existing CRM pilot"):
        create_crm_routers_for_hub()
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_CONFIG_FILE", str(pilot))
    monkeypatch.setenv("EMPIRE_CRM_MAUTIC_MODE", "ENABLED")
    with pytest.raises(ValueError, match="Mautic CRM integration mode"):
        create_crm_routers_for_hub()
    monkeypatch.setenv("EMPIRE_CRM_MAUTIC_MODE", "APPROVED_READ_ONLY_MAUTIC_INBOX")
    with pytest.raises(ValueError, match="evidence authority required"):
        create_crm_routers_for_hub()
    assert len(create_crm_routers_for_hub(
        mautic_evidence_verifier=SyntheticFirstPartyEvidenceVerifier(),
    )) == 4
    monkeypatch.delenv("EMPIRE_CRM_MAUTIC_MODE")
    with pytest.raises(ValueError, match="Mautic CRM integration mode"):
        create_crm_routers_for_hub()
    monkeypatch.delenv("EMPIRE_CRM_MAUTIC_CONFIG_FILE")
    assert len(create_crm_routers_for_hub()) == 2


@pytest.mark.parametrize("change", [
    {"schema_version": "unknown"},
    {"founder_approval_ref": "founder:existing-crm-pilot"},
    {"founder_approval_ref": ""},
    {"source_evidence_ref": ""},
    {"tenant_id": OTHER},
    {"source_id": "../invalid"},
    {"writer_dsn": dsn("empiredb_app")},
    {"writer_dsn": dsn("empire_crm_tenant_0123456789ab")},
    {"writer_dsn": "host=other.example.invalid port=5432 dbname=empiredb user=empire_mautic_tenant_aabbccddeeff"},
    {"contact_bindings": {"0": {"prospect_id": PROSPECT,
                                 "identity_evidence_ref": "identity:exact-first-party-join"}}},
    {"contact_bindings": {"42": {"prospect_id": PROSPECT}}},
    {"contact_bindings": {"42": {"prospect_id": PROSPECT,
                                 "identity_evidence_ref": "guess"}}},
    {"contact_bindings": {"42": {"prospect_id": "bad",
                                 "identity_evidence_ref": "identity:exact-first-party-join"}}},
    {"contact_bindings": {"42": {"prospect_id": PROSPECT,
                                 "identity_evidence_ref": "identity:exact-first-party-join"},
                          "43": {"prospect_id": PROSPECT,
                                 "identity_evidence_ref": "identity:another-prospect"}}},
])
def test_bad_identity_source_writer_or_approval_prevents_router_creation(
    tmp_path, change,
):
    pilot, source_path, source, _ = configs(tmp_path)
    source.update(change)
    private_file(source_path, json.dumps(source))
    with pytest.raises(ValueError):
        build_pilot_routers(pilot, mautic_config_path=source_path)


def test_duplicate_json_bindings_fail_closed(tmp_path):
    pilot, source_path, source, _ = configs(tmp_path)
    serial = json.dumps(source).replace(
        '"source_id": "mautic-uk-01"',
        '"source_id": "mautic-uk-01", "source_id": "other"',
    )
    private_file(source_path, serial)
    with pytest.raises(ValueError, match="duplicated"):
        build_pilot_routers(pilot, mautic_config_path=source_path)


def test_world_readable_source_or_secret_never_activates(tmp_path):
    pilot, source_path, _, secret = configs(tmp_path)
    source_path.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        build_pilot_routers(pilot, mautic_config_path=source_path)
    source_path.chmod(0o600)
    secret.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        build_pilot_routers(pilot, mautic_config_path=source_path)


def test_secret_must_match_explicit_mautic_source_format(tmp_path):
    pilot, source_path, _, secret = configs(tmp_path)
    private_file(secret, b"synthetic-not-actual-source-secret")
    with pytest.raises(ValueError, match="64-character hex"):
        build_pilot_routers(pilot, mautic_config_path=source_path)


def test_empty_approved_source_cold_starts_without_fake_customer(tmp_path, monkeypatch):
    """A real source may be connected before its FIRST contact exists.

    All signed unknown contacts must return retryable 503 with no CRM read
    and no durable acknowledgement. Source evidence is still independently
    verified; unsigned callers do not reach tenant data.
    """
    import base64
    import hashlib
    import hmac
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

    def forbidden_db_read(_self, _prospect):
        raise AssertionError("empty Mautic source must not access CRM data")

    monkeypatch.setattr(
        PostgresRevenueCrmRepository, "prospect", forbidden_db_read,
    )
    pilot, source_path, source, secret = configs(tmp_path)
    source["contact_bindings"] = {}
    private_file(source_path, json.dumps(source))
    client = app(build_pilot_routers(
        pilot, mautic_config_path=source_path,
    ))
    event = {
        "mautic.lead_channel_subscription_changed": [{
            "contact": {"id": 42},
            "channel": "email", "old_status": "contactable",
            "new_status": "unsubscribed",
        }],
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    signature = base64.b64encode(
        hmac.new(secret.read_bytes(), raw, hashlib.sha256).digest()
    ).decode()
    res = client.post(
        POST, content=raw,
        headers={"Content-Type": "application/json",
                 "Webhook-Signature": signature},
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "mautic_contact_binding_unavailable"
    assert client.post(
        POST, content=raw,
        headers={"Content-Type": "application/json",
                 "Webhook-Signature": "invalid"},
    ).status_code == 401
    with pytest.raises(ValueError, match="evidence authority required"):
        _build_pilot_routers(pilot, mautic_config_path=source_path)


def test_valid_signed_but_unbound_contact_returns_retryable_503_not_success(
    tmp_path, monkeypatch,
):
    import base64
    import hashlib
    import hmac
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

    def forbidden_db_read(_self, _prospect):
        raise AssertionError("unbound Mautic event must not access CRM DB")
    monkeypatch.setattr(
        PostgresRevenueCrmRepository, "prospect", forbidden_db_read,
    )
    pilot, source_path, _, secret = configs(tmp_path)
    client = app(build_pilot_routers(
        pilot, mautic_config_path=source_path,
    ))
    # Same synthetic email, different Mautic ID. Email matching is prohibited.
    event = {
        "mautic.lead_channel_subscription_changed": [{
            "contact": {"id": 99, "email": "synthetic-only@example.invalid"},
            "channel": "email", "old_status": "contactable",
            "new_status": "unsubscribed",
        }],
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    signature = base64.b64encode(
        hmac.new(secret.read_bytes(), body, hashlib.sha256).digest()
    ).decode()
    headers = {"Content-Type": "application/json",
               "Webhook-Signature": signature,
               "X-Tenant-ID": OTHER}
    result = client.post(POST, content=body, headers=headers)
    assert result.status_code == 503
    assert result.json()["detail"] == "mautic_contact_binding_unavailable"
    assert "synthetic-only@example.invalid" not in result.text


def test_valid_signed_bound_event_requires_real_canonical_crm_lookup(
    tmp_path, monkeypatch,
):
    import base64
    import hashlib
    import hmac
    from empire_os.revenue_crm_transport import (
        PostgresRevenueCrmRepository, RevenueCrmTransportError,
    )

    def unavailable(_self, _prospect):
        raise RevenueCrmTransportError("isolated canonical reader unavailable")
    monkeypatch.setattr(PostgresRevenueCrmRepository, "prospect", unavailable)
    pilot, source_path, _, secret = configs(tmp_path)
    client = app(build_pilot_routers(
        pilot, mautic_config_path=source_path,
    ))
    event = {
        "mautic.lead_channel_subscription_changed": [{
            "contact": {"id": 42},
            "channel": "email", "old_status": "contactable",
            "new_status": "unsubscribed",
        }],
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    signature = base64.b64encode(
        hmac.new(secret.read_bytes(), body, hashlib.sha256).digest()
    ).decode()
    result = client.post(POST, content=body, headers={
        "Content-Type": "application/json", "Webhook-Signature": signature,
    })
    assert result.status_code == 503
    assert result.json()["detail"] == "mautic_crm_review_unavailable"


def test_private_config_cannot_attest_itself_without_trusted_evidence(tmp_path):
    pilot, source_path, _, _ = configs(tmp_path)
    with pytest.raises(ValueError, match="evidence authority required"):
        _build_pilot_routers(pilot, mautic_config_path=source_path)


@pytest.mark.parametrize("change", [
    {"source_evidence_ref": "source:invented-plausible-reference"},
    {"founder_approval_ref": "founder:invented-plausible-approval"},
    {"contact_bindings": {"42": {
        "prospect_id": PROSPECT,
        "identity_evidence_ref": "identity:invented-plausible-proof",
    }}},
])
def test_well_formed_unverified_reference_is_rejected(tmp_path, change):
    pilot, source_path, source, _ = configs(tmp_path)
    source.update(change)
    private_file(source_path, json.dumps(source))
    with pytest.raises(ValueError, match="verified"):
        build_pilot_routers(pilot, mautic_config_path=source_path)


def test_authority_refuses_or_fails_closed_without_mounting_routes(tmp_path):
    pilot, source_path, _, _ = configs(tmp_path)

    class NoEvidence:
        def verify_source(self, **_kwargs): return False
        def verify_binding(self, **_kwargs): return True

    class BrokenEvidence:
        def verify_source(self, **_kwargs): raise RuntimeError("unavailable")
        def verify_binding(self, **_kwargs): return True

    class NoIdentity:
        def verify_source(self, **_kwargs): return True
        def verify_binding(self, **_kwargs): return False

    for verifier in (NoEvidence(), BrokenEvidence(), NoIdentity()):
        with pytest.raises(ValueError):
            _build_pilot_routers(
                pilot, mautic_config_path=source_path,
                mautic_evidence_verifier=verifier,
            )
