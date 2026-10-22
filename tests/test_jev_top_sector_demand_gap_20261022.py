"""Archived sector interest != original buyer need or a sales-ready client."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import pytest

from empire_os.jev_top_sector_demand_gap import (
    review_sector_demand_gap,WORK_TYPE,
)
from scripts.review_jev_top_sector_demand_gap_20261022 import (
    PUBLIC_CONTRACTOR_BID_DISCOVERY,run_demand_gap,
)

ROOT=Path(__file__).resolve().parents[1]
PRIORITY=ROOT/"docs/commercial/JEV_SECTOR_RESEARCH_PRIORITY_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_TOP_SECTOR_CLIENT_DEMAND_GAP_20261022.json"


def sector():
    return json.loads(PRIORITY.read_text())


def pain(*,niche="roofing",lane="REVIEW_IDENTITY",opt_out=False):
    items=[{
        "source_sha256":hashlib.sha256(b"synthetic-original-not-a-person").hexdigest(),
        "source":"company_site","niche":niche,
        "unverified_identity":True,"unverified_commercial_need":True,
        "outreach_authorized":False,"review_lane":lane,
        "no_solicitation":opt_out,
    }]
    return {
        "schema_version":"empire.jev.client_pain_discovery.v1",
        "mode":"OBSERVE",
        "status":"CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY",
        "observations_submitted":1,
        "observations_with_pain_or_topic":1,
        "items":items,
        "review_lane_counts":{lane:1},
        "prospects_verified":0,
        "buyer_purchase_intent_verified":False,
        "source_rights_and_consent_verified":False,
        "crm_writes":False,
        "outbound_sent":0,
        "execution_authority":"none",
    }


def review(public=None,notices=()):
    return review_sector_demand_gap(
        sector(),pain() if public is None else public,
        public_procurement_candidates=notices,
    )


def test_public_pain_review_hypothesis_is_not_automatically_real_demand():
    d=review()
    roofing=next(r for r in d["sector_demand_research"] if r["sector"]=="roofing")
    assert roofing["unverified_public_pain_review_candidates"]==1
    assert roofing["actual_b2b_software_or_leadgen_purchase_request_proven"] is False
    assert roofing["original_canonical_buyer_identity_verified"] is False
    assert roofing["safe_to_contact"] is False
    assert d["software_or_marketing_clients_verified"]==0
    assert d["outbound_sent"]==0


def test_missing_first_party_pain_is_a_gap_not_a_global_no_demand_claim():
    p=pain(lane="MONITOR_UNVERIFIED")
    d=review(p)
    roofing=next(x for x in d["sector_demand_research"] if x["sector"]=="roofing")
    assert roofing["classified_public_pain_observations"]==1
    assert roofing["unverified_public_pain_review_candidates"]==0
    assert roofing["next_existing_research_action"]=="ORIGINAL_FIRST_PARTY_CLIENT_NEED_DISCOVERY_AND_EVIDENCE_REVIEW"


def test_explicit_no_solicitation_never_added_to_identity_review():
    p=pain(opt_out=True)
    d=review(p)
    row=next(x for x in d["sector_demand_research"] if x["sector"]=="roofing")
    assert row["unverified_public_pain_review_candidates"]==0
    assert row["no_solicitation_rows_held"]==1
    assert d["outbound_sent"]==0


def test_public_contractor_procurement_is_not_saas_customer_request():
    d=review(notices=PUBLIC_CONTRACTOR_BID_DISCOVERY)
    notices=d["contractor_work_procurement_discovery_candidates"]
    assert len(notices)==3
    assert {r["sector"] for r in notices}=={"general_contractor","roofing","hvac"}
    assert all(r["procurement_object"]==WORK_TYPE
               and not r["buyer_of_empire_leadgen_or_saas_verified"]
               and not r["allowed_for_auto_outreach"]
               and not r["bidding_eligibility_and_deadline_current_verified"]
               for r in notices)
    assert d["original_procurement_notices_verified"]==0


@pytest.mark.parametrize("mutate",[
    lambda x:x.update(prospects_verified=1),
    lambda x:x.update(buyer_purchase_intent_verified=True),
    lambda x:x.update(source_rights_and_consent_verified=True),
    lambda x:x.update(crm_writes=True),
    lambda x:x.update(outbound_sent=1),
    lambda x:x["items"][0].update(unverified_identity=False),
    lambda x:x["items"][0].update(outreach_authorized=True),
    lambda x:x["items"][0].update(private_evidence_url="https://company.com/secret"),
    lambda x:x["items"][0].update(source_sha256="private"),
])
def test_promotions_or_personally_identifying_content_are_rejected(mutate):
    p=pain()
    mutate(p)
    with pytest.raises(ValueError):
        review(p)


@pytest.mark.parametrize("mutate",[
    lambda x:x.update(outreach_sent=1),
    lambda x:x.update(verified_contactable_leads=1),
    lambda x:x.update(database_writes=True),
    lambda x:x["sector_research_rows"][0].update(auto_contact_authority=True),
    lambda x:x["sector_research_rows"][0].update(
        recent_gps_observed_acquisitions_not_buyer_demand=-1),
])
def test_false_archive_authority_or_market_inference_is_rejected(mutate):
    s=sector()
    mutate(s)
    with pytest.raises(ValueError):
        review_sector_demand_gap(s,pain())


def test_untrusted_government_rfp_original_claim_is_rejected():
    notices=list(deepcopy(PUBLIC_CONTRACTOR_BID_DISCOVERY))
    notices[0]["source_original_notice_independently_inspected"]=True
    with pytest.raises(ValueError):
        review(notices=tuple(notices))


def test_repeated_notice_cannot_manufacture_more_procurement_demand():
    notices=(PUBLIC_CONTRACTOR_BID_DISCOVERY[0],
             PUBLIC_CONTRACTOR_BID_DISCOVERY[0])
    with pytest.raises(ValueError):
        review(notices=notices)


def test_immutable_live_receipt_contains_no_raw_contacts_or_source_ids():
    d=json.loads(RECEIPT.read_text())
    assert d["schema_version"]=="empire.jev.top_sector_demand_gap.v1"
    assert d["status"]=="TOP_THREE_SECTORS_HAVE_RESEARCH_GAPS_NOT_VERIFIED_BUYERS"
    assert d["sector_priority_original_receipt_sha256"]==hashlib.sha256(
        PRIORITY.read_bytes()).hexdigest()
    assert d["original_social_post_publication_date_verified"] is False
    assert d["original_procurement_notices_verified"]==0
    assert d["software_or_marketing_clients_verified"]==0
    assert d["public_source_editorial_admissions"]==0
    assert d["buyer_scout_capacity_matches_verified"]==0
    assert d["outbound_sent"]==0
    assert d["crm_writes"] is False
    assert d["execution_authority"]=="none"
    assert len(d["sector_demand_research"])==3
    assert sum(r["unverified_public_pain_review_candidates"]
               for r in d["sector_demand_research"])==0
    text=RECEIPT.read_text()
    for literal in ("@", "reddit.com", "linkedin.com", "private_evidence_url",
                    "source_sha256", "contact_name", "person_id", "address"):
        assert literal not in text


def test_existing_research_owner_has_specific_queries_without_execution_rights():
    report=review(notices=PUBLIC_CONTRACTOR_BID_DISCOVERY)
    briefs=report["existing_owner_source_discovery_briefs"]
    assert [x["sector"] for x in briefs]==["general_contractor","roofing","hvac"]
    assert all(len(x["research_queries"])==2 for x in briefs)
    assert all(x["automatic_dispatch_authorized"] is False
               and x["outreach_allowed"] is False
               and x["independent_identity_verified"] is False
               and x["client_purchase_intent_verified"] is False
               and x["consumer_data_or_contacts_to_extract"]==0
               and x["owner_review_required"] is True
               for x in briefs)
    assert all("public_rfp" not in x["permitted_source_type_review_scope"]
               for x in briefs)


def test_live_receipt_keeps_contractor_tender_only_as_discovery_not_buyer():
    report=json.loads(RECEIPT.read_text())
    briefs=report["existing_owner_source_discovery_briefs"]
    assert len(briefs)==3
    assert all(x["automatic_dispatch_authorized"] is False for x in briefs)
    notices=report["contractor_work_procurement_discovery_candidates"]
    assert len(notices)==3
    assert all(n["source_class"]==
               "SECONDARY_DISCOVERY_ORIGINAL_NOTICE_REVIEW_REQUIRED" for n in notices)
    assert all(n["buyer_of_empire_leadgen_or_saas_verified"] is False
               for n in notices)
