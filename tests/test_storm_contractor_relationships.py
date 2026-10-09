from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

import pytest

from empire_os.storm_contractor_relationships import relationship_context
from empire_os.storm_contractor_review import build_contractor_review

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 9, 23, 10, tzinfo=timezone.utc)


def base():
    def load(path):
        return json.loads((ROOT/path).read_text())
    return build_contractor_review(
        load("runtime/revenue_strike/dfw_storm_2026-09-20.json"),
        load("docs/DFW_SITE_OBSERVATIONS_20261009.json"),
        load("docs/DFW_CONTRACTOR_PUBLIC_SIGNALS_20261009.json"),
        as_of=NOW.date(),
        independent_evidence=load("docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json"),
    )


def registry():
    return {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "mode": "OBSERVE", "outbound_authorized": False,
        "generated_at": NOW.isoformat(), "gmail_snapshot_fresh": True,
        "relationship_count": 1,
        "relationships": [
            {"entity_key":"existing", "identity_domains":["maxexteriors.com"],
             "company":"PRIVATE_COMPANY_LABEL", "gmail_thread_ids":["abcdef123abc"],
             "last_inbound_at":NOW.isoformat(), "bounced_addresses":["secret@example.org"],
             "stage":"INBOUND_REVIEW_REQUIRED"},
        ],
    }


def test_existing_company_domain_match_is_not_a_send_clearance():
    source=base()
    result=relationship_context(source, registry(), now=NOW)
    assert result["existing_relationship_registry_state"]=="FRESH"
    assert result["summary"]["existing_relationship_domain_matches"]==1
    assert result["summary"]["ambiguous_relationship_domain_holds"]==0
    p=next(x for x in result["packets"] if x["company_domain"]=="maxexteriors.com")
    assert p["existing_commercial_relationship"]["status"]=="KNOWN_RELATIONSHIP_REVIEW_HOLD"
    assert "RECONCILE_EXISTING_COMMERCIAL_RELATIONSHIP_BEFORE_NEW_OUTREACH" in p["review_tasks"]
    assert not p["suppression_verified_clear"]
    assert not result["canonical_contact_history_checked"]
    assert not result["outbound_authorized"]
    assert "secret@" not in str(result) and "abcdef123abc" not in str(result)
    assert source["packets"][0].get("existing_commercial_relationship") is None


def test_no_exact_overlap_not_suppression_clearance():
    data=registry()
    data["relationships"][0]["identity_domains"]=["unrelatedcompany.org"]
    result=relationship_context(base(), data, now=NOW)
    assert result["summary"]["existing_relationship_domain_matches"]==0
    assert result["summary"]["relationship_registry_checked"] is True
    assert all(not p["existing_commercial_relationship"]["recipient_suppression_cleared"]
               for p in result["packets"])
    assert all(not p["outbound_authorized"] for p in result["packets"])


def test_ambiguous_exact_domain_is_manual_hold():
    r=registry()
    second=deepcopy(r["relationships"][0]); second["entity_key"]="duplicate"
    r["relationships"].append(second)
    r["relationship_count"]=2
    result=relationship_context(base(),r,now=NOW)
    assert result["summary"]["ambiguous_relationship_domain_holds"]==1
    p=next(x for x in result["packets"] if x["company_domain"]=="maxexteriors.com")
    assert p["existing_commercial_relationship"]["status"]=="AMBIGUOUS_RELATIONSHIP_HOLD"


def test_missing_relationship_snapshot_research_only():
    out=relationship_context(base(),None,now=NOW)
    assert out["existing_relationship_registry_state"]=="UNAVAILABLE"
    assert out["summary"]["relationship_registry_checked"] is False
    assert not out["outbound_authorized"]


def test_stale_registries_do_not_claim_live_clean_state():
    r=registry(); r["generated_at"]=(NOW-timedelta(days=5)).isoformat()
    out=relationship_context(base(),r,now=NOW)
    assert out["existing_relationship_registry_state"]=="STALE"
    assert out["summary"]["relationship_registry_checked"] is False
    assert all(p["existing_commercial_relationship"]["status"]=="RELATIONSHIP_SOURCE_STALE"
               for p in out["packets"])


def test_stale_gmail_capture_blocks_history_reliance():
    r=registry(); r["gmail_snapshot_fresh"]=False
    out=relationship_context(base(),r,now=NOW)
    assert out["existing_relationship_registry_state"]=="STALE"
    assert not out["canonical_contact_history_checked"]


@pytest.mark.parametrize("change", [
    {"schema_version":"not-existing-registry"},
    {"outbound_authorized":True},
    {"relationship_count":3},
    {"generated_at":"naive-time"},
])
def test_invalid_registry_fail_closed(change):
    r=registry(); r.update(change)
    with pytest.raises(ValueError):
        relationship_context(base(),r,now=NOW)


def test_exact_reconcile_deterministic():
    r=registry()
    assert relationship_context(base(),r,now=NOW)==relationship_context(base(),r,now=NOW)


def test_no_implicit_email_matching_from_company_names():
    r=registry()
    r["relationships"][0]["identity_domains"]=["someothercompany.com"]
    r["relationships"][0]["company"]="Max Exteriors LLC"
    result=relationship_context(base(),r,now=NOW)
    assert result["summary"]["existing_relationship_domain_matches"]==0
    assert not result["outbound_authorized"]


def test_live_snapshot_join_matches_existing_relationship_count():
    path=ROOT/"runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
    if not path.exists():
        pytest.skip("existing relationship registry snapshot unavailable")
    actual=json.loads(path.read_text())
    out=relationship_context(base(), actual, now=datetime.now(timezone.utc))
    assert out["summary"]["historical_contractor_companies"]==8
    assert not out["outbound_authorized"]
    assert out["summary"]["relationship_registry_checked"] or out["existing_relationship_registry_state"]=="STALE"
