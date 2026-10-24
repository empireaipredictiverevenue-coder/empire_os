"""Supplier-fit and hypothetical unit economics never imply bid authority."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import json
import os
import pytest

from scripts.review_official_tender_bid_no_bid_20261024 import (
    decide, hypothetical_margin, review_live, write_private,
    STATUS_READY, STATUS_HELD, OUTPUT,
)

NOW=datetime(2026,10,24,10,0,tzinfo=timezone.utc)
STAMP=(NOW-timedelta(minutes=10)).isoformat()


def item(*,title="GDPR Data Audit", ocid="ocds-abc", deadline=None,
         decision="HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT",
         urgency="DUE_WITHIN_72_HOURS", source="contracts_finder"):
    return {
        "source":source,"ocid":ocid,"title":title,
        "buyer_organisation":"Council",
        "official_notice_url":"https://www.contractsfinder.service.gov.uk/Notice/5f4d9841-b30a-42bb-b122-3f7758606443",
        "deadline_urgency":urgency,
        "tender_closes_at_utc":deadline or (NOW+timedelta(hours=40)).isoformat(),
        "deadline_last_confirmed_by_aggregated_feed_at_utc":STAMP,
        "individual_document_and_amendment_recheck_required":True,
        "policy_or_supplier_hold":decision,
        "bid_authorized":False,"bid_eligible":False,"contact_authorized":False,
        "document_reviewed":False,"buyer_verified_for_empire_ai":False,
    }


def triage(*items):
    return {
        "status":"DEADLINES_TRIAGED_REVIEW_ONLY",
        "external_bids_authorized":False,"outbound_sent":False,"crm_writes":False,
        "bid_ready_count":0,"source_qualified_customer_count":0,
        "notice_count":len(items),"items":list(items),
        "original_feed_observed_at_utc":STAMP,
    }


def test_zero_bid_ready_does_not_mean_automatically_qualified():
    result=decide(triage(item()))
    assert result["status"]==STATUS_READY
    assert result["supplier_scope_hold_count"]==1
    assert result["bid_ready_count"]==0
    assert result["external_bids_submitted"]==0
    assert result["verified_empire_ai_customers"]==0
    assert result["payment_activation"] is False
    row=result["founder_review_items"][0]
    assert row["issuer_documents_checked"] is False
    assert row["binding_contract_value_gbp"] is None
    assert row["verified_profit_or_margin"] is None
    assert row["bid_submission_authorized"] is False
    assert "CONDITIONAL_PRIVACY_AUDIT" in row["specific_capability_question"]
    assert len(row["missing_evidence"])>=6


def test_policy_hold_and_closed_notice_become_not_biddable():
    paid=item(title="Digital Media Buying",ocid="ocds-paid",
              decision="HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE")
    closed=item(title="Closed audit",ocid="ocds-closed",
                urgency="CLOSED_AFTER_LAST_SOURCE_OBSERVATION")
    paid["official_notice_url"]="https://www.contractsfinder.service.gov.uk/Notice/d2301388-4ca6-48fc-805d-eb2e5793377e"
    closed["official_notice_url"]="https://www.contractsfinder.service.gov.uk/Notice/cab39ee0-c192-4fb2-9253-472214e58ca7"
    result=decide(triage(paid,closed))
    assert result["status"]==STATUS_READY
    assert result["policy_no_bid_or_scope_hold_count"]==1
    assert result["closed_no_bid_count"]==1
    assert all(x["bid_submission_authorized"] is False for x in result["founder_review_items"])


@pytest.mark.parametrize("mutation",["qualified","authorised","paid","unreviewed",
                                   "duplicate","missing","made_up_decision"])
def test_untrusted_or_escalated_notice_fails_closed(mutation):
    one=item()
    d=triage(one)
    if mutation=="qualified":d["source_qualified_customer_count"]=1
    elif mutation=="authorised":one["bid_authorized"]=True
    elif mutation=="paid":d["outbound_sent"]=True
    elif mutation=="unreviewed":one["individual_document_and_amendment_recheck_required"]=False
    elif mutation=="duplicate":d["items"].append(one.copy());d["notice_count"]=2
    elif mutation=="missing":one.pop("contact_authorized")
    else:one["policy_or_supplier_hold"]="BID_APPROVED"
    report=decide(d)
    assert report["status"]==STATUS_HELD
    assert report["bid_ready_count"]==0
    assert report["external_bids_submitted"]==0
    assert report["new_emails_sent"] is False
    assert report["realised_revenue"] is None


def test_hypothetical_economics_are_net_of_cash_costs_and_unapproved():
    result=hypothetical_margin({
        "proposed_net_price_gbp":"25000",
        "staff_hours":"150",
        "loaded_hourly_cost_gbp":"65",
        "subcontractor_cost_gbp":"3000",
        "software_and_data_cost_gbp":"500",
        "insurance_and_compliance_cost_gbp":"500",
        "travel_and_misc_cost_gbp":"250",
        "overhead_allocation_gbp":"500",
        "contingency_percentage":"10",
    })
    assert result["labour_cost_gbp"]=="9750.00"
    assert result["base_delivery_cost_gbp"]=="14500.00"
    assert result["contingency_cost_gbp"]=="1450.00"
    assert result["total_delivery_cost_gbp"]=="15950.00"
    assert result["contribution_gbp"]=="9050.00"
    assert result["contribution_margin_percent"]=="36.20"
    assert result["source_cost_evidence_verified"] is False
    assert result["bid_authorized"] is False
    assert result["revenue_verified"] is False


def test_negative_margin_and_invalid_costs():
    p={
        "proposed_net_price_gbp":"1000", "staff_hours":"40",
        "loaded_hourly_cost_gbp":"100", "subcontractor_cost_gbp":"0",
        "software_and_data_cost_gbp":"0", "insurance_and_compliance_cost_gbp":"0",
        "travel_and_misc_cost_gbp":"0", "overhead_allocation_gbp":"0",
        "contingency_percentage":"20",
    }
    assert hypothetical_margin(p)["profitable_in_this_hypothetical"] is False
    for bad in ("nan","Infinity","-1","abc"):
        altered=dict(p,proposed_net_price_gbp=bad)
        with pytest.raises(ValueError):
            hypothetical_margin(altered)
    with pytest.raises(ValueError):
        hypothetical_margin(dict(p,staff_hours=True))
    with pytest.raises(ValueError):
        hypothetical_margin(dict(p,unknown_cost=0))
    with pytest.raises(ValueError):
        hypothetical_margin(dict(p,contingency_percentage="101"))


def test_private_output_is_atomic_and_root_folder_protected(tmp_path):
    root=Path(tmp_path)
    folder=root/OUTPUT.parent
    folder.mkdir(parents=True)
    folder.chmod(0o700)
    valid=decide(triage(item()))
    destination=write_private(root,valid)
    assert destination==root/OUTPUT
    assert destination.stat().st_mode & 0o077==0
    assert json.loads(destination.read_text())["realised_revenue"] is None
    assert write_private(root,valid)==destination
    destination.unlink()
    marker=root/"outside"
    marker.write_text("untouched",encoding="utf-8")
    destination.symlink_to(marker)
    with pytest.raises(ValueError):
        write_private(root,valid)
    assert marker.read_text()=="untouched"
    with pytest.raises(ValueError):
        write_private(root,decide({}))


def test_source_absence_does_not_generate_unverified_bid(tmp_path):
    result=review_live(tmp_path,now=NOW)
    assert result["status"]==STATUS_HELD
    assert result["bid_ready_count"]==0



def test_original_ryde_source_overlay_preserves_discrepant_deadline_and_no_bid(tmp_path):
    import json
    from scripts.review_official_tender_bid_no_bid_20261024 import _join_original_ryde_issuer_proof
    from scripts.reconcile_ryde_original_issuer_documents_20261024 import (
        OCID, NOTICE, PAGE, SCHEMA, READY, OUTPUT, FILES,
    )
    row=item(ocid=OCID)
    row["official_notice_url"]=NOTICE
    row["tender_closes_at_utc"]="2026-10-26T12:00:00+00:00"
    original=decide(triage(row))
    source={
        "schema_version":SCHEMA,"status":READY,"ocid":OCID,
        "official_contracts_finder_notice":NOTICE,
        "issuer_transparency_page":PAGE,
        "source_review_verified_at_utc":NOW.isoformat(),
        "source_deadline_conflict":True,
        "buyer_closing_date_authoritatively_reconciled":False,
        "bid_authorized":False,"bid_eligibility_verified":False,
        "contact_authorized":False,"verified_contract_value_gbp":None,
        "verified_profit_margin":None,"issuer_document_count":4,
        "feed_closing_datetime":"2026-10-26T12:00:00+00:00",
        "quotation_deadline_from_issuer_document":"2026-11-02T12:00:00+00:00",
        "clarification_deadline_from_issuer_document":"2026-10-26",
        "published_requirements":["Original qualified specialist evidence "+str(i) for i in range(11)],
        "payment_terms_as_stated_percent":[20,20,30,30],
        "documents":[{"content_sha256":digest} for _name,_mime,digest in FILES.values()],
    }
    path=tmp_path/OUTPUT
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(source))
    path.chmod(0o600)
    result=_join_original_ryde_issuer_proof(tmp_path,original,now=NOW)
    assert result["original_issuer_documents_reconciled_count"]==1
    assert result["unresolved_issuer_deadline_conflict_count"]==1
    item_out=result["founder_review_items"][0]
    assert item_out["issuer_deadline_discrepancy"] is True
    assert item_out["tender_closes_at_utc"]=="2026-10-26T12:00:00+00:00"
    assert item_out["issuer_quotation_datetime_unconfirmed"]=="2026-11-02T12:00:00+00:00"
    assert item_out["bid_submission_authorized"] is False
    assert item_out["verified_profit_or_margin"] is None
    assert result["bid_ready_count"]==0
    assert result["supplier_eligible_count"]==0
    assert result["realised_revenue"] is None


def test_invalid_ryde_primary_source_overlay_never_promotes_any_bid(tmp_path):
    import json
    from scripts.review_official_tender_bid_no_bid_20261024 import _join_original_ryde_issuer_proof
    from scripts.reconcile_ryde_original_issuer_documents_20261024 import OCID,NOTICE,OUTPUT
    row=item(ocid=OCID)
    row["official_notice_url"]=NOTICE
    report=decide(triage(row))
    p=tmp_path/OUTPUT
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('{"status":"fabricated_customer_approved","bid_authorized":true}')
    p.chmod(0o600)
    result=_join_original_ryde_issuer_proof(tmp_path,report,now=NOW)
    assert result["founder_review_items"][0]["issuer_primary_source_reconciliation"]=="SOURCE_PROOF_NOT_CURRENT"
    assert result["founder_review_items"][0]["bid_submission_authorized"] is False
    assert result["bid_ready_count"]==0
    p.chmod(0o644)
    assert _join_original_ryde_issuer_proof(tmp_path,decide(triage(row)),now=NOW)["bid_ready_count"]==0
