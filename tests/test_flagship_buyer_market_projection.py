"""Use existing authorised buyer-capacity worker, never a new DB identity."""
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from empire_os.flagship_buyer_market_projection import (
    summarize_authorized_market_coverage,
)
from empire_os.revenue_evidence_pathways import SOURCES
from test_revenue_evidence_pathways import payloads
from test_revenue_market_buyer_linkage import buyer

NOW = datetime(2026,10,19,12,tzinfo=timezone.utc)


def fixture(tmp_path):
    sources=payloads(n=1)
    sources["radar"]["candidates"][0]["metro"]="Little Rock, AR"
    for name,(rel,_) in SOURCES.items():
        p=tmp_path/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(sources[name]))


def test_exact_market_record_bucket_is_not_buyer_intent_or_payment(tmp_path):
    fixture(tmp_path)
    record=buyer()
    report=summarize_authorized_market_coverage(tmp_path,[record],as_of=NOW)
    assert report["status"]=="SAME_MARKET_BUYER_RECORDS_EXIST_UNVERIFIED"
    assert report["record_count_bucket"]=="ONE_TO_FOUR"
    assert report["exact_market_record_count"] is None
    assert report["full_buyer_projection_confirmed"] is True
    assert report["market_attribute_coverage_complete"] is True
    assert report["market_no_match_claim_authorized"] is False
    assert report["first_party_buyer_request_verified"] is False
    assert report["written_terms_or_allocation_verified"] is False
    assert report["buyer_or_revenue_verified"] is False
    assert report["database_writes"] is False
    assert report["outbound_sent"] is False
    text=json.dumps(report)
    for private in ("local-buyer-42", "Acme Clean Solar", "confidential contact",
                    "Little Rock", "555"):
        assert private not in text


def test_zero_claim_only_if_full_market_coverage_is_observed(tmp_path):
    fixture(tmp_path)
    result=summarize_authorized_market_coverage(
        tmp_path,[buyer(metro="Austin, TX")],as_of=NOW,
    )
    assert result["status"]=="NO_SAME_MARKET_RECORDS_IN_COMPLETE_PROJECTION"
    assert result["record_count_bucket"]=="ZERO"
    assert result["market_no_match_claim_authorized"] is True
    assert result["full_buyer_projection_confirmed"] is True
    assert result["buyer_or_revenue_verified"] is False


def test_missing_market_fields_mean_zero_is_unknown_not_verified_absence(tmp_path):
    fixture(tmp_path)
    incomplete=buyer(metro=None)
    result=summarize_authorized_market_coverage(
        tmp_path,[incomplete],as_of=NOW,
    )
    assert result["status"]=="NO_MATCH_OBSERVED_MARKET_COVERAGE_UNKNOWN"
    assert result["record_count_bucket"]=="UNKNOWN"
    assert result["market_no_match_claim_authorized"] is False
    assert result["market_attribute_coverage_complete"] is False
    assert result["next_internal_evidence_action"] == (
        "COMPLETE_MISSING_BUYER_NICHE_AND_METRO_PROVENANCE"
    )


def test_exact_observed_match_is_lower_bound_with_missing_other_buyers(tmp_path):
    fixture(tmp_path)
    result=summarize_authorized_market_coverage(
        tmp_path,[buyer(),buyer(id="other",metro=None)],as_of=NOW,
    )
    assert result["status"]=="PARTIAL_MARKET_OVERLAP_OBSERVED_COVERAGE_INCOMPLETE"
    assert result["record_count_bucket"]=="ONE_TO_FOUR"
    assert result["market_attribute_coverage_complete"] is False
    assert result["market_no_match_claim_authorized"] is False


def test_tenant_scoped_rows_block_global_absence_claim(tmp_path):
    fixture(tmp_path)
    result=summarize_authorized_market_coverage(
        tmp_path,[buyer(tenant_id="secret-tenant")],as_of=NOW,
    )
    assert result["status"]=="NO_MATCH_OBSERVED_MARKET_COVERAGE_UNKNOWN"
    assert result["record_count_bucket"]=="UNKNOWN"
    assert result["market_attribute_coverage_complete"] is False
    assert "secret-tenant" not in json.dumps(result)


def test_empty_completed_projection_is_real_zero_but_not_sales(tmp_path):
    fixture(tmp_path)
    result=summarize_authorized_market_coverage(tmp_path,[],as_of=NOW)
    assert result["status"]=="NO_SAME_MARKET_RECORDS_IN_COMPLETE_PROJECTION"
    assert result["market_no_match_claim_authorized"] is True
    assert result["buyer_or_revenue_verified"] is False


def test_truncated_projection_and_invalid_rows_held(tmp_path):
    fixture(tmp_path)
    result=summarize_authorized_market_coverage(
        tmp_path,[buyer()]*10000,as_of=NOW,
    )
    assert result["status"]=="EXACT_MARKET_COVERAGE_HELD"
    assert result["record_count_bucket"]=="UNKNOWN"
    assert result["full_buyer_projection_confirmed"] is False
    other=summarize_authorized_market_coverage(
        tmp_path,[None],as_of=NOW,
    )
    assert other["status"]=="EXACT_MARKET_COVERAGE_HELD"
    assert other["record_count_bucket"]=="UNKNOWN"


def test_stale_or_untrusted_factory_fails_closed_without_genuine_buyer_claim(tmp_path):
    fixture(tmp_path)
    path=tmp_path/SOURCES["quant"][0]
    document=json.loads(path.read_text())
    document["mode"]="WRITE"
    path.write_text(json.dumps(document))
    report=summarize_authorized_market_coverage(
        tmp_path,[buyer()],as_of=NOW,
    )
    assert report["status"]=="EXACT_MARKET_COVERAGE_HELD"
    assert report["record_count_bucket"]=="UNKNOWN"
    assert report["buyer_or_revenue_verified"] is False


def test_existing_root_worker_reuses_single_database_read_and_isolates_output(
    tmp_path,monkeypatch,capsys
):
    fixture(tmp_path)
    from scripts import build_buyer_capacity_readiness as existing
    calls=[]
    def fake_fetch():
        calls.append("READ_EXISTING_CANONICAL_BUYER_PROJECTION")
        return [buyer()]
    monkeypatch.setattr(existing,"fetch_all_buyers",fake_fetch)
    monkeypatch.setattr(existing,"ROOT",tmp_path)
    out=tmp_path/"runtime/buyer_capacity_readiness/latest.json"
    monkeypatch.setattr(existing,"OUT",out)
    # Service uses real UTC; fixture uses fixed test day. This is a source
    # chronology hold, not reason to contact DB a second time.
    assert existing.main() == 0
    assert calls == ["READ_EXISTING_CANONICAL_BUYER_PROJECTION"]
    result=json.loads(out.read_text())
    assert result["schema_version"]=="empire.buyer_capacity_readiness.v1"
    assert result["buyers_seen"]==1
    assert "flagship_exact_market_coverage" in result
    cov=result["flagship_exact_market_coverage"]
    assert cov["status"] in {
        "EXACT_MARKET_COVERAGE_HELD",
        "SAME_MARKET_BUYER_RECORDS_EXIST_UNVERIFIED",
    }
    assert cov["database_writes"] is False
    assert "local-buyer-42" not in json.dumps(result)
    assert "Acme Clean Solar" not in json.dumps(result)
    assert "confidential contact" not in json.dumps(result)
    assert existing.main() == 0
    assert len(calls)==2  # one per explicit service run, no extra DB query


def test_founder_reads_only_authorized_safe_market_projection(tmp_path):
    from empire_os.flagship_buyer_market_projection import (
        review_authorized_market_coverage_snapshot,
    )
    fixture(tmp_path)
    child=summarize_authorized_market_coverage(
        tmp_path,[buyer()],as_of=NOW,
    )
    p=tmp_path/"runtime/buyer_capacity_readiness/latest.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({
        "schema_version":"empire.buyer_capacity_readiness.v1",
        "observed_at":NOW.isoformat(),
        "mode":"OBSERVE", "execution_authority":"none",
        "buyers_seen":1,"market_defined":1,
        "flagship_exact_market_coverage":child,
    }))
    result=review_authorized_market_coverage_snapshot(tmp_path,as_of=NOW)
    assert result["status"]=="SAME_MARKET_BUYER_RECORDS_EXIST_UNVERIFIED"
    assert result["record_count_bucket"]=="ONE_TO_FOUR"
    assert result["source_classification_is_customer_proof"] is False
    assert result["first_party_buyer_request_verified"] is False
    assert "local-buyer-42" not in json.dumps(result)
    assert "Little Rock" not in json.dumps(result)


def test_forged_zero_count_and_untrusted_ref_blocked_by_global_reader(tmp_path):
    from empire_os.flagship_buyer_market_projection import review_authorized_market_coverage_snapshot
    fixture(tmp_path)
    child=summarize_authorized_market_coverage(tmp_path,[buyer()],as_of=NOW)
    child["record_count_bucket"]="ZERO"
    child["market_no_match_claim_authorized"]=True
    p=tmp_path/"runtime/buyer_capacity_readiness/latest.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({
        "schema_version":"empire.buyer_capacity_readiness.v1",
        "observed_at":NOW.isoformat(), "mode":"OBSERVE",
        "execution_authority":"none",
        "buyers_seen":1,"market_defined":1,
        "flagship_exact_market_coverage":child,
    }))
    held=review_authorized_market_coverage_snapshot(tmp_path,as_of=NOW)
    assert held["status"]=="EXACT_MARKET_COVERAGE_HELD"
    assert held["record_count_bucket"]=="UNKNOWN"
    assert held["market_no_match_claim_authorized"] is False
    child["record_count_bucket"]="ONE_TO_FOUR"
    child["market_no_match_claim_authorized"]=False
    child["opaque_opportunity_ref"]="private-buyer@example.com"
    p.write_text(json.dumps({
        "schema_version":"empire.buyer_capacity_readiness.v1",
        "observed_at":NOW.isoformat(), "mode":"OBSERVE",
        "execution_authority":"none","buyers_seen":1,"market_defined":1,
        "flagship_exact_market_coverage":child,
    }))
    result=review_authorized_market_coverage_snapshot(tmp_path,as_of=NOW)
    assert "private-buyer" not in json.dumps(result)
    assert result["status"]=="EXACT_MARKET_COVERAGE_HELD"


def test_stale_or_missing_authorized_service_report_is_unknown(tmp_path):
    from datetime import timedelta
    from empire_os.flagship_buyer_market_projection import review_authorized_market_coverage_snapshot
    empty=review_authorized_market_coverage_snapshot(tmp_path,as_of=NOW)
    assert empty["record_count_bucket"]=="UNKNOWN"
    p=tmp_path/"runtime/buyer_capacity_readiness/latest.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({
        "schema_version":"empire.buyer_capacity_readiness.v1",
        "observed_at":(NOW-timedelta(hours=9)).isoformat(),
        "mode":"OBSERVE","execution_authority":"none",
    }))
    result=review_authorized_market_coverage_snapshot(tmp_path,as_of=NOW)
    assert result["hold_code"]=="CAPACITY_SNAPSHOT_NOT_FRESH"
    assert result["market_no_match_claim_authorized"] is False
