"""Original public official land-guide score/deadline evidence; no bid authority."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import pytest

from scripts import reconcile_land_guide_public_official_notice_20261024 as mod

NOW=datetime(2026,10,24,13,0,tzinfo=timezone.utc)
ROWS={
    "ocid":mod.CF_OCID,
    "official_notice_url":mod.CF_NOTICE,
    "title":"CA18567 - "+mod.EXPECTED_TITLE,
    "policy_or_supplier_hold":"HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT",
    "tender_closes_at_utc":"2026-10-30T12:00:00+00:00",
    "published_estimated_value_gbp":"25000.00",
    "published_value_source":"OFFICIAL_OCDS_TENDER_VALUE_NOT_BINDING",
    "published_sme_suitable":True,
    "bid_authorized":False,
    "bid_eligible":False,
    "contact_authorized":False,
}
TEXT = """UK4 RFQ 2026/43 - Development of a Dublin Belfast Economic Corridor Investment Land Guide
Summary OCID: ocds-h6vhtk-0787b9
Published by: Newry, Mourne and Down District Council (NMD)
Deadline date: 31 October 2026
Notice type: UK4 Has documents: No
Full notice text Scope Procurement reference CA18567
Procurement description The DBEC Partnership wishes to appoint a suitably qualified and experienced consultant
Total value (estimated, excluding VAT) 25000.00 GBP to 25000.00GBP
Contract dates (estimated) 30 November 2026 to 31 March 2027
Procedure Below threshold - open competition
Award criteria Type: price Name As per RFQ Documentation Description As per RFQ Documentation
Weighting: 20.00 Weighting type: percentageExact
Type: quality Name As per RFQ Documentation Description As per RFQ Documentation
Weighting: 80.00 Weighting type: percentageExact
Submission Tender submission deadline 30 October 2026, 12:00PM
Enquiry deadline 26 October 2026, 12:00PM
To access this opportunity, log in to https://suppliers.multiquote.com and view the opportunity CA18567.
"""
def deadline():
    return {"status":"DEADLINES_TRIAGED_REVIEW_ONLY",
            "external_bids_authorized":False,"source_qualified_customer_count":0,
            "items":[dict(ROWS)]}


def response(body=TEXT):
    return {"status":200,"url":mod.SOURCE_URL,"mime":"text/html",
            "raw":("<html><body>"+body+"</body></html>").encode()}


def test_strict_official_source_weights_no_bid_rights():
    result=mod.verify_primary_notices(
        deadline_review=deadline(),fetch=lambda u:response(),observed_at=NOW)
    assert result["status"]==mod.READY
    assert result["published_quality_weight_pct"]==80
    assert result["published_price_weight_pct"]==20
    assert result["official_full_notice_submit_at_utc"]=="2026-10-30T12:00:00+00:00"
    assert result["official_full_notice_questions_until_utc"]=="2026-10-26T12:00:00+00:00"
    assert result["public_summary_displays_different_deadline"]=="2026-10-31"
    assert result["summary_and_full_notice_deadline_disagree"] is True
    assert result["submit_date_authoritatively_reconciled_with_portal"] is False
    assert result["scoring_subcriteria_from_full_rfq_verified"] is False
    assert result["full_supplier_rfq_verified"] is False
    assert result["supplier_eligibility_verified"] is False
    assert result["buyer_contacted"] is False
    assert result["bid_submitted"] is False
    assert result["crm_writes"] is False
    assert result["customer_revenue_verified"] is False
    assert result["primary_sell2wales_public_page_sha256"]==sha256(response()["raw"]).hexdigest()


@pytest.mark.parametrize("mutation",[
    "quality","price","reference","government_ocid","submission","enquiry",
    "summary","portal","no_documents","company","source_host",
    "redirect","wrong_type","http","body_short","not_get",
])
def test_changed_public_terms_and_transport_hold_fail_closed(mutation):
    fake=response()
    txt=fake["raw"].decode()
    subs={
        "quality":("Weighting: 80.00","Weighting: 90.00"),
        "price":("Weighting: 20.00","Weighting: 10.00"),
        "reference":("CA18567","CA18568"),
        "government_ocid":("ocds-h6vhtk-0787b9","ocds-h6vhtk-unknown"),
        "submission":("30 October 2026, 12:00PM","29 October 2026, 12:00PM"),
        "enquiry":("26 October 2026, 12:00PM","25 October 2026, 12:00PM"),
        "summary":("31 October 2026","1 November 2026"),
        "portal":("https://suppliers.multiquote.com","https://evil.test"),
        "no_documents":("Has documents: No","Has documents: Yes"),
        "company":("Newry, Mourne and Down District Council (NMD)","Unknown Council"),
    }
    if mutation in subs:
        a,b=subs[mutation];txt=txt.replace(a,b)
        fake["raw"]=txt.encode()
    elif mutation=="source_host":fake["url"]="https://evil.test/notice"
    elif mutation=="redirect":fake["url"]="https://www.sell2wales.gov.wales/redirect"
    elif mutation=="wrong_type":fake["mime"]="text/plain"
    elif mutation=="http":fake["status"]=404
    elif mutation=="body_short":fake["raw"]=b"hello"
    else:fake["raw"]=None
    result=mod.verify_primary_notices(
        deadline_review=deadline(),fetch=lambda u:fake,observed_at=NOW)
    assert result["status"]==mod.HELD
    assert result["bid_submitted"] is False
    assert result["full_supplier_rfq_verified"] is False
    assert result["buyer_contacted"] is False


def test_source_mismatch_blocks_even_true_external_website():
    for key,bad in (
        ("published_estimated_value_gbp","30000.00"),
        ("bid_authorized",True),
        ("published_sme_suitable",False),
        ("tender_closes_at_utc","2026-11-01T12:00:00+00:00"),
    ):
        research=deadline()
        research["items"][0][key]=bad
        result=mod.verify_primary_notices(
            deadline_review=research,fetch=lambda u:response(),observed_at=NOW)
        assert result["status"]==mod.HELD
        assert result["bid_ready"] is False


def test_private_mode_atomic_and_symlink_denial(tmp_path):
    report=mod.verify_primary_notices(
        deadline_review=deadline(),fetch=lambda u:response(),observed_at=NOW)
    folder=tmp_path/mod.OUTPUT.parent
    folder.mkdir(parents=True)
    folder.chmod(0o700)
    target=mod.write_private(tmp_path,report)
    assert target.stat().st_mode&0o077==0
    assert json.loads(target.read_text())["supplier_eligibility_verified"] is False
    target.unlink()
    outside=tmp_path/"untouched"
    outside.write_text("KEEP")
    target.symlink_to(outside)
    with pytest.raises(ValueError):
        mod.write_private(tmp_path,report)
    assert outside.read_text()=="KEEP"
    with pytest.raises(ValueError):
        mod.write_private(tmp_path,mod.verify_primary_notices(
            deadline_review={},observed_at=NOW,fetch=lambda _:response()))
