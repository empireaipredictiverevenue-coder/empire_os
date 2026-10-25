#!/usr/bin/env python3
"""Read-only EmpireOS Predictive Cloud V4.8 installed-code canary.

This canary NEVER changes DBs, streams, websites, services or live authority.
It only imports the release modules and checks held-return contracts. An
existing loopback status may be probed separately by the operator.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_cloud_v4_redis_shadow import feature_key
from empire_os.predictive_cloud_v4_outbox_hold_reader import review_held_outbox
from empire_os.predictive_cloud_v47_admission_shadow import (
    SCHEMA, PURPOSE, FixtureRevocations, FixtureTrustRoots, _canonical_bytes,
    review_signed_source_fixture,
)
from empire_os.predictive_cloud_v48_crm_bound_shadow import (
    review_crm_bound_admission_fixture,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

TENANT = "00000000-0000-0000-0000-000000000101"


def digest(name: str) -> str:
    return sha256(("production-safe-fictional-only:" + name).encode()).hexdigest()


def main() -> None:
    now = datetime.now(timezone.utc)
    source = Ed25519PrivateKey.generate()
    tenant = Ed25519PrivateKey.generate()
    def public_bytes(key):
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    claim = {
        "schema_version": SCHEMA,
        "tenant_id": TENANT,
        "sector": "roofing",
        "entity_digest": digest("entity"),
        "source_evidence_digest": digest("source"),
        "event_digest": digest("event"),
        "revision": 1,
        "event_kind": "OBSERVED",
        "permitted_purpose": PURPOSE,
        "issued_at": (now-timedelta(seconds=3)).isoformat(),
        "expires_at": (now+timedelta(minutes=4)).isoformat(),
        "nonce_digest": digest("nonce"),
    }
    data = _canonical_bytes(claim)
    roots = FixtureTrustRoots(
        source_keys={"source_canary_2026": public_bytes(source)},
        tenant_keys={"tenant_canary_2026": public_bytes(tenant)},
    )
    envelope = {
        "claim": claim,
        "source_key_id": "source_canary_2026",
        "tenant_key_id": "tenant_canary_2026",
        "source_signature_hex": source.sign(data).hex(),
        "tenant_signature_hex": tenant.sign(data).hex(),
    }
    row = {key: claim[key] for key in (
        "tenant_id", "sector", "entity_digest", "source_evidence_digest",
        "event_digest", "revision", "event_kind"
    )}
    row.update(
        latest_revision=1, withdrawn=False, source_review_state="UNVERIFIED",
        delivery_state="HELD", execution_authority="none",
    )
    result = review_signed_source_fixture(
        envelope, expected_tenant_id=TENANT, canonical_row=row,
        trust_roots=roots, revocations=FixtureRevocations(), now=now,
    )
    assert result["fixture_dual_signature_valid"] is True
    assert result["redis_publish_authorized"] is False
    assert result["production_source_admitted"] is False
    assert result["recognized_revenue_cents"] is None
    assert callable(review_crm_bound_admission_fixture)
    assert callable(SignedCrmTenantVerifier.authenticate)
    assert feature_key(
        tenant_scope_digest=digest("tenant"), sector="roofing",
        entity_digest=digest("entity")
    ).startswith("v4:feature_vector:")
    assert callable(review_held_outbox)
    assert str(UUID(TENANT)) == TENANT
    print(json.dumps({
        "status": "PREDICTIVE_V48_INSTALLED_SHADOW_CANARY_PASS",
        "installed_modules": 4,
        "original_crm_verifier_present": True,
        "fixture_dual_signature_verified": True,
        "real_source_rights_verified": False,
        "real_customer_forecast_verified": False,
        "production_database_migrated": False,
        "redis_published": False,
        "production_trading_enabled": False,
        "live_paid_traffic_enabled": False,
        "outbound_sent": False,
        "money_moved": False,
        "mode": "OBSERVE",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
