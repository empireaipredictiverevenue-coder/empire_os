"""Restricted reply source custody and production/feature merge-block tests."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from test_predictive_market_evidence_binding import snapshot, review, NOW
from empire_os.predictive_market_restricted_provenance import (
    review_restricted_reply_lineage,
    review_restricted_reply_lineage_runtime,
    review_market_gps_merge_compatibility,
)


def source():
    s=snapshot()
    s["raw_reply_records_are_commercial_proof"]=False
    s["inbound_reply_authenticity_verified"]=False
    s["restricted_reply_lineage"]={
        "schema":"empire.market_gps_restricted_reply_lineage.v1",
        "window_days":90,
        "reply_records_observed":10,
        "reply_records_with_intent_pointer":8,
        "reply_records_matched_to_intent":6,
        "reply_records_matched_to_prospect":4,
        "reply_records_missing_intent_pointer":2,
        "reply_records_with_unmatched_intent":2,
        "reply_records_with_unmatched_prospect":2,
        "positive_classification_records_unverified":3,
        "original_provider_message_id_checked":False,
        "canonical_contact_identity_verified":False,
        "provider_thread_binding_verified":False,
        "tenant_binding_verified":False,
        "buyer_intent_verified":False,
        "commercial_demand_inferred":False,
        "read_only_aggregate":True,
        "execution_authority":"none",
        "private_provider_message":"this_should_not_leak",
    }
    return s


def run(s=None,t=None):
    src=s if s is not None else source()
    territory=t if t is not None else review(src)
    return review_restricted_reply_lineage(src,territory,as_of=NOW)


def test_lineage_intent_and_prospect_links_are_not_direct_purchasing_or_training():
    r=run()
    assert r["status"]=="RESTRICTED_REPLY_PROVENANCE_RESEARCH_ONLY"
    assert r["reply_lineage_window_days"]==90
    assert r["territory_research_window_days"]==7
    assert len(r["original_territory_revision_sha256"])==64
    counts=r["source_reported_lineage_counts"]
    assert counts["reply_records_observed"]==10
    assert counts["reply_records_matched_to_prospect"]==4
    assert counts["positive_classification_records_unverified"]==3
    assert r["canonical_provider_message_authenticated"] is False
    assert r["direct_buying_role_authenticated"] is False
    assert r["independent_committed_buyer_count"] is None
    assert r["paid_order_count"] is None
    assert r["reply_lineage_count_is_a_proven_unique_buyer_count"] is False
    assert r["reply_lineage_can_be_mapped_to_territory_research"] is False
    assert r["matched_outbound_intent_is_authenticated_buyer_intent"] is False
    assert r["calibration_training_allowed"] is False
    assert r["execution_authority"]=="none"
    assert "this_should_not_leak" not in json.dumps(r)


@pytest.mark.parametrize("path,value,reason",[
    ("reply_records_observed",-1,"INVALID_REPLY_LINEAGE_COUNTERS"),
    ("reply_records_observed",True,"INVALID_REPLY_LINEAGE_COUNTERS"),
    ("reply_records_matched_to_prospect",7,"CONTRADICTORY_PROVIDER_REPLY_LINEAGE"),
    ("reply_records_with_intent_pointer",11,"CONTRADICTORY_PROVIDER_REPLY_LINEAGE"),
    ("reply_records_missing_intent_pointer",1,"CONTRADICTORY_PROVIDER_REPLY_LINEAGE"),
    ("reply_records_with_unmatched_prospect",1,"CONTRADICTORY_PROVIDER_REPLY_LINEAGE"),
    ("positive_classification_records_unverified",11,"CONTRADICTORY_PROVIDER_REPLY_LINEAGE"),
    ("buyer_intent_verified",True,"UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE"),
    ("commercial_demand_inferred",True,"UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE"),
    ("tenant_binding_verified",True,"UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE"),
    ("provider_thread_binding_verified",True,"UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE"),
    ("original_provider_message_id_checked",True,"UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE"),
    ("read_only_aggregate",False,"UNTRUSTED_OR_MISSING_PROVIDER_LINEAGE"),
    ("window_days",7,"INCOMPATIBLE_SOURCE_OBSERVATION_WINDOWS"),
    ("window_days",True,"INCOMPATIBLE_SOURCE_OBSERVATION_WINDOWS"),
])
def test_tampered_reply_lineage_holds(path,value,reason):
    s=source()
    s["restricted_reply_lineage"][path]=value
    result=run(s)
    assert result["status"]=="RESTRICTED_REPLY_PROVENANCE_HOLD"
    assert result["hold_code"]==reason
    assert result["paid_order_count"] is None
    assert result["calibration_training_allowed"] is False


def test_same_source_epoch_required_prevents_mixing_old_territories():
    s=source()
    t=review(s)
    s["generated_at"]=(NOW-timedelta(minutes=2)).isoformat()
    r=run(s,t)
    assert r["hold_code"]=="INCONSISTENT_SOURCE_EPOCHS"


@pytest.mark.parametrize("field,value",[
    ("inbound_reply_authenticity_verified",True),
    ("raw_reply_records_are_commercial_proof",True),
    ("restricted_source_scope","PUBLIC_ALL_REPLIES"),
])
def test_source_cannot_upgrade_self_to_authenticated_replies(field,value):
    s=source()
    t=review(s)
    s[field]=value
    r=run(s,t)
    assert r["hold_code"]=="UNTRUSTED_RESTRICTED_REPLIES_OR_SOURCE"


def test_unregistered_prospect_plus_positive_reply_does_not_count_as_buyer():
    s=source()
    s["restricted_reply_lineage"]["positive_classification_records_unverified"]=10
    r=run(s)
    assert r["status"]=="RESTRICTED_REPLY_PROVENANCE_RESEARCH_ONLY"
    assert r["direct_buying_role_authenticated"] is False
    assert r["independent_committed_buyer_count"] is None


def test_source_absent_or_held_does_not_invent_any_customer_counts():
    s=source()
    t=review(s)
    t["status"]="TERRITORY_RESEARCH_EVIDENCE_HOLD"
    r=run(s,t)
    assert r["hold_code"]=="UNREADY_OR_STALE_TERRITORY_EVIDENCE"
    assert r["source_reported_lineage_counts"] is None
    assert r["outbound_allowed"] is False


def test_runtime_reads_allowlisted_original_aggregate_only(tmp_path):
    s=source()
    p=tmp_path/"runtime/market_sweeps/revenue_gps_latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(s))
    (p.parent/"private_reply_messages.json").write_text("SECRET_NEVER_LOAD")
    r=review_restricted_reply_lineage_runtime(tmp_path,as_of=NOW)
    assert r["status"]=="RESTRICTED_REPLY_PROVENANCE_RESEARCH_ONLY"
    assert "SECRET_NEVER_LOAD" not in json.dumps(r)
    assert "this_should_not_leak" not in json.dumps(r)
    p.unlink()
    assert review_restricted_reply_lineage_runtime(tmp_path,as_of=NOW)["status"]=="RESTRICTED_REPLY_PROVENANCE_HOLD"


def producer(root,content):
    f=root/"empire_os/market_sweep_revenue_gps.py"
    f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(content)


def test_static_producer_audit_blocks_deprecated_nonexistent_rpc(tmp_path):
    feature=tmp_path/"feature"
    production=tmp_path/"production"
    producer(feature,"get_market_sweep_revenue_gps(")
    producer(production,"market_gps_restricted_reader RESTRICTED_MARKET_QUERY "
             "SET TRANSACTION READ ONLY REPLY_LINEAGE_QUERY "
             "restricted_source_scope restricted_reply_lineage "
             "unverified_positive_classifications_present")
    result=review_market_gps_merge_compatibility(feature,production)
    assert result["status"]=="SOURCE_OWNER_MERGE_REVIEW_REQUIRED"
    assert result["production_source_uses_restricted_read_only_query"] is True
    assert result["feature_producer_uses_production_restricted_contract"] is False
    assert result["exact_producer_code_revision_equal"] is False
    assert "FEATURE_MARKET_PRODUCER_MUST_NOT_REPLACE_RESTRICTED_PRODUCTION_SOURCE" in result["blockers"]
    assert result["merge_source_producer_authorized"] is False
    assert result["database_writes"] is False


def test_producer_code_unavailable_is_not_a_green_merge():
    from pathlib import Path
    x=review_market_gps_merge_compatibility(Path("/does_not_exist"),Path("/does_not_exist"))
    assert x["status"]=="SOURCE_CODE_UNAVAILABLE"
    assert x["merge_source_producer_authorized"] is False


def test_matching_epoch_with_changed_territory_body_cannot_pass_source_lineage():
    s=source()
    t=review(s)
    t["territory_research_cards"][0]["research_priority_score_not_conversion_probability"]=100.0
    r=run(s,t)
    assert r["hold_code"]=="TERRITORY_REVISION_OR_CONTENT_DRIFT"
    assert r["calibration_training_allowed"] is False


def test_modified_source_content_with_same_clock_cannot_reuse_territory_revision():
    s=source()
    t=review(s)
    s["markets"][0]["prospect_count"]+=1
    r=run(s,t)
    assert r["hold_code"]=="TERRITORY_REVISION_OR_CONTENT_DRIFT"
    assert r["direct_buying_role_authenticated"] is False
