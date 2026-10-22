"""Direct client requests are source hypotheses, not qualified/paid clients."""
from __future__ import annotations
from datetime import datetime, timedelta,timezone
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import json
import pytest

from empire_os.jev_explicit_buyer_source_triage import review_direct_buyer_requests

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"docs/commercial/JEV_DIRECT_B2B_BUYER_REQUEST_SOURCES_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_DIRECT_B2B_PURCHASE_NEED_PRIORITY_20261022.json"
BUYER=Path("/srv/empire_os/runtime/buyer_capacity_readiness/latest.json")
CLOCK=datetime(2026,10,22,14,55,tzinfo=timezone.utc)


def sample():
    return json.loads(SOURCE.read_text())


def capacity():
    b=json.loads(BUYER.read_text())
    b["observed_at"]=(CLOCK-timedelta(minutes=4)).isoformat()
    return b


def review(rows=None,buyer=None):
    return review_direct_buyer_requests(sample() if rows is None else rows,
        as_of=CLOCK,buyer_capacity=capacity() if buyer is None else buyer)


def test_five_original_explicit_needs_ranked_by_evidence_and_delivery_fit():
    r=review()
    assert r["distinct_public_purchase_need_posts"]==5
    assert [x["case_id"] for x in r["cases"]]==[
        "freelancer_40778550","reddit_wp_1woeuix",
        "reddit_legal_1x46cup","reddit_agency_1w7wwwe",
        "reddit_old_1uk1vw1"]
    assert r["buyer_capacity_aggregate_status"]=="NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert r["verified_business_buyers"]==0
    assert r["officially_awarded_business_orders"]==0
    assert r["government_work_procurements_excluded"] is True
    assert r["live_bids_submitted"]==0
    assert r["outbound_sent"]==0
    assert r["database_writes"] is False


def test_first_route_has_official_platform_project_and_unapproved_bid():
    r=review()
    x=r["cases"][0]
    assert x["case_id"]=="freelancer_40778550"
    assert x["original_posted_price_code"]=="PUBLIC_ADVERTISED_BUDGET_AUD_250_TO_750"
    assert x["research_lane"]=="PLATFORM_SCOPED_APPLICATION_OWNER_REVIEW"
    assert "WORDPRESS_WORK" in " ".join(x["next_existing_owner_checks"])
    assert x["applicant_contact_or_bid_approved"] is False
    assert x["purchase_or_payment_contract_verified"] is False


def test_aged_june_offer_cannot_look_like_new_customer():
    r=review()
    old=r["cases"][-1]
    assert old["age_days_at_review"]>90
    assert old["research_lane"]=="STALE_LOW_UNIT_ECONOMICS_RECONFIRMATION_HOLD"
    assert old["qualified_pipeline_revenue"] is False


@pytest.mark.parametrize("index,field,value",[
    (0,"posted_date","2026-10-21"),
    (0,"source_kind","PUBLIC_HIRING_POST"),
    (0,"payment_proof","UNVERIFIED"),
    (0,"priced","USD_5000"),
    (0,"url","https://freelancer.com/elsewhere"),
    (0,"legal_company_id_verified",True),
    (0,"fulfilment_capability_verified",True),
    (0,"market","US"),
    (0,"sector","legal"),
    (0,"scope","OTHER"),
    (2,"id","freelancer_40778550"),
    (3,"need","DIRECT_WORDPRESS_WEB_DEVELOPMENT"),
])
def test_cannot_forge_a_public_advert_or_buyer_rights(index,field,value):
    s=sample()
    s["source_posts"][index][field]=value
    with pytest.raises(ValueError):
        review(rows=s)


@pytest.mark.parametrize("field,value",[
    ("legal_buyer_identity_verified",True),
    ("commercial_terms_signed",True),
    ("automated_outbound_authorized",True),
    ("public_pages_checked_in_web_review",False),
    ("lawful_use_of_republished_content_not_verified",False),
])
def test_overall_commercial_gates_fail_closed(field,value):
    s=sample()
    s[field]=value
    with pytest.raises(ValueError):
        review(rows=s)


def test_positive_aggregate_buyers_cannot_become_signed_first_party_contract():
    b=capacity()
    b.update(capacity_verified=3,terms_verified=2,delivery_verified=2)
    r=review(buyer=b)
    assert r["verified_business_buyers"]==0
    assert all(x["specific_business_buybox_verified"] is False for x in r["cases"])


def test_receipt_is_immutable_aggregate_only_no_contacts_or_payout():
    r=json.loads(RECEIPT.read_text())
    assert r["schema_version"]=="empire.jev.direct_b2b_buying_need_review.v1"
    assert r["distinct_public_purchase_need_posts"]==5
    assert r["pinned_external_source_sha256"]==sha256(SOURCE.read_bytes()).hexdigest()
    assert r["verified_business_buyers"]==0
    assert r["paid_customer_acceptance_verified"] is False
    assert r["officially_awarded_business_orders"]==0
    assert r["live_bids_submitted"]==0
    assert r["crm_writes"] is False
    assert r["outbound_sent"]==0
    body=RECEIPT.read_text()
    assert "@" not in body
    assert "contact_email" not in body
    assert "phone_number" not in body
    assert "private_profile" not in body
