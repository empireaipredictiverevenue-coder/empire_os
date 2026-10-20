"""US permit date truth + bounded UK official procurement economic research."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import pytest

from test_permit_project_intelligence_20261018 import record, fixture
from test_public_source_sweep import tender
from empire_os.permit_project_intelligence import analyze_permit_project_intelligence
from empire_os.uk_public_tender_observer import normalize_uk_tender_releases
from empire_os.predictive_primary_source_economic_bridge import (
    review_existing_permit_owner, review_existing_uk_tender_owner,
    build_primary_source_economic_review,
)

NOW=datetime(2026,10,20,12,0,tzinfo=timezone.utc)


def permit_fixture(tmp_path,*,recent=False):
    event=record(job="402424052", filing="10/19/2026" if recent else "02/09/2007")
    event["created_at"]=NOW.isoformat()
    event["last_seen_at"]=NOW.isoformat()
    fixture(tmp_path,[event],market=False)
    return analyze_permit_project_intelligence(tmp_path,now=NOW)


def tender_fixture():
    return normalize_uk_tender_releases(tender(),as_of=NOW)


def test_original_historical_permit_is_not_new_project_or_buyer(tmp_path):
    packet=permit_fixture(tmp_path)
    x=review_existing_permit_owner(packet,as_of=NOW)
    assert x["status"]=="PERMIT_SOURCE_CHRONOLOGY_TRIAGED"
    assert x["research_observation_count"]==1
    assert x["historical_project_source_count"]==1
    assert x["original_recent_filing_or_issuance_count"]==0
    assert x["source_research_cards"][0]["research_action"]=="NO_NEW_PROJECT_CLAIM_FROM_HISTORICAL_FILING"
    assert x["actionable_current_business_count"] is None
    assert x["actual_revenue_or_margin_verified"] is False
    assert x["opportunity_metro_scope"]=="NYC_ORIGINAL_SOURCE_ONLY"
    out=json.dumps(x)
    assert "Private Person" not in out
    assert "Private Owner Corporation" not in out
    assert "PRIVATE STREET" not in out


def test_actual_recent_official_filing_is_still_not_purchase(tmp_path):
    packet=permit_fixture(tmp_path,recent=True)
    x=review_existing_permit_owner(packet,as_of=NOW)
    assert x["original_recent_filing_or_issuance_count"]==1
    assert x["source_research_cards"][0]["source_original_recent_project_event"] is True
    assert x["source_research_cards"][0]["research_action"]=="VERIFY_ORIGINAL_PROJECT_AND_SERVICE_SCOPE"
    assert x["source_research_cards"][0]["permit_owner_and_permittee_independently_authenticated"] is False
    assert x["source_research_cards"][0]["source_original_recent_project_is_paying_customer"] is False


def test_uk_tender_original_ocds_sample_matches_cpv_not_contract_sales():
    original=tender_fixture()
    x=review_existing_uk_tender_owner(original,as_of=NOW)
    assert x["status"]=="UK_TENDER_SOURCE_STAGE_TRIAGED"
    assert x["research_observation_count"]==2
    assert x["original_cpv_relevant_notice_count"]==2
    assert x["source_sample_limited_to_five_releases"] is True
    assert x["original_source_is_contract_award"] is False
    assert any("solar" in r["original_cpv_niches"] for r in x["source_research_cards"])
    assert any(r["research_action"]=="REVIEW_ORIGINAL_NOTICE_ELIGIBILITY_AND_CAPACITY"
               for r in x["source_research_cards"])
    assert all(r["tender_publication_is_contract_award"] is False for r in x["source_research_cards"])
    assert all(r["respond_to_bid_authorized"] is False for r in x["source_research_cards"])
    assert all(r["country_scope"]=="GB" for r in x["source_research_cards"])
    assert "example" not in json.dumps(x)


def test_independent_us_and_gb_source_summaries_are_never_summed_as_buyers(tmp_path):
    result=build_primary_source_economic_review(permit_fixture(tmp_path,recent=True),
                                                 tender_fixture(),as_of=NOW)
    assert result["status"]=="PRIMARY_PROJECT_AND_PROCUREMENT_ECONOMIC_TRIAGE_REVIEWED"
    assert result["source_owner_count"]==2
    assert result["country_and_territory_source_scopes_are_joined"] is False
    assert result["customer_revenue_or_profit_recognized"] is False
    assert result["external_source_is_first_party_customer_purchase"] is False
    assert result["historical_import_means_recent_building_demand"] is False
    assert result["aggregate_opportunity_market_size_inferred"] is False
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False


def test_unavailable_tender_is_unknown_not_claim_that_no_tenders_exist(tmp_path):
    output=build_primary_source_economic_review(permit_fixture(tmp_path),None,as_of=NOW)
    t=output["sources"]["gb_public_procurement"]
    assert t["status"]=="TENDER_OWNER_SOURCE_UNAVAILABLE"
    assert t["research_observation_count"] is None
    assert t["source_research_cards"]==[]
    assert output["tender_notice_is_guaranteed_sale"] is False


@pytest.mark.parametrize("which,field,value,reason",[
    ("permit","automatic_sales_promotion",True,"PERMIT_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("permit","buyer_matched",True,"PERMIT_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("permit","recognised_revenue_proven",True,"PERMIT_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("permit","execution_authority","send","PERMIT_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("permit","review_dossier_count",500,"PERMIT_OWNER_COUNTS_OR_REVISION_HOLD"),
    ("permit","generated_at","2030-01-01T00:00:00+00:00","PERMIT_OWNER_SOURCE_STALE_HOLD"),
    ("tender","outreach_or_bid_authorized",True,"TENDER_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("tender","actual_contract_or_revenue_proven",True,"TENDER_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("tender","payment_authorized",True,"TENDER_OWNER_AUTHORITY_OR_SCHEMA_HOLD"),
    ("tender","record_count_in_bounded_page",True,"TENDER_SOURCE_COUNT_HOLD"),
    ("tender","tender_status_counts_in_page",{"active":500},"TENDER_OWNER_RELEASE_CONTRACT_HOLD"),
    ("tender","generated_at","2026-10-01T00:00:00+00:00","TENDER_SOURCE_STALE_HOLD"),
])
def test_authority_time_and_count_forgery_hold(tmp_path,which,field,value,reason):
    packet=permit_fixture(tmp_path) if which=="permit" else tender_fixture()
    packet=deepcopy(packet)
    packet[field]=value
    func=review_existing_permit_owner if which=="permit" else review_existing_uk_tender_owner
    out=func(packet,as_of=NOW)
    assert out["status"]==reason
    assert out["actionable_current_business_count"] is None


@pytest.mark.parametrize("field,value",[
    ("notice_is_contract_award",True),
    ("buyer_acceptance_or_payment_verified",True),
    ("future_submissions_deadline_evidenced","yes"),
    ("source_semantic_digest","pretend-verified"),
    ("source_reported_tender_status","UNRESTRICTED"),
])
def test_tender_stage_cannot_fake_bid_acceptance_or_revenue(field,value):
    packet=deepcopy(tender_fixture())
    packet["source_observations"][0][field]=value
    output=review_existing_uk_tender_owner(packet,as_of=NOW)
    assert output["status"]=="TENDER_OWNER_RELEASE_CONTRACT_HOLD"
    assert output["source_research_cards"]==[]
    assert output["actual_revenue_or_margin_verified"] is False


def test_original_permit_dossier_cannot_self_certify_buyer(tmp_path):
    packet=permit_fixture(tmp_path)
    packet["review_dossiers"][0]["buyer_demand_proven"]=True
    assert review_existing_permit_owner(packet,as_of=NOW)["status"]=="PERMIT_OWNER_COUNTER_OR_DOSSIER_HOLD"


def test_different_source_revision_not_generated_by_clock_rollover():
    p=tender_fixture()
    x=review_existing_uk_tender_owner(p,as_of=NOW)
    y=review_existing_uk_tender_owner(p,as_of=NOW+timedelta(hours=1))
    assert x["source_revision_sha256"]==y["source_revision_sha256"]
