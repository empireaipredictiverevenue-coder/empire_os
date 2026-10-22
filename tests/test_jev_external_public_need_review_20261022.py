"""Independent web source discovery is not verified business ownership."""
from copy import deepcopy
from datetime import date,timedelta
from hashlib import sha256
import json
from pathlib import Path
import pytest

from empire_os.jev_external_public_need_review import review_public_b2b_needs

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_CANDIDATES_20261022.json"
OUTPUT=ROOT/"docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_REVIEW_20261022.json"
NOW=date(2026,10,22)


def evidence():
    return json.loads(SOURCE.read_text())


def audit(data=None):
    return review_public_b2b_needs(evidence() if data is None else data,as_of=NOW)


def test_eight_public_original_page_observations_not_eight_named_prospects():
    out=audit()
    assert out["original_source_pages_observed_in_web_review"]==8
    assert out["markets"]=={"GB":1,"US":7}
    assert out["direct_claims_of_provider_search"]==2
    assert out["lanes"]=={
        "ORIGINAL_BUSINESS_AND_TERMS_REVIEW":1,
        "ORIGINAL_COMPANY_NEED_AND_SOLUTION_FIT_REVIEW":2,
        "PUBLIC_MARKET_RESEARCH_ONLY":1,
        "ROLE_OR_BUYER_AUTHORITY_HOLD":3,
        "STALE_PURCHASE_REQUEST_REVALIDATION_REQUIRED":1,
    }
    assert out["verified_legal_business_buyers"]==0
    assert out["b2b_lead_sales_ready"]==0
    assert out["approved_outbound_messages"]==0
    assert out["crm_writes"] is False
    assert out["model_calls"]==0


def test_tennessee_direct_need_requires_commercial_proof_and_consent():
    one=next(x for x in audit()["items"] if x["public_post_id"]=="1wciats")
    assert one["proposed_review_lane"]=="ORIGINAL_BUSINESS_AND_TERMS_REVIEW"
    assert one["payment_or_data_rights_risk_review"] is True
    assert one["commercial_terms_verified"] is False
    assert one["original_business_identity_verified"] is False
    assert one["outreach_authorized"] is False


def test_web_agency_specific_offer_is_old_and_phone_data_rights_unproven():
    one=next(x for x in audit()["items"] if x["public_post_id"]=="1uk1vw1")
    assert one["source_age_days"]>90
    assert one["proposed_review_lane"]=="STALE_PURCHASE_REQUEST_REVALIDATION_REQUIRED"
    assert one["payment_or_data_rights_risk_review"] is True
    assert one["buyer_scout_promotion_authorized"] is False


@pytest.mark.parametrize("index,field,new",[
    (0,"actual_service_purchase_verified",True),
    (0,"verified_business_name",True),
    (0,"request","MARKET_DISCUSSION"),
    (0,"market","GB"),
    (0,"date","2026-10-22"),
    (0,"risk","NOT_EXPLICIT_VENDOR_HIRE"),
    (0,"source_url","https://other-site.invalid/post"),
    (0,"source_url","https://www.reddit.com/r/LeadGenMarketplace/comments/1wciats/roofing_lead_generation/?email=x"),
    (1,"id","1wciats"),
    (4,"sector","roofing"),
])
def test_identity_or_direct_buyer_injection_does_not_promote(index,field,new):
    data=evidence()
    data["rows"][index][field]=new
    with pytest.raises(ValueError):
        audit(data)


@pytest.mark.parametrize("field,new",[
    ("server_api_original_fetch_success",True),
    ("source_license_verified",True),
    ("original_business_identity_verified",True),
    ("consent_to_contact_verified",True),
    ("automatic_research_import_authorized",True),
    ("crm_writes",True),
    ("outbound_sent",1),
])
def test_spoofed_global_authority_rejected(field,new):
    data=evidence()
    data[field]=new
    with pytest.raises(ValueError):
        audit(data)


def test_unverified_source_only_stays_owner_review_and_no_raw_person_contacts():
    result=audit()
    assert all(x["recommended_research_owner"]=="existing_jev_intent_research_owner"
               and x["outreach_authorized"] is False
               and x["crm_insertion_authorized"] is False
               and x["current_demand_confirmed"] is False
               and x["existing_crm_relationship_and_suppression_checked"] is False
               for x in result["items"])
    blob=json.dumps(result)
    assert "@" not in blob
    assert "contact_name" not in blob
    assert "phone_number" not in blob
    assert "private_email" not in blob


def test_receipt_has_pinned_manual_source_digest_and_no_promotions():
    from scripts.review_jev_public_b2b_sources_20261022 import run
    a=run()
    saved=json.loads(OUTPUT.read_text())
    assert saved==a
    assert saved["original_manual_public_web_review_source_sha256"]==sha256(SOURCE.read_bytes()).hexdigest()
    assert saved["original_page_fetch_to_empireos_server_successful"] is False
    assert saved["original_business_identity_or_rights_admitted"] is False
    assert saved["approved_outbound_messages"]==0


def test_invalid_review_date_refused():
    with pytest.raises(ValueError):
        review_public_b2b_needs(evidence(),as_of=NOW+timedelta(days=1))
