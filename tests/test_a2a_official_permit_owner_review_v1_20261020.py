"""Official data is research only; never a qualified or contactable HVAC buyer."""
from copy import deepcopy
from hashlib import sha256
from datetime import datetime,timezone
import pytest
from tests.test_a2a_b2b_evidence_mining_v1_20261020 import fixture_data, NOW
from empire_os.a2a_official_permit_owner_review_v1 import permit_owner_review


def receipt():
    return {
        "schema_version":"empire.a2a.official_little_rock_mechanical_permit_research.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "market":"little rock, ar","sector":"hvac",
        "verified_local_hvac_lead_buyers":0,"crm_writes":0,"outbound_messages":0,
        "source_terms_and_commercial_redistribution_cleared":False,
        "personal_contacts_or_property_addresses_exported":False,
        "source_response_observed_at_utc":NOW.isoformat(),
        "source_http_body_sha256":"f"*64,
        "source_layer_url":"https://maps.littlerock.gov/server/rest/services/Permits/MapServer/0",
        "source_records_scanned":5,
        "conservative_business_names_retained":1,
        "source_fresh_within_14_days":False,
        "provider_response_may_be_truncated":True,
        "contractor_company_research_records":[{
            "public_contractor_business_name_for_owner_review":"Example Mechanical LLC",
            "business_name_review_id":sha256(b"little rock, ar|example mechanical llc").hexdigest()[:24],
            "official_permit_object_ids":[1001,1002],
            "business_identity_independently_verified":False,
            "lead_purchase_intent_verified":False,
            "customer_contact_authorized":False,
        }],
    }


def test_official_research_owner_handoff_keeps_stale_info_and_no_dispatch():
    pickup=fixture_data()[1]
    result=permit_owner_review(receipt(),pickup,now=NOW)
    assert result["businesses_for_owner_review_count"]==1
    assert result["source_may_be_truncated"] is True
    assert result["source_state"]=="OFFICIAL_SOURCE_OBSERVED_BUT_PERMIT_ISSUE_DATES_STALE"
    assert not result["owner_inbox_published"]
    assert result["verified_hvac_lead_buyers"]==0
    assert result["owner_tasks_dispatched"]==0
    row=result["public_contractor_businesses_for_owner_review"][0]
    assert row["buyer_scout_ticket_id"]
    assert row["not_a_homeowner_lead"]
    assert row["needs_canonical_company_identity_match"]
    assert not row["contact_authorized"]


def test_missing_official_data_is_unknown_not_zero_demand():
    p=fixture_data()[1]
    out=permit_owner_review(None,p,now=NOW)
    assert out["businesses_for_owner_review_count"] is None
    assert out["source_state"]=="OFFICIAL_SOURCE_NOT_COLLECTED"
    assert out["new_customer_records"]==0


def test_unauthorized_contact_or_budget_claim_rejected():
    p=fixture_data()[1]
    d=receipt()
    d["contractor_company_research_records"][0]["contact_authorized"]=True
    with pytest.raises(ValueError,match="UNVERIFIED"):
        permit_owner_review(d,p,now=NOW)
    d=receipt()
    d["source_terms_and_commercial_redistribution_cleared"]=True
    with pytest.raises(ValueError,match="UNTRUSTED"):
        permit_owner_review(d,p,now=NOW)


def test_unverified_individual_and_bad_identifier_rejected():
    p=fixture_data()[1]
    d=receipt()
    d["contractor_company_research_records"][0]["public_contractor_business_name_for_owner_review"]="Jane Smith"
    with pytest.raises(ValueError,match="UNVERIFIED"):
        permit_owner_review(d,p,now=NOW)
    d=receipt()
    d["contractor_company_research_records"][0]["official_permit_object_ids"]=[-1]
    with pytest.raises(ValueError,match="UNVERIFIABLE"):
        permit_owner_review(d,p,now=NOW)
