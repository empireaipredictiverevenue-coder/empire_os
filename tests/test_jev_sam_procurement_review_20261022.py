"""SAM.gov contractor-work notices never become Empire AI SaaS buying leads."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import pytest

from empire_os.jev_sam_procurement_review import reconcile_official_work_notices

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"config/jev_sam_procurement_public_review_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_SAM_OFFICIAL_NOTICE_TRIAGE_20261022.json"
NOW=datetime(2026,10,22,9,0,tzinfo=timezone.utc)


def originals():
    return json.loads(LEDGER.read_text())


def triage(data=None,now=NOW):
    return reconcile_official_work_notices(
        originals() if data is None else data,now=now)


def test_three_sam_official_fields_and_legal_work_classification():
    result=triage()
    assert result["notice_count"]==3
    assert result["status"]=="OFFICIAL_NOTICE_FIELDS_REVIEWED_SEPARATE_CONTRACTOR_WORK_PIPELINE"
    assert [x["notice_id"] for x in result["notices"]]==[
        "140L4326Q0127","36C25727Q0022","W9127826RA089"]
    assert result["deadline_watch_counts"]=={
        "DEADLINE_WITHIN_48_HOURS":1,
        "DEADLINE_WITHIN_SEVEN_DAYS":1,
        "LATER_DEADLINE_OWNER_VERIFY":1,
        "PAST_DEADLINE_NO_BID_INFERENCE":0,
    }
    assert result["notices"][1]["set_aside"]=="SERVICE_DISABLED_VETERAN_OWNED_SMALL_BUSINESS"
    assert result["notices"][0]["naics_code"]=="238220"
    assert result["notices"][2]["naics_code"]=="238990"
    assert result["direct_empire_saas_buying_requests_verified"]==0
    assert result["approved_contractors_for_bid"]==0
    assert result["buyer_scout_payable_lead_buyboxes_verified"]==0
    assert result["automatic_outbound_allowed"] is False
    assert result["crm_writes"] is False
    assert result["financial_actions"] is False
    assert result["model_calls"]==0
    assert result["execution_authority"]=="none"


def test_no_claim_of_live_sam_api_or_original_attachments():
    result=triage()
    assert result["manual_snapshot_recent_for_owner_review"] is True
    for n in result["notices"]:
        assert n["source_listing_reported_active"] is True
        assert n["live_sam_notice_api_state_confirmed"] is False
        assert n["full_bid_package_and_amendments_reviewed"] is False
        assert n["individual_vendor_set_aside_eligibility_verified"] is False
        assert n["public_contract_work_is_not_purchase_of_empire_services"] is True
        assert n["agency_buys_empire_leadgen_or_saas_verified"] is False
        assert n["direct_empire_saas_sales_lead_qualified"] is False
        assert n["brokerage_or_subcontract_eligibility_verified"] is False
        assert n["outreach_authorized"] is False
        assert n["automatic_bid_authorized"] is False


def test_due_date_rolls_to_expired_not_active_bid_opportunity():
    after_hvac=datetime(2026,10,24,0,0,tzinfo=timezone.utc)
    result=triage(now=after_hvac)
    first=result["notices"][0]
    assert first["time_band"]=="PAST_DEADLINE_NO_BID_INFERENCE"
    assert first["time_to_deadline_hours_rounded"]==0
    assert result["deadline_watch_counts"]["PAST_DEADLINE_NO_BID_INFERENCE"]==1
    assert result["automatic_outbound_allowed"] is False


def test_stale_manual_portal_snapshot_flagged_for_reverification():
    later=datetime(2026,10,30,12,tzinfo=timezone.utc)
    result=triage(now=later)
    assert result["manual_snapshot_recent_for_owner_review"] is False
    assert result["direct_empire_saas_buying_requests_verified"]==0
    assert result["approved_contractors_for_bid"]==0


@pytest.mark.parametrize("field,replacement",[
    ("vendor_set_aside_eligibility_verified",True),
    ("agency_purchase_of_leadgen_or_saas_verified",True),
    ("original_attachment_or_piee_package_verified",True),
    ("opportunity_kind","SAAS_PROCUREMENT"),
    ("set_aside","UNRESTRICTED"),
    ("naics_code","541613"),
    ("deadline_local","2027-12-31T14:00:00-06:00"),
    ("last_updated_local_date","2026-10-22"),
    ("exact_url","https://sam.gov/opp/bad/view"),
    ("original_sam_page_reported_status","Inactive"),
])
def test_forged_procurement_terms_or_authority_rejected(field,replacement):
    data=originals()
    data["opportunities"][0][field]=replacement
    with pytest.raises(ValueError):
        triage(data)


@pytest.mark.parametrize("field",[
    "buyer_of_empire_ai_services_verified",
    "bids_or_proposals_authorized","outbound_authorized",
    "sam_notice_attachments_inspected",
    "source_rights_and_vendor_eligibility_approved",
    "live_api_availability_confirmed",
])
def test_global_approval_or_live_api_claims_cannot_be_spoofed(field):
    data=originals()
    data[field]=True
    with pytest.raises(ValueError):
        triage(data)


def test_duplicate_id_rejected():
    data=originals()
    data["opportunities"][2]["notice_id"]=data["opportunities"][0]["notice_id"]
    with pytest.raises(ValueError):
        triage(data)


def test_future_observation_date_rejected():
    with pytest.raises(ValueError):
        triage(now=datetime(2026,10,21,9,tzinfo=timezone.utc))


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        triage(now=datetime(2026,10,22))


def test_runner_receipt_pins_original_evidence_and_checks_prior_shortlist():
    from scripts.review_jev_sam_procurement_20261022 import review_verified_fields
    result=review_verified_fields(now=NOW)
    assert result["historical_research_discovery_shortlist_crosschecked"] is True
    assert result["curated_official_public_field_ledger_sha256"]==sha256(LEDGER.read_bytes()).hexdigest()
    assert result["current_sam_api_or_attachment_query_performed"] is False
    assert result["notice_count"]==3


def test_published_receipt_has_no_contacts_or_email():
    result=json.loads(RECEIPT.read_text())
    assert result["schema_version"]=="empire.jev.sam_public_contract_review.v1"
    assert result["curated_official_public_field_ledger_sha256"]==sha256(LEDGER.read_bytes()).hexdigest()
    assert result["notice_count"]==3
    assert result["direct_empire_saas_buying_requests_verified"]==0
    assert result["automatic_outbound_allowed"] is False
    assert result["current_sam_api_or_attachment_query_performed"] is False
    blob=RECEIPT.read_text()
    assert "@" not in blob
    assert "contracting_officer_email" not in blob
    assert "contact_phone" not in blob
    assert "private_evidence_url" not in blob
