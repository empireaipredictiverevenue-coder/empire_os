"""PPIR is evidence-grade: no fake precision, performance, unit costs or revenue."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import importlib.util
import json
from pathlib import Path
import os
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/review_predictive_cloud_ppir_existing_evidence_20261107.py"
SPEC=importlib.util.spec_from_file_location("ppir_existing_evidence",SCRIPT)
ppir=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ppir)
NOW=datetime(2026,11,7,20,30,tzinfo=timezone.utc)

def inputs():
    rows=[{
        "domain":"example-roofing.co.uk",
        "website":"https://example-roofing.co.uk",
        "source":"decodo_web_data",
        "evidence_state":"SEARCH_RESULT_REQUIRES_FIRST_PARTY_VERIFICATION",
        "qualified_customer":False,
        "outreach_authorized":False,
        "search_title_unverified":"Synthetic roofers",
        "source_query":"roofing contractors",
        "observed_at":"2026-11-07T19:00:00+00:00",
    }]
    discovery={"schema_version":ppir.DISCOVERY_SCHEMA,"source":"decodo_web_data","entries":rows}
    ledger={"schema_version":ppir.LEDGER_SCHEMA,"billing_window":"2026-11",
            "attempts_by_day":{"2026-11-06":6,"2026-11-07":10},
            "total_attempts":16,"provider_hold":False}
    return discovery,ledger

def test_actual_measurement_does_not_claim_success():
    a,b=inputs()
    out=ppir.audit_evidence(a,b,now=NOW)
    assert out["precision"]["unique_candidate_domains"]==1
    assert out["precision"]["top_k_precision"] is None
    assert out["precision"]["independently_verified_entity_count_in_this_artifact"]==0
    assert out["power"]["provider_attempts_in_billing_window"]==16
    assert out["power"]["requests_linked_to_verified_entities"] is None
    assert out["power"]["verified_cost_per_entity"] is None
    assert out["intelligence"]["measured_predictive_uplift"] is None
    assert out["revenue"]["verified_attributable_revenue"] is None
    assert out["readiness"]["benchmark_validated"] is False
    assert out["readiness"]["paid_provider_calls_made_by_audit"]==0

@pytest.mark.parametrize("field,value",[
    ("qualified_customer",True),
    ("outreach_authorized",True),
    ("evidence_state","VERIFIED_CUSTOMER"),
])
def test_discovery_can_never_self_attest_customer_eligibility(field,value):
    a,b=inputs()
    a["entries"][0][field]=value
    with pytest.raises(ppir.EvidenceHold,match="independent_first_party_proof"):
        ppir.audit_evidence(a,b,now=NOW)

def test_invalid_domain_spoofing_and_duplicate_denied():
    a,b=inputs()
    a["entries"][0]["domain"]="another.example"
    with pytest.raises(ppir.EvidenceHold,match="mismatched_domain"):
        ppir.audit_evidence(a,b,now=NOW)
    a,b=inputs()
    a["entries"].append(deepcopy(a["entries"][0]))
    with pytest.raises(ppir.EvidenceHold,match="duplicate"):
        ppir.audit_evidence(a,b,now=NOW)

@pytest.mark.parametrize("unsafe",["http://example-roofing.co.uk",
    "https://localhost/","https://127.0.0.1",
    "https://service.internal/path"])
def test_unsafe_urls_rejected(unsafe):
    a,b=inputs()
    a["entries"][0]["website"]=unsafe
    with pytest.raises(ppir.EvidenceHold):
        ppir.audit_evidence(a,b,now=NOW)

@pytest.mark.parametrize("timestamp",["2026-11-08T00:00:00+00:00","2026-11-07T19:00:00"])
def test_future_or_naive_sources_rejected(timestamp):
    a,b=inputs()
    a["entries"][0]["observed_at"]=timestamp
    with pytest.raises(ppir.EvidenceHold):
        ppir.audit_evidence(a,b,now=NOW)

def test_stale_is_explicit_and_not_a_fresh_result():
    a,b=inputs()
    a["entries"][0]["observed_at"]="2026-10-01T10:00:00Z"
    result=ppir.audit_evidence(a,b,now=NOW)
    assert result["precision"]["stale_search_result_candidates"]==1
    assert result["precision"]["fresh_search_result_candidates"]==0

@pytest.mark.parametrize("field,value",[
    ("total_attempts",20),
    ("total_attempts",True),
    ("provider_hold",0),
    ("billing_window","not-valid"),
])
def test_ledger_tampering_rejected(field,value):
    a,b=inputs()
    b[field]=value
    with pytest.raises(ppir.EvidenceHold):
        ppir.audit_evidence(a,b,now=NOW)

def test_ledger_day_outside_billing_window_rejected():
    a,b=inputs()
    b["attempts_by_day"]={"2026-12-01":16}
    with pytest.raises(ppir.EvidenceHold):
        ppir.audit_evidence(a,b,now=NOW)

def test_trusted_private_file_mode_and_no_symlink(tmp_path):
    a,b=inputs()
    path=tmp_path/"discovery.json"
    path.write_text(json.dumps(a))
    path.chmod(0o644)
    with pytest.raises(ppir.EvidenceHold,match="ownership_or_size"):
        ppir._read(path,100000)
    path.chmod(0o600)
    assert ppir._read(path,100000)["source"]=="decodo_web_data"
    link=tmp_path/"link.json"
    link.symlink_to(path)
    with pytest.raises(ppir.EvidenceHold,match="missing_or_unsafe"):
        ppir._read(link,100000)

def test_no_candidates_does_not_make_zero_precision_claim():
    a,b=inputs()
    a["entries"]=[]
    result=ppir.audit_evidence(a,b,now=NOW)
    assert result["precision"]["candidates_observed"]==0
    assert result["precision"]["top_k_precision"] is None

def test_naive_audit_clock_rejected():
    a,b=inputs()
    with pytest.raises(ppir.EvidenceHold,match="clock"):
        ppir.audit_evidence(a,b,now=datetime(2026,11,7,20,30))


def test_raw_search_result_cohort_does_not_claim_source_policy_admission():
    # ZipRecruiter-like job-board results can appear in old research artifacts.
    # This independent PPIR reviewer must never infer that such raw results
    # passed the separately owned Search Fabric source-admission policy.
    discovery, ledger = inputs()
    row = deepcopy(discovery["entries"][0])
    row["website"] = "https://ziprecruiter.com"
    row["domain"] = "ziprecruiter.com"
    row["search_title_unverified"] = "Synthetic job directory listing"
    discovery["entries"].append(row)

    result = ppir.audit_evidence(discovery, ledger, now=NOW)
    precision = result["precision"]
    assert precision["candidates_observed"] == 2  # raw observations, not eligible businesses
    assert precision["raw_candidate_count_is_not_source_policy_admission"] is True
    assert precision["source_policy_eligible_research_rows"] is None
    assert precision["source_policy_rejected_research_rows"] is None
    assert precision["source_policy_review_status"] == "NOT_ASSESSED_BY_PPIR_AUDIT"
    assert precision["independently_verified_entity_count_in_this_artifact"] == 0
    assert result["readiness"]["raw_discovery_results_are_not_customer_admission"] is True
    assert "original_search_fabric_source_policy_admission_for_fixed_cohort" in result["readiness"]["next_required_evidence"]
    assert result["readiness"]["external_data_delivery_authorized"] is False
    assert result["revenue"]["verified_attributable_revenue"] is None
