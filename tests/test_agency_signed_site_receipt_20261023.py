"""Read-only receipt for owner-signed site grants and local durable replay checks."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECEIPT=ROOT/"docs/commercial/EMPIRE_AGENCY_SIGNED_OWNER_SECURITY_NONCE_PREFLIGHT_20261023.json"

def test_explicit_owner_security_separation_and_no_live_activation():
    r=json.loads(RECEIPT.read_text())
    assert r["status"]=="SIGNED_OWNER_SECURITY_AND_PERSISTENT_SINGLE_HOST_REPLAY_PREFLIGHT_PASS"
    assert r["independent_issuer_keys_required"] is True
    assert r["owner_grant_and_security_registry_rechecked_each_operation"] is True
    assert r["allowed_operations"]==["capabilities:read","vehicles:read"]
    assert r["max_site_grant_age_seconds"]==86400
    assert r["site_origin_policy"]=="127.0.0.1_loopback_only"
    assert r["nonce_receipts"]=="owner_private_single_host_exclusive_create"
    assert all(r[key] is False for key in (
        "production_authority_issued","production_site_grant_issued",
        "production_empiredb_accessed","managed_credential_vault_activated",
        "distributed_nonce_authority_deployed","remote_mcp_exposed",
        "production_changes"))
def test_receipt_sources_match_and_trust_roots_not_committed():
    r=json.loads(RECEIPT.read_text())
    for path,digest in r["source_sha256"].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    doc=(ROOT/"docs/commercial/EMPIRE_AGENCY_SIGNED_SITE_OWNER_AND_NONCE_PREFLIGHT_20261023.md").read_text()
    assert "NOT live production" in doc
    assert "not a distributed or centrally managed replay service" in doc.lower()
    assert "no claim of direct drop-in production vault compatibility" in doc.lower()
