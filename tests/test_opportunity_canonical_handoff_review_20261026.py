"""Exact research-to-EmpireDB handoff checks; synthetic records only in tmp tests."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json

from empire_os.opportunity_canonical_handoff_review import (
    review_factory_handoffs, from_existing_factory, BATCH_SCHEMA, RECORD_SCHEMA,
)

NOW = datetime(2026, 10, 26, 10, tzinfo=timezone.utc)

def candidate(**changes):
    row = {
        "schema_version": RECORD_SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "opportunity_key": "market:hvac:detroit, mi",
        "opportunity_class": "market_research",
        "evidence_refs": ["canonical:prospect_acquisitions",
                          "https://example.org/industry/source"],
        "evidence_count": 2,
        "factory_ready": False,
        "revenue_verified": False,
        "opportunity_id": None,
        "tenant_id": None,
    }
    row.update(changes)
    return row

def batch(items=None, **changes):
    rows = [candidate()] if items is None else items
    out = {"schema_version": BATCH_SCHEMA, "mode": "OBSERVE",
           "execution_authority": "none",
           "automatic_external_execution_allowed": False,
           "generated_at": NOW.isoformat(), "candidate_count": len(rows),
           "factory_ready_count": sum(x.get("factory_ready") is True for x in rows),
           "items": rows}
    out.update(changes)
    return out

def test_real_style_candidate_has_exact_holds_without_inventing_identity():
    v = review_factory_handoffs(batch(), now=NOW)
    assert v["source_reviewed"] is True
    assert v["records_reviewed"] == 1
    assert v["handoff_ready_count"] == 0
    row = v["items"][0]
    assert row["opportunity_key"] == "market:hvac:detroit, mi"
    assert row["next_owner"] == "OpportunityFactory"
    assert row["next_action"] == "COMPLETE_REAL_FACTORY_VALIDATION"
    assert "CANONICAL_GTM_OPPORTUNITY_UUID_NOT_PRESENT" in row["blockers"]
    assert "TENANT_BUSINESS_ENTITY_BINDING_NOT_ATTESTED" in row["blockers"]
    assert row["canonical_opportunity_id"] is None
    assert row["tenant_id"] is None
    assert not v["outbound_authorized"]
    assert not v["database_writes"]

def test_reported_factory_ready_and_claimed_uuids_still_do_not_make_db_join():
    v = review_factory_handoffs(batch([candidate(
        factory_ready=True,
        tenant_id="11111111-1111-4111-8111-111111111111",
        opportunity_id="22222222-2222-4222-8222-222222222222",
        evidence_refs=["empiredb:prospect_acquisitions:some_claim"],
    )]), now=NOW)
    r = v["items"][0]
    assert v["handoff_ready_count"] == 0
    assert r["factory_ready_reported"] is True
    assert r["next_owner"] == "CanonicalIdentity / SmartCRM"
    assert "SOURCE_ROW_RECEIPT_CLAIM_UNVERIFIED_IN_EMPIREDB" in r["blockers"]
    assert "TENANT_BUSINESS_ENTITY_BINDING_NOT_ATTESTED" in r["blockers"]
    assert r["canonical_opportunity_id"] is None
    assert v["crm_tenant_binding_verified"] is False

def test_duplicate_keys_and_untrusted_authority_fail_closed():
    duplicate = batch([candidate(), candidate()])
    assert review_factory_handoffs(duplicate, now=NOW)["holds"] == [
        "DUPLICATE_RESEARCH_OPPORTUNITY_KEY"]
    for unsafe in [
        batch(automatic_external_execution_allowed=True),
        batch(execution_authority="payment"),
        batch(items=[candidate(revenue_verified=True)]),
        batch(items=[candidate(factory_ready=1)]),
        batch(candidate_count=2),
        batch(items=[candidate(evidence_refs=["x", "x"])]),
    ]:
        result = review_factory_handoffs(unsafe, now=NOW)
        assert result["source_reviewed"] is False
        assert result["handoff_ready_count"] == 0
        assert not result["outbound_authorized"]

def test_stale_and_missing_sources_held_not_assumed(tmp_path):
    stale = batch(generated_at=(NOW-timedelta(days=7)).isoformat())
    assert review_factory_handoffs(stale, now=NOW)["status"] == "STALE"
    assert from_existing_factory(tmp_path, now=NOW)["status"] == "UNAVAILABLE"
    f = tmp_path/"runtime/opportunity_factory/intake_latest.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(batch()))
    assert from_existing_factory(tmp_path, now=NOW)["records_reviewed"] == 1
    f.unlink()
    f.symlink_to(tmp_path/"missing.json")
    assert from_existing_factory(tmp_path, now=NOW)["status"] == "UNAVAILABLE"

def test_deterministic_fingerprint_is_review_only():
    first = review_factory_handoffs(batch(), now=NOW)["items"][0]["review_id"]
    second = review_factory_handoffs(batch(), now=NOW)["items"][0]["review_id"]
    assert first == second
    assert first.startswith("research_review:")
    assert not first.startswith("empiredb:")

def test_original_supervisor_has_additive_read_only_handoff_field():
    import inspect
    from empire_os.revenue_completion_supervisor import build_snapshot
    source=inspect.getsource(build_snapshot)
    assert '"canonical_opportunity_handoffs"' in source
    assert "from_existing_factory" in source
