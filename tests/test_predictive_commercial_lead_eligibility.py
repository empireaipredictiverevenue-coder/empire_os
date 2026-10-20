"""Per-lead owner preview checks duplicate IDs and keeps qualification unproven."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import pytest
from empire_os.predictive_commercial_requirements import (
    tampa_roofing_founder_example,review_commercial_requirement,
)
from empire_os.predictive_commercial_lead_eligibility import (
    review_lead_eligibility_owner_preview,
)
NOW=datetime(2026,10,20,13,tzinfo=timezone.utc)
H=lambda s:sha256(s.encode()).hexdigest()


def req():
    data=tampa_roofing_founder_example()
    data["zip_codes"]=["33602","33606"]
    return review_commercial_requirement(data,as_of=NOW)


def preview(requirement):
    return {
        "schema_version":"empire.lead_supply.owner_eligibility_preview.v1",
        "source_owner":"existing_lead_supply_intelligence",
        "mode":"OBSERVE","execution_authority":"none",
        "requirement_revision_sha256":requirement["requirement_revision_sha256"],
        "generated_at":NOW.isoformat(),
        "source_owner_message_authenticated":False,"delivery_executed":False,
        "records":[{
            "lead_ref_sha256":H("test_lead_a"),
            "original_event_ref_sha256":H("test_event_a"),
            "zip_code":"33602","source_event_at":NOW.isoformat(),
            "event_type":"consented_form","classification":"owner_claimed_billable",
            "original_consent_proof_authenticated":False,
            "billable_customer_acceptance_verified":False,
            "source_event_delivery_authenticated":False,
        }],
    }


def test_eligible_preview_is_not_authenticated_accepted_lead_inventory():
    r=req()
    out=review_lead_eligibility_owner_preview(r,preview(r),as_of=NOW)
    assert out["status"]=="SOURCE_OWNER_LEAD_PREVIEW_DEDUPED_NOT_AUTHENTICATED"
    assert out["source_owner_observed_records"]==1
    assert out["source_owner_claimed_billable_not_verified"]==1
    assert out["eligible_and_independently_authenticated_customer_leads"] is None
    assert out["real_reserved_leads"] is None
    assert out["original_consent_and_uniqueness_independently_authenticated"] is False
    assert out["database_writes"] is False


def test_missing_owner_preview_reports_unknown_not_zero():
    x=review_lead_eligibility_owner_preview(req(),None,as_of=NOW)
    assert x["status"]=="PER_LEAD_OWNER_AUDIT_NOT_AVAILABLE"
    assert x["source_owner_observed_records"] is None


@pytest.mark.parametrize("field,altered",[
    ("lead_ref_sha256",True),("original_event_ref_sha256",True),
])
def test_duplicate_event_and_lead_identity_never_counted_twice(field,altered):
    r=req();p=preview(r)
    row=deepcopy(p["records"][0])
    if field=="lead_ref_sha256":
        row["original_event_ref_sha256"]=H("different_event")
    else:
        row["lead_ref_sha256"]=H("different_lead")
    p["records"].append(row)
    with pytest.raises(ValueError):
        review_lead_eligibility_owner_preview(r,p,as_of=NOW)


@pytest.mark.parametrize("field,value",[
    ("original_consent_proof_authenticated",True),
    ("billable_customer_acceptance_verified",True),
    ("source_event_delivery_authenticated",True),
    ("zip_code","33699"),("zip_code","PRIVATE_STREET"),
    ("classification","paid_delivered"),
    ("event_type","scraped_social_user"),
    ("lead_ref_sha256","fake"),
    ("source_event_at",(NOW-timedelta(days=150)).isoformat()),
])
def test_stale_fake_consent_wrong_zip_or_false_payment_rejected(field,value):
    r=req();p=preview(r)
    p["records"][0][field]=value
    with pytest.raises(ValueError):
        review_lead_eligibility_owner_preview(r,p,as_of=NOW)


def test_owner_replay_older_than_48_hours_rejected():
    r=req();p=preview(r)
    p["generated_at"]=(NOW-timedelta(days=5)).isoformat()
    with pytest.raises(ValueError):
        review_lead_eligibility_owner_preview(r,p,as_of=NOW)


def test_false_a2a_source_signature_authority_rejected():
    r=req();p=preview(r)
    p["source_owner_message_authenticated"]=True
    with pytest.raises(ValueError):
        review_lead_eligibility_owner_preview(r,p,as_of=NOW)


def test_exact_revision_required_for_original_company_intake():
    r=req();p=preview(r)
    p["requirement_revision_sha256"]=H("different_revision")
    with pytest.raises(ValueError):
        review_lead_eligibility_owner_preview(r,p,as_of=NOW)


def test_suppressed_rejected_and_accepted_source_counts_separated():
    r=req();p=preview(r)
    p["records"][0]["classification"]="duplicate_suppressed"
    p["records"].append({
        **deepcopy(p["records"][0]),
        "lead_ref_sha256":H("new_lead"),"original_event_ref_sha256":H("new_event"),
        "classification":"rejected",
    })
    out=review_lead_eligibility_owner_preview(r,p,as_of=NOW)
    assert out["source_owner_claimed_billable_not_verified"]==0
    assert out["source_owner_suppressed_duplicate_records"]==1
    assert out["source_owner_rejected_or_withdrawn_records"]==1
    assert out["eligible_and_independently_authenticated_customer_leads"] is None
