"""Report why an already-executed TAM first-party recovery run was held."""
from copy import deepcopy
import json
from pathlib import Path
import os
import subprocess
import pytest

from scripts.summarize_tam_source_review_readonly import (
    summarize_review_payload, report_summary,
)


def packet(state, *, source_url=None, names=None, canonical="Acme Solar Ltd"):
    return {
        "schema_version":"empire.tam-first-party-discovery-review.v1",
        "mode":"OBSERVE","source":"first_party_search",
        "entities_selected_for_search":3,
        "search_candidates_before_cross_entity_filter":1,
        "website_probes_attempted":1,
        "database_write":False,"acquisitions_appended":0,
        "outbound_sent":False,
        "findings":[{
            "entity_id":"private-id",
            "canonical_name":canonical,
            "review_state":state,"source_url":source_url,
            "observed_business_names":names or [],
        }],
    }


def test_actual_successful_site_but_guard_rejection_is_specific():
    d=packet("DISCOVERED_SITE_IDENTITY_UNVERIFIED",
             source_url="https://acme.example/",
             names=["Acme Solar Ltd"])
    r=summarize_review_payload(d)
    assert r["rejection_reason_counts"]=={
        "SEARCH_FABRIC_IDENTITY_GUARD_REJECTED":1}
    assert r["public_site_probes_attempted"]==1
    assert r["database_access"] is False
    assert r["network_requests"]==0
    assert r["company_details_returned"]==0
    assert "private-id" not in json.dumps(r)
    assert "Acme Solar" not in json.dumps(r)
    assert "acme.example" not in json.dumps(r)


@pytest.mark.parametrize("names,url,reason",[
    (["Acme Solar Ltd"], None,"PUBLIC_SITE_OR_SAME_HOST_UNVERIFIED"),
    ([], "https://acme.example/","SITE_RETRIEVED_BUT_NO_BUSINESS_NAME_EVIDENCE"),
    (["Unrelated Company Ltd"],"https://acme.example/",
     "SITE_BUSINESS_NAME_DOES_NOT_EXACTLY_MATCH"),
])
def test_failed_site_fails_for_actual_observed_condition(names,url,reason):
    d=packet("DISCOVERED_SITE_IDENTITY_UNVERIFIED",source_url=url,names=names)
    r=summarize_review_payload(d)
    assert r["rejection_reason_counts"]=={reason:1}
    assert r["acquisitions_appended"]==0
    assert r["outbound_sent"] is False


def test_ambiguous_host_stays_ambiguous_even_when_source_url_missing():
    d=packet("AMBIGUOUS_OR_MISSING_DISCOVERED_HOST")
    r=summarize_review_payload(d)
    assert r["rejection_reason_counts"]=={
        "NO_UNIQUE_INDEPENDENT_CANDIDATE_HOST":1}


def test_review_candidate_is_not_misreported_as_written_acquisition():
    d=packet("DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW",
             source_url="https://acme.example/",names=["Acme Solar Ltd"])
    r=summarize_review_payload(d)
    assert r["rejection_reason_counts"]=={
        "REVIEW_CANDIDATE_NOT_LEDGER_APPROVED":1}
    assert r["acquisitions_appended"]==0


@pytest.mark.parametrize("key,value",[
    ("schema_version","something-else"),
    ("mode","EXECUTE"),
    ("source","recc_solar"),
    ("database_write",True),
    ("acquisitions_appended",1),
    ("outbound_sent",True),
])
def test_schema_or_unsafe_authority_refused(key,value):
    d=packet("DISCOVERED_SITE_IDENTITY_UNVERIFIED")
    d[key]=value
    with pytest.raises(ValueError,match="PRIVATE_REVIEW_SCHEMA_NOT_APPROVED"):
        summarize_review_payload(d)


def test_unknown_finding_state_refused_instead_of_silently_counting():
    d=packet("UNKNOWN_STATE")
    with pytest.raises(ValueError,match="UNKNOWN_PRIVATE_REVIEW_STATE"):
        summarize_review_payload(d)


def test_never_allows_arbitrary_path_when_reading_report(tmp_path,monkeypatch):
    monkeypatch.setattr(os,"geteuid",lambda:0)
    wrong=tmp_path/"secrets.json"
    wrong.write_text("{}")
    with pytest.raises(ValueError,match="OUTSIDE_APPROVED_DIRECTORY"):
        report_summary(wrong)
    # Even the right basename in the wrong folder is not sufficient.
    wrong=tmp_path/"20261010T200046Z-3e7726d663ba.json"
    wrong.write_text("{}")
    with pytest.raises(ValueError,match="OUTSIDE_APPROVED_DIRECTORY"):
        report_summary(wrong)


def test_no_raw_data_on_nonroot_failure():
    if os.geteuid()==0:
        pytest.skip("nonroot guard verified when invoked as ubuntu")
    res=subprocess.run([
        "python3","-m","scripts.summarize_tam_source_review_readonly",
        "--report",
        "/var/lib/empire/source-acquisition-review/20261010T200046Z-3e7726d663ba.json",
    ],capture_output=True,text=True,timeout=4)
    assert res.returncode==3
    assert res.stdout==""
    assert "ValueError" in res.stderr
    assert "Acme" not in res.stderr
    assert "3e7726d663ba" not in res.stderr


def test_bounded_findings_cannot_be_subverted():
    d=packet("DISCOVERED_SITE_IDENTITY_UNVERIFIED")
    d["findings"]=d["findings"]*6
    with pytest.raises(ValueError,match="PRIVATE_REVIEW_SCHEMA_NOT_APPROVED"):
        summarize_review_payload(d)
