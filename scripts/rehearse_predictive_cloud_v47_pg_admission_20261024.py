#!/usr/bin/env python3
"""V4.7: disposable PG18 owner's held-event readback + dual Ed25519 fixture.

All private keys are generated in volatile memory and never written to disk.
No canonical production DB, no real identity/rights approvals, no Redis calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_cloud_v47_admission_shadow import (
    SCHEMA, PURPOSE, FixtureTrustRoots, FixtureRevocations,
    V47AdmissionHold, _canonical_bytes, review_signed_source_fixture,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"


def digest(s: str) -> str:
    return sha256(("fictional-v47-pg-owner:" + s).encode()).hexdigest()


def query(sql: str, *, role: bool = True) -> str:
    pgport = os.environ.get("PGPORT", "")
    if (os.environ.get("PGHOST") != "localhost" or not pgport.isdigit()
            or int(pgport) < 5433):
        raise ValueError("V47_REFUSE_NON_DISPOSABLE_PG")
    cmd = (["psql", "-XAtq", "-v", "ON_ERROR_STOP=1"]
           + (["-d", "empire_v4_outbox_fixture"] if role else ["-d", "postgres"])
           + ["-c", ("SET ROLE empiredb_migrator; " if role else "") + sql])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if proc.returncode:
        raise RuntimeError("V47_FIXTURE_QUERY_FAILED: " + proc.stderr[-1000:])
    return proc.stdout.strip()


def trust_setup():
    source = Ed25519PrivateKey.generate()
    tenant = Ed25519PrivateKey.generate()
    def raw(key):
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    return source, tenant, FixtureTrustRoots(
        source_keys={"v47_source_fixture": raw(source)},
        tenant_keys={"v47_tenant_fixture": raw(tenant)},
    )


def signed(claim: dict, source: Ed25519PrivateKey, tenant: Ed25519PrivateKey):
    payload = _canonical_bytes(claim)
    return {
        "claim": claim,
        "source_key_id": "v47_source_fixture",
        "tenant_key_id": "v47_tenant_fixture",
        "source_signature_hex": source.sign(payload).hex(),
        "tenant_signature_hex": tenant.sign(payload).hex(),
    }


def canonical(event: str) -> dict:
    result = query(
        "BEGIN READ ONLY; SELECT jsonb_build_object("
        "'tenant_id',o.tenant_id::text,'sector',o.sector,"
        "'entity_digest',o.entity_digest,"
        "'source_evidence_digest',o.source_evidence_digest,"
        "'event_digest',o.event_digest,'revision',o.revision,"
        "'event_kind',o.event_kind,'latest_revision',w.latest_revision,"
        "'withdrawn',w.withdrawn,'source_review_state',w.source_review_state,"
        "'delivery_state',o.delivery_state,'execution_authority',o.execution_authority)"
        " FROM public.empire_predictive_v4_outbox_held o JOIN "
        "public.empire_predictive_v4_watermarks_held w "
        "USING(tenant_id,sector,entity_digest)"
        f" WHERE o.tenant_id='{TENANT}'::uuid AND o.event_digest='{event}';"
        " COMMIT;"
    )
    return json.loads(result.splitlines()[0])


def stage(event: str, revision: int, kind: str):
    result = query(
        "SELECT public.stage_empire_predictive_v4_projection_held("
        f"'{TENANT}','roofing','{digest('entity')}',"
        f"'{digest('source')}',{revision},'{event}','{kind}')"
    )
    assert json.loads(result)["status"] == "HELD_STAGED"


def main():
    # Repeat the security guard even if the shell wrapper is bypassed.
    directory = query("SHOW data_directory", role=False)
    if (not directory.startswith("/tmp/pg_virtualenv.")
            or not directory.endswith("/data/18/regress")):
        raise ValueError("V47_NON_EPHEMERAL_PG_CLUSTER_REFUSED")
    now = datetime.now(timezone.utc)
    event = digest("event-11")
    stage(event, 11, "OBSERVED")
    source, tenant, roots = trust_setup()
    claim = {
        "schema_version": SCHEMA,
        "tenant_id": TENANT,
        "sector": "roofing",
        "entity_digest": digest("entity"),
        "source_evidence_digest": digest("source"),
        "event_digest": event,
        "revision": 11,
        "event_kind": "OBSERVED",
        "permitted_purpose": PURPOSE,
        "issued_at": (now - timedelta(seconds=10)).isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "nonce_digest": digest("nonce"),
    }
    envelope = signed(claim, source, tenant)
    args = {
        "expected_tenant_id": TENANT,
        "trust_roots": roots,
        "revocations": FixtureRevocations(),
        "now": now,
    }
    readback = canonical(event)
    good = review_signed_source_fixture(envelope, canonical_row=readback, **args)
    assert good["fixture_dual_signature_valid"] is True
    assert good["real_source_rights_independently_verified"] is False
    assert good["production_source_admitted"] is False
    assert good["redis_publish_authorized"] is False

    cross_tenant = dict(readback, tenant_id=OTHER)
    try:
        review_signed_source_fixture(envelope, canonical_row=cross_tenant, **args)
    except V47AdmissionHold as e:
        assert str(e) == "canonical_event_binding_mismatch"
    else:
        raise AssertionError("V47_CROSS_TENANT_CANONICAL_ROW_ACCEPTED")
    try:
        review_signed_source_fixture(
            envelope, canonical_row=readback,
            **dict(args, revocations=FixtureRevocations(
                source_digests=frozenset({digest("source")}))),
        )
    except V47AdmissionHold as e:
        assert str(e) == "owner_or_source_revoked"
    else:
        raise AssertionError("V47_REVOKED_SOURCE_ACCEPTED")

    # Durable canonical revision change invalidates the earlier signed claim.
    withdrawal = digest("withdrawn-12")
    stage(withdrawal, 12, "WITHDRAWN")
    after = canonical(event)
    assert after["latest_revision"] == 12 and after["withdrawn"] is True
    try:
        review_signed_source_fixture(envelope, canonical_row=after, **args)
    except V47AdmissionHold as e:
        assert str(e) in ("stale_canonical_revision", "source_withdrawn")
    else:
        raise AssertionError("V47_CANONICAL_WITHDRAWAL_BYPASSED")

    print(json.dumps({
        "status": "V47_DUAL_SIGNATURE_PG18_HELD_BINDING_PASS",
        "independent_source_and_tenant_ed25519_fixture": True,
        "canonical_pg_owner_readback_bound": True,
        "cross_tenant_db_row_blocked": True,
        "source_revocation_blocked": True,
        "durable_newer_revision_and_withdrawal_blocked": True,
        "production_source_admitted": False,
        "real_source_rights_verified": False,
        "redis_published": False,
        "money_moved": False,
        "production_empiredb_writes": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
