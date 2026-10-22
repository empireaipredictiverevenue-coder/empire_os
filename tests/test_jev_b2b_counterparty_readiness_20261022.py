"""External supplier claims cannot bypass company, source, CRM or supply proof."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import pytest

from empire_os.jev_b2b_counterparty_readiness import audit_public_b2b_counterparties

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_CANDIDATES_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_B2B_SUPPLIER_REQUESTS_COUNTERPARTY_READINESS_20261022.json"
CAPACITY=Path("/srv/empire_os/runtime/buyer_capacity_readiness/latest.json")
ROUTE=Path("/srv/empire_os/runtime/revenue/lead_smart/ringba/routing_observation/latest.json")
AS_OF=datetime(2026,10,22,12,55,tzinfo=timezone.utc)


def originals():
    return json.loads(BASE.read_text())


def capacity():
    c=json.loads(CAPACITY.read_text())
    c["observed_at"]="2026-10-22T12:45:00+00:00"
    return c


def routing():
    return json.loads(ROUTE.read_text())


def audit(*,source=None,buyer=None,route=None):
    return audit_public_b2b_counterparties(
        originals() if source is None else source,
        buyer_capacity=capacity() if buyer is None else buyer,
        existing_roofing_route=routing() if route is None else route,
        as_of=AS_OF,
    )


def test_cases_have_explicit_proof_gaps():
    r=audit()
    assert r["schema_version"]=="empire.jev.b2b_counterparty_readiness.v1"
    assert r["public_source_posts_reviewed"]==8
    assert r["counterparties_assessed"]==2
    assert r["verified_named_buyer_companies"]==0
    assert r["buyer_scout_aggregate_status"]=="NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert r["buyer_scout_is_not_supplier_inventory_proof"] is True
    assert r["ready_to_deliver"] is False
    assert r["ready_to_contact"] is False
    assert r["actual_supply_committed"]==0
    assert r["outbound_sent"]==0
    assert r["crm_writes"] is False
    assert r["execution_authority"]=="none"
    assert {x["public_post_id"] for x in r["cases"]}=={"1wciats","1uk1vw1"}


def test_tennessee_company_and_organic_appointment_constraints():
    r=audit()
    roofing=next(x for x in r["cases"] if x["public_post_id"]=="1wciats")
    assert "Knoxville" in roofing["claimed_business_region"]
    assert roofing["self_stated_terms"]=="TEN_PERCENT_CLOSED_DEAL_NO_UPFRONT_FEE"
    assert "CLOSED_DEAL_ATTRIBUTION" in " ".join(roofing["next_owner_checks"])
    assert roofing["organic_compliant_source_supply_proven"] is False
    assert roofing["revenue_share_attribution_or_batch_acceptance_verified"] is False
    assert roofing["automatic_contact_allowed"] is False


def test_web_agency_age_and_lawful_business_data_hold():
    r=audit()
    agency=next(x for x in r["cases"] if x["public_post_id"]=="1uk1vw1")
    assert agency["self_stated_terms"]=="USD_150_PER_ACCEPTED_50_LEADS_PLUS_TEN_PERCENT_PAID_CLOSE"
    assert agency["feasibility_status"]=="STALE_REQUEST_AND_BUSINESS_DATA_RIGHTS_REVALIDATION_REQUIRED"
    assert agency["source_and_contact_data_rights_verified"] is False
    assert agency["legal_business_identity_verified"] is False
    assert agency["automatic_contact_allowed"] is False
    assert "BUSINESS_ONLY_DATA_USAGE" in " ".join(agency["next_owner_checks"])


def test_buyer_scout_positive_aggregates_still_not_a_specific_contract():
    c=capacity()
    c.update(capacity_verified=4,terms_verified=3,
             delivery_verified=2,commercially_activated=1)
    r=audit(buyer=c)
    assert r["buyer_scout_aggregate_status"]=="AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX"
    assert r["actual_supply_committed"]==0
    assert all(x["specific_buybox_with_signed_terms_verified"] is False
               for x in r["cases"])
    assert r["ready_to_contact"] is False


def test_old_other_market_call_route_cannot_prove_knoxville_organic_supply():
    route=routing()
    route["routing_runtime_verified"]=True
    r=audit(route=route)
    assert r["existing_other_market_roofing_route"]["proof_of_tennessee_organic_supply"] is False
    assert r["ready_to_deliver"] is False


@pytest.mark.parametrize("field,value",[
    ("crm_writes",True),("outbound_sent",1),
    ("original_business_identity_verified",True),
    ("source_license_verified",True),("consent_to_contact_verified",True),
])
def test_original_public_source_authority_forgery_fails_closed(field,value):
    source=originals()
    source[field]=value
    with pytest.raises(ValueError):
        audit(source=source)


@pytest.mark.parametrize("field,value",[
    ("route_mutation_performed",True),("test_call_performed",True),
    ("mode","EXECUTE")
])
def test_modified_route_authority_rejected(field,value):
    r=routing()
    r[field]=value
    with pytest.raises(ValueError):
        audit(route=r)


def test_naive_clock_fails_closed():
    with pytest.raises(ValueError):
        audit_public_b2b_counterparties(
            originals(),buyer_capacity=None,existing_roofing_route=None,
            as_of=datetime(2026,10,22,12))


def test_pinned_commercial_receipt_is_review_only():
    result=json.loads(RECEIPT.read_text())
    assert result["original_public_manual_source_sha256"]==sha256(BASE.read_bytes()).hexdigest()
    assert result["public_source_posts_reviewed"]==8
    assert result["counterparties_assessed"]==2
    assert result["verified_named_buyer_companies"]==0
    assert result["current_buying_commitments_verified"]==0
    assert result["source_licensing_or_contact_consent_verified"] is False
    assert result["outbound_sent"]==0
    assert result["crm_writes"] is False
    assert result["payments_moved"] is False
    text=RECEIPT.read_text()
    assert "@" not in text
    assert "phone_number" not in text
    assert "contact_email" not in text
    assert "individual_lead_id" not in text
