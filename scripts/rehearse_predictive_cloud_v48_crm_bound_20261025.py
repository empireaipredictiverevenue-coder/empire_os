#!/usr/bin/env python3
"""V4.8 integrated original CRM041 + V4 held064 on disposable PG18 only."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_cloud_v48_crm_bound_shadow import (
    V48MembershipHold, review_crm_bound_admission_fixture,
)
from empire_os.revenue_crm_signed_auth import (
    SignedCrmTenantVerifier, EmpireDbCrmMembershipReader,
    AUTHORIZATION_AUDIENCE, AUTHORIZATION_ISSUER, AUTHORIZATION_SCOPE,
)
from empire_os.predictive_cloud_v47_admission_shadow import (
    SCHEMA, PURPOSE, FixtureRevocations,
)
from scripts.rehearse_predictive_cloud_v47_pg_admission_20261024 import (
    TENANT, OTHER, digest, canonical, stage, signed, trust_setup, query,
)

SUBJECT = "pilot:verified"


def _base64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_crm_token(key: Ed25519PrivateKey, key_id: str, now: datetime, tenant: str) -> str:
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id}
    timestamp = int(now.timestamp())
    claims = {
        "iss": AUTHORIZATION_ISSUER, "aud": AUTHORIZATION_AUDIENCE,
        "sub": SUBJECT, "tenant_id": tenant, "scope": AUTHORIZATION_SCOPE,
        "iat": timestamp-15, "nbf": timestamp-15,
        "exp": timestamp+240, "jti": "v48fixture_unique_001",
    }
    parts = [_base64(json.dumps(v, sort_keys=True, separators=(",", ":")).encode())
             for v in (header, claims)]
    signed_bytes = ".".join(parts).encode("ascii")
    return signed_bytes.decode("ascii") + "." + _base64(key.sign(signed_bytes))


def denied(fn, reason: str):
    try:
        fn()
    except V48MembershipHold as exc:
        assert reason in str(exc), (reason, str(exc))
    else:
        raise AssertionError("V48_FAIL_OPEN:" + reason)


def pg_update(query_text: str):
    port = os.environ.get("PGPORT", "")
    if os.environ.get("PGHOST") != "localhost" or not port.isdigit() or int(port) < 5433:
        raise RuntimeError("V48_EPHEMERAL_ONLY")
    cmd = ["psql", "-XAtq", "-v", "ON_ERROR_STOP=1",
           "-d", "crm_membership_fixture", "-c", query_text]
    process = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    assert process.returncode == 0, process.stderr[-1000:]


def main():
    dir = query("SHOW data_directory", role=False)
    assert dir.startswith("/tmp/pg_virtualenv.") and dir.endswith("/data/18/regress")
    now = datetime.now(timezone.utc)
    event = digest("v48-held-11")
    stage(event, 11, "OBSERVED")
    original_crm_issuer = Ed25519PrivateKey.generate()  # volatile fixture key
    issuer_public = original_crm_issuer.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    # Must use the actual dedicated login and original 041 SECURITY DEFINER.
    dsn = (f"host=127.0.0.1 port={os.environ['PGPORT']} "
           "dbname=crm_membership_fixture user=empire_crm_membership_login "
           f"password={os.environ['V48_FIXTURE_PG_PASSWORD']}")
    member_reader = EmpireDbCrmMembershipReader(dsn)
    assert member_reader(SUBJECT, TENANT) is not None, "V48_DEDICATED_MEMBERSHIP_READER_NO_RESULT"
    assert member_reader(SUBJECT, OTHER) is None
    verifier = SignedCrmTenantVerifier(
        {"v48_fixture_issuer": issuer_public},
        load_membership=member_reader, now=lambda: int(now.timestamp()),
    )
    good_token = make_crm_token(original_crm_issuer, "v48_fixture_issuer", now, TENANT)
    source, tenant_signer, source_roots = trust_setup()
    claim = {
        "schema_version": SCHEMA, "tenant_id": TENANT, "sector": "roofing",
        "entity_digest": digest("entity"),
        "source_evidence_digest": digest("source"),
        "event_digest": event, "revision": 11, "event_kind": "OBSERVED",
        "permitted_purpose": PURPOSE,
        "issued_at": (now-timedelta(seconds=10)).isoformat(),
        "expires_at": (now+timedelta(minutes=5)).isoformat(),
        "nonce_digest": digest("v48-nonce"),
    }
    envelope = signed(claim, source, tenant_signer)
    owner_event = canonical(event)
    common = dict(envelope=envelope, signed_crm_bearer=good_token,
                  crm_verifier=verifier, canonical_row=owner_event,
                  trust_roots=source_roots, revocations=FixtureRevocations(), now=now)
    held = review_crm_bound_admission_fixture(**common)
    assert held["status"] == "CRM_AND_SOURCE_FIXTURES_CRYPTOGRAPHICALLY_REVIEWED_HELD"
    assert held["redis_publish_authorized"] is False
    assert held["production_source_admitted"] is False
    assert held["real_crm_membership_verified"] is False

    # Real existing 041 membership function rejects disabled second tenant.
    second = make_crm_token(original_crm_issuer, "v48_fixture_issuer", now, OTHER)
    denied(lambda: review_crm_bound_admission_fixture(
        **dict(common, signed_crm_bearer=second)),
        "crm_identity_or_membership_not_authorized")
    # Even a genuinely active membership in B cannot consume A's signed source.
    pg_update("UPDATE public.empire_crm_tenant_memberships SET "
              "status='active' "
              f"WHERE tenant_id='{OTHER}'::uuid AND subject='{SUBJECT}';")
    assert member_reader(SUBJECT, OTHER) is not None
    denied(lambda: review_crm_bound_admission_fixture(
        **dict(common, signed_crm_bearer=second)),
        "source_admission_held:cross_tenant_claim_refused")
    pg_update("UPDATE public.empire_crm_tenant_memberships SET "
              "status='disabled' "
              f"WHERE tenant_id='{OTHER}'::uuid AND subject='{SUBJECT}';")
    altered = good_token[:-1] + ("A" if good_token[-1] != "A" else "B")
    denied(lambda: review_crm_bound_admission_fixture(
        **dict(common, signed_crm_bearer=altered)),
        "crm_identity_or_membership_not_authorized")

    pg_update("UPDATE public.empire_crm_tenant_memberships SET "
              "status='disabled',revoked_at=now() "
              f"WHERE tenant_id='{TENANT}'::uuid AND subject='{SUBJECT}';")
    assert member_reader(SUBJECT, TENANT) is None
    denied(lambda: review_crm_bound_admission_fixture(**common),
           "crm_identity_or_membership_not_authorized")
    # Even when restored in the isolated fixture, an independently withdrawn
    # canonical V4 source event remains held.
    pg_update("UPDATE public.empire_crm_tenant_memberships SET "
              "status='active',revoked_at=NULL "
              f"WHERE tenant_id='{TENANT}'::uuid AND subject='{SUBJECT}';")
    assert member_reader(SUBJECT, TENANT) is not None
    stage(digest("v48-withdrawal-12"), 12, "WITHDRAWN")
    fresh_canonical = canonical(event)
    denied(lambda: review_crm_bound_admission_fixture(
        **dict(common, canonical_row=fresh_canonical)),
        "source_admission_held:stale_canonical_revision")
    print(json.dumps({
        "status": "V48_ORIGINAL_CRM041_AND_HELD064_BINDING_PASS",
        "real_ephemeral_pg18_crm_membership_reader_used": True,
        "signed_crm_bearer_verified_by_original_verifier": True,
        "owner_dual_signatures_bound_to_held_pg_event": True,
        "separate_tenant_denied": True,
        "revoked_membership_denied": True,
        "tampered_bearer_denied": True,
        "newer_source_withdrawal_denied": True,
        "redis_publish_authorized": False,
        "production_source_admitted": False,
        "live_db_touched": False,
        "real_source_rights_verified": False,
        "financial_execution": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
