"""Internal supply workflow QA; fictional tests cannot authorize real resale."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest

from empire_os.jev_internal_b2b_sample_qa import review_internal_business_sample
from scripts.review_jev_internal_supply_sample_20261022 import run_qa

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"docs/commercial/JEV_WEB_AGENCY_SYNTHETIC_SUPPLY_SAMPLE_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_WEB_AGENCY_SYNTHETIC_QA_CANARY_20261022.json"


def example():
    return json.loads(FIXTURE.read_text())


def qa(row=None):
    return review_internal_business_sample(example() if row is None else row)


def test_eleven_fictional_record_canary_and_all_dispositions():
    r=qa()
    assert r["synthetic_records_checked"]==11
    assert r["synthetic_distinct_domains"]==10
    assert r["synthetic_qa_pattern_passes"]==2
    assert r["synthetic_lane_counts"]=={
        "BUSINESS_IDENTITY_HOLD":1,
        "DUPLICATE_DOMAIN":1,
        "INCONCLUSIVE_WEBSITE_STATUS":1,
        "LISTING_OMISSION_NOT_WEBSITE_ABSENCE":1,
        "ORIGINAL_SOURCE_REVIEW_HOLD":1,
        "PRIMARY_SITE_EXAMINATION_REQUIRED":1,
        "REVIEWER_DISAGREEMENT_HOLD":1,
        "SOURCE_RIGHTS_HOLD":1,
        "SYNTHETIC_QA_PATTERN_MATCH_ONLY":2,
        "VALID_WEBSITE_NOT_A_NEED_SIGNAL":1,
    }
    assert r["actual_available_accepted_records"]==0
    assert r["actual_business_records_evaluated"]==0
    assert r["current_buyers_or_paid_orders_verified"]==0
    assert r["outbound_sent"]==0
    assert r["database_writes"] is False
    assert r["execution_authority"]=="none"


def test_listing_without_website_field_is_not_a_no_website_lead():
    r=qa()
    s=next(x for x in r["fictional_qa_decisions"] if x["fixture_key"]=="SYN-CC")
    assert s["qa_lane"]=="LISTING_OMISSION_NOT_WEBSITE_ABSENCE"
    assert s["synthetic_workflow_pattern_pass"] is False


def test_duplicate_not_double_counted():
    r=qa()
    dup=next(x for x in r["fictional_qa_decisions"] if x["fixture_key"]=="SYN-BB")
    assert dup["qa_lane"]=="DUPLICATE_DOMAIN"
    assert dup["actual_lead_accepted_by_buyer"] is False


@pytest.mark.parametrize("key,value",[
    ("real_business_count",1),("contact_details_included",True),
    ("commercial_send_authorized",True),
    ("source_licensing_of_real_records_verified",True),
    ("mode","LIVE"),("schema_version","bad"),
])
def test_forged_real_data_or_contact_authority_rejected(key,value):
    sample=example()
    sample[key]=value
    with pytest.raises(ValueError):
        qa(sample)


@pytest.mark.parametrize("field,value",[
    ("fictional_domain","gmail.com"),
    ("fictional_domain","https://test.example/"),
    ("company_is_fictional",False),
    ("personal_contact_included",True),
    ("business_only",False),
    ("source_review_complete","yes"),
    ("mock_reuse_rights_pass",1),
    ("reviewer_one_classification","NO_WEBSITE_CONFIRMED"),
])
def test_personal_data_untrusted_business_or_bad_review_status_rejected(field,value):
    sample=example()
    sample["rows"][0][field]=value
    with pytest.raises(ValueError):
        qa(sample)


def test_source_rights_hold_precedes_any_quality_promotion():
    sample=example()
    sample["rows"][0]["mock_reuse_rights_pass"]=False
    r=qa(sample)
    original=next(x for x in r["fictional_qa_decisions"] if x["fixture_key"]=="SYN-AA")
    assert original["qa_lane"]=="SOURCE_RIGHTS_HOLD"
    assert original["actual_company_verified"] is False


def test_unverified_source_is_not_a_sellable_company_record():
    for d in qa()["fictional_qa_decisions"]:
        assert d["contact_or_delivery_permitted"] is False
        assert d["actual_company_verified"] is False
        assert d["actual_website_verified"] is False
        assert d["live_data_licence_verified"] is False


def test_stated_50_record_150_usd_offer_is_conditional_only():
    r=qa()
    assert r["requested_full_batch_size"]==50
    assert r["conditional_gross_full_batch_usd"]==150
    assert r["conditional_average_gross_per_accepted_if_all_fifty_accepted_usd"]==3
    assert r["partial_batch_payment_terms_confirmed"] is False
    assert r["commercial_offer_ready"] is False


def test_forged_buyer_pricing_not_accepted():
    with pytest.raises(ValueError):
        review_internal_business_sample(example(),stated_base_payment_usd=500)


def test_immutable_private_review_protects_no_delivery_authority():
    saved=json.loads(RECEIPT.read_text())
    assert saved["synthetic_fixture_sha256"]==sha256(FIXTURE.read_bytes()).hexdigest()
    assert saved["independent_source_licence_and_contact_rights_proven"] is False
    assert saved["original_website_fetches_performed"]==0
    assert saved["recipient_names_or_contacts_collected"]==0
    assert saved["actual_available_accepted_records"]==0
    assert saved["customer_delivery_authorized"] is False
    assert saved["execution_authority"]=="none"
    assert "@" not in RECEIPT.read_text()
    assert run_qa()==saved
