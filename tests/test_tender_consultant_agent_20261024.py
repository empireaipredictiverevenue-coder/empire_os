"""EmpireOS consultant agent: grounded analysis, no delegated bid authority."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest

from empire_os import tender_consultant_agent as module

NOW=datetime(2026,10,24,13,15,tzinfo=timezone.utc)
RYDE=[
    "Named auditor(s) with recognised data-protection qualification",
    "Evidence of comparable public-sector data audits",
    "Independence and conflict-of-interest declaration",
    "ICO registration",
    "Professional indemnity insurance GBP 5000000",
    "Public liability insurance GBP 5000000",
    "Two references",
    "Some on-site work in Ryde",
    "Audit GDPR and DPIAs",
    "Present to council",
    "Supplier accounts and safety checks",
]


def source():
    def row(ocid,title,url):
        return {
            "ocid":ocid,"title":title,"official_notice_url":url,
            "decision":"HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE",
            "bid_submission_authorized":False,
            "bid_no_bid_final_authority":False,
            "outreach_authorized":False,
            "quote_approved":False,
            "supplier_eligibility":"NOT_VERIFIED",
            "verified_profit_or_margin":None,
            "binding_contract_value_gbp":None,
            "missing_evidence":[f"GAP_{i}" for i in range(8)],
        }
    r=row(module.RYDE_OCID,module.EXPECTED[module.RYDE_OCID],module.RYDE_URL)
    r.update({
        "issuer_primary_source_reconciliation":
            "VERIFIED_PUBLIC_ISSUER_DOCUMENTS_WITH_UNRESOLVED_DEADLINE_CONFLICT",
        "issuer_deadline_discrepancy":True,
        "tender_closes_at_utc":"2026-10-26T12:00:00+00:00",
        "issuer_quotation_datetime_unconfirmed":"2026-11-02T12:00:00+00:00",
        "issuer_required_qualifications":list(RYDE),
        "issuer_supplier_capability_evidence":"NOT_VERIFIED",
    })
    l=row(module.LAND_OCID,module.EXPECTED[module.LAND_OCID],module.LAND_URL)
    l.update({
        "second_government_notice_reconciliation":
            "PUBLISHED_AWARD_WEIGHTS_CORROBORATED_SUPPLIER_RFQ_STILL_HELD",
        "published_estimated_value_gbp":"25000.00",
        "estimated_value_receipt_status":"OFFICIAL_OCDS_ADVERT_ESTIMATE_NOT_A_QUOTE",
        "published_quality_weight_percent":80,
        "published_price_weight_percent":20,
        "public_page_displays_different_deadline":True,
        "full_supplier_rfq_documents_reviewed":False,
        "tender_closes_at_utc":"2026-10-30T12:00:00+00:00",
    })
    paid=[]
    for i in range(4):
        paid.append({
            "ocid":f"fake-hold-{i}",
            "decision":"NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER",
            "bid_submission_authorized":False,"outreach_authorized":False,
            "quote_approved":False,
        })
    return {
        "status":"RESEARCH_ONLY_BID_NO_BID_TRIAGED",
        "original_feed_observed_at_utc":(NOW-timedelta(minutes=15)).isoformat(),
        "bid_ready_count":0,"supplier_eligible_count":0,
        "actual_bid_economics_verified_count":0,"external_bids_submitted":0,
        "new_emails_sent":False,"new_crm_writes":False,
        "payment_activation":False,"outbound_governor_activated":False,
        "automatic_bid_submission":False,"realised_revenue":None,
        "notices_assessed":6,"supplier_scope_hold_count":2,
        "policy_no_bid_or_scope_hold_count":4,
        "founder_review_items":[r,l,*paid],
    }


def test_real_specialist_route_and_two_consultant_dossiers():
    packet=module.consult(source(),now=NOW)
    assert packet["status"]==module.READY
    assert packet["agent_key"]=="tender_consultant"
    assert packet["reports_to"]=="CHIEF_OF_STAFF_FOUNDER_REVIEW"
    assert packet["execution_authority"]=="none"
    assert packet["source_notice_count"]==6
    assert packet["review_only_public_notice_count"]==2
    assert packet["blocked_paid_traffic_or_undefined_scope_count"]==4
    assert len(packet["briefs"])==2
    a,b=packet["briefs"]
    assert a["ocid"]==module.RYDE_OCID
    assert a["consultant_recommendation"].startswith("NO_BID")
    assert len(a["qualification_requirements"])==11
    assert all(x["supplier_proof"]=="NOT_VERIFIED" for x in a["qualification_requirements"])
    assert a["advertised_contract_estimate_gbp"] is None
    assert a["deadline_status"]=="CONFLICT_ISSUER_CONFIRMATION_REQUIRED"
    assert b["ocid"]==module.LAND_OCID
    assert b["published_estimate_gbp"]=="25000.00"
    assert b["evaluation_quality_percent"]==80
    assert b["evaluation_price_percent"]==20
    assert b["full_rfq_scoring_questions"]=="NOT_VERIFIED"
    assert b["multi_quote_portal_deadline_reconciled"] is False
    assert b["internal_economic_readiness"].startswith("NOT_CALCULABLE")
    assert len(b["consultant_owner_tasks"])>=5
    assert all(task["status"]=="NOT_VERIFIED" for dossier in packet["briefs"] for task in dossier["consultant_owner_tasks"])
    assert all(not task["external_action_authorized"] for dossier in packet["briefs"] for task in dossier["consultant_owner_tasks"])
    assert packet["bid_submissions"]==0
    assert packet["outbound_sent"] is False
    assert packet["customer_contracts"]==0
    assert packet["verified_revenue"] is None
    assert packet["crm_writes"] is False
    assert packet["ai_is_qualified_professional"] is False


@pytest.mark.parametrize("mutation",[
    "stale","future","missing_second_source","fake_supplier","fake_quote",
    "source_qualified","missing_ryde","changed_land_estimate","weight_tamper",
    "fake_ryde_deadline","no_qualifications","fake_full_rfq",
    "source_send","bad_revenue","wrong_count","duplicate_ids",
])
def test_inconsistent_or_stale_source_never_creates_consultant_signoff(mutation):
    p=deepcopy(source())
    rows=p["founder_review_items"]
    r,l=rows[:2]
    if mutation=="stale":p["original_feed_observed_at_utc"]=(NOW-timedelta(days=2)).isoformat()
    elif mutation=="future":p["original_feed_observed_at_utc"]=(NOW+timedelta(minutes=2)).isoformat()
    elif mutation=="missing_second_source":l["second_government_notice_reconciliation"]="SOURCE_PROOF_NOT_CURRENT"
    elif mutation=="fake_supplier":r["supplier_eligibility"]="VERIFIED"
    elif mutation=="fake_quote":l["quote_approved"]=True
    elif mutation=="source_qualified":p["bid_ready_count"]=1
    elif mutation=="missing_ryde":rows.pop(0)
    elif mutation=="changed_land_estimate":l["published_estimated_value_gbp"]="50000.00"
    elif mutation=="weight_tamper":l["published_quality_weight_percent"]=90
    elif mutation=="fake_ryde_deadline":r["issuer_deadline_discrepancy"]=False
    elif mutation=="no_qualifications":r["issuer_required_qualifications"]=[]
    elif mutation=="fake_full_rfq":l["full_supplier_rfq_documents_reviewed"]=True
    elif mutation=="source_send":p["new_emails_sent"]=True
    elif mutation=="bad_revenue":p["realised_revenue"]=100
    elif mutation=="wrong_count":p["notices_assessed"]=7
    elif mutation=="duplicate_ids":rows[2]["ocid"]=r["ocid"]
    report=module.consult(p,now=NOW)
    assert report["status"]==module.HELD
    assert report["bid_ready_count"]==0
    assert report["bid_submissions"]==0
    assert report["verified_revenue"] is None
    assert report["outbound_sent"] is False
    assert "briefs" not in report


def test_real_original_source_requires_protected_file(tmp_path):
    s=source()
    p=tmp_path/module.INPUT
    p.parent.mkdir(parents=True)
    p.parent.chmod(0o700)
    p.write_text(json.dumps(s))
    p.chmod(0o600)
    ready=module.review(tmp_path,now=NOW)
    assert ready["status"]==module.READY
    dest=module.save_private(tmp_path,ready)
    assert dest==tmp_path/module.OUTPUT
    assert dest.stat().st_mode&0o077==0
    assert json.loads(dest.read_text())["bid_ready_count"]==0
    assert module.save_private(tmp_path,ready)==dest
    dest.unlink()
    outside=tmp_path/"outside"
    outside.write_text("DO_NOT_TOUCH")
    dest.symlink_to(outside)
    with pytest.raises(ValueError):
        module.save_private(tmp_path,ready)
    assert outside.read_text()=="DO_NOT_TOUCH"
    p.chmod(0o644)
    assert module.review(tmp_path,now=NOW)["status"]==module.HELD
    p.chmod(0o600)
    p.unlink()
    assert module.review(tmp_path,now=NOW)["status"]==module.HELD


def test_consultant_no_assumed_scheduler_or_external_action():
    report=module.consult(source(),now=NOW)
    assert report["run_mode"]=="ON_DEMAND_OBSERVE_ONLY"
    assert report["automatic_bid_enabled"] is False
    assert report["portal_logins"]==0
    assert report["outbound_governor_enabled"] is False
    assert report["approved_quotes"]==0


def test_naive_now_clock_denied():
    result=module.consult(source(),now=datetime(2026,10,24,13))
    assert result["status"]==module.HELD



def test_shadow_local_model_only_proposes_unverified_questions():
    packet=module.consult(source(),now=NOW)
    calls=[]
    def mock_call(request):
        calls.append(request)
        return {"choices":[{"message":{"content":
            "Q1: Has the land consultancy supplied relevant corridor development references?\n"
            "Q2: Who will validate the land GIS rights and investor guide deliverables?\n"
            "Q3: Can a named independent auditor prove data protection credentials?\n"
            "Q4: Are the insurance certificates and Ryde site visits independently verified?"
        }}]}
    shadow=module.local_shadow_advice(packet,call=mock_call)
    assert shadow["status"]=="LOCAL_SHADOW_QUESTIONS_UNVERIFIED_FOR_HUMAN_REVIEW"
    assert len(shadow["questions"])==4
    assert shadow["source_evidence_upgraded"] is False
    assert shadow["qualified_supplier_inferred"] is False
    assert shadow["bid_allowed"] is False
    assert calls[0]["model"]=="qwen2.5-coder:1.5b"
    assert calls[0]["stream"] is False
    assert packet["bid_ready_count"]==0
    assert "local_shadow_questions" not in packet


def test_shadow_malicious_or_offline_response_remains_held():
    packet=module.consult(source(),now=NOW)
    for text in (
        "Q1: Submit a bid now?\nQ2: What is the price?",
        "Q1: Contact the buyer by email?\nQ2: Did you win?\n"
        "Q3: What are credentials?\nQ4: What is capacity?",
        "The bid is approved and you have insurance.",
    ):
        result=module.local_shadow_advice(
            packet,call=lambda _:{"choices":[{"message":{"content":text}}]},
        )
        assert result["status"]=="SHADOW_ADVICE_HELD_NO_NEW_CLAIMS"
        assert result["questions"]==[]
        assert result["bid_allowed"] is False
    offline=module.local_shadow_advice(
        packet,call=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert offline["status"]=="SHADOW_ADVICE_HELD_NO_NEW_CLAIMS"
    assert module.local_shadow_advice({},call=lambda _:None)["status"]=="SHADOW_ADVICE_HELD_NO_NEW_CLAIMS"


def test_consultant_reports_rfq_drop_without_promoting_issuer_or_seller(tmp_path):
    import os
    from empire_os import tender_supplier_evidence_intake as intake
    packet=source()
    private=tmp_path/module.INPUT
    private.parent.mkdir(parents=True)
    private.parent.chmod(0o700)
    private.write_text(json.dumps(packet))
    private.chmod(0o600)
    intake.ensure_private_drop(tmp_path)
    no_files=module.review(tmp_path,now=NOW)
    assert no_files["status"]==module.READY
    assert no_files["ca18567_supplier_document_intake"]["status"]==intake.AWAIT
    doc=tmp_path/intake.DROP/"CA18567_RFQ.pdf"
    doc.write_bytes(b"%PDF-1.7\n"+b"a"*1100+b"\n%%EOF")
    doc.chmod(0o600)
    os.utime(doc,(NOW.timestamp()-10,NOW.timestamp()-10))
    seen=module.review(tmp_path,now=NOW)
    assert seen["status"]==module.READY
    assert seen["ca18567_supplier_document_intake"]["status"]==intake.OBSERVED
    assert seen["ca18567_supplier_document_intake"]["documents_observed"]==1
    assert seen["ca18567_supplier_document_intake"]["provenance_status"]=="NOT_AUTHENTICATED_BY_ISSUER"
    assert seen["ca18567_supplier_document_intake"]["full_rfq_reviewed"] is False
    assert seen["ca18567_supplier_document_intake"]["bid_authorized"] is False
    assert seen["bid_ready_count"]==0
    assert seen["verified_revenue"] is None
