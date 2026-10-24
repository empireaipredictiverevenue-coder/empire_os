"""CA18567 original EmpireOS tender commercial readiness review.

Reads original private authenticated-outbound *send receipts* and original
supplier-document custody inventory only. Never mistakes dispatch for delivery,
RFQ staging for document authenticity, or research for specialist qualifications.
No database, outbound, portal login, submission, LLM, external service or funds.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from empire_os.tender_supplier_evidence_intake import inventory, OBSERVED

SCHEMA = "empire.tender_ca18567_commercial_readiness.v1"
BASE = Path("runtime/acquisition_research")
INCOMING = BASE / "ca18567_approved_outreach_receipt_20261024.json"
OUTPUT = BASE / "ca18567_commercial_readiness_latest.json"
FOUNDER_DEADLINE_TZ = ZoneInfo("Europe/London")
QUESTIONS_AT = datetime(2026,10,26,12,0,tzinfo=FOUNDER_DEADLINE_TZ)
BIDS_AT = datetime(2026,10,30,12,0,tzinfo=FOUNDER_DEADLINE_TZ)
SOURCE_OFFICIAL = "https://www.sell2wales.gov.wales/search/show/search_view.aspx?ID=OCT667975&catID="
SOURCE_PORTAL = "https://suppliers.multiquote.com/Unauthenticated/BrowseOpportunities.aspx"

# Hard-anchored to actually sent Gmail provider IDs, not unverified drafts.
EXPECTED_SENDS = {
    "info@multiquote.com": ("1a16e945dd6292bc", "1a16e2db82c6bb5a", "procurement_access"),
    "planning@mdb.ie": ("1a16e9464a7b3cfb", "1a16e2ee272c9320", "planning_land_research"),
    "angela.wiggam@turley.co.uk": ("1a16e946afa816b8", "1a16e32d8504c618", "northern_ireland_planning"),
    "info@perspectiveeconomics.com": ("1a16e94737a555ab", "1a16e2eeee251f62", "economic_methodology"),
    "mail@centroidsystems.com": ("1a16e94798c4f951", "1a16e7d81ebcd9f4", "gis_and_mapping"),
}

def _safe_private_directory(root: Path) -> Path:
    base=root.resolve(strict=True) / BASE
    st=base.lstat()
    if (base.is_symlink() or not stat.S_ISDIR(st.st_mode)
        or stat.S_IMODE(st.st_mode)!=0o700 or st.st_uid!=os.geteuid()):
        raise ValueError("PRIVATE_EMPIREOS_TENDER_DIRECTORY_REQUIRED")
    return base

def _read_receipt(root: Path) -> dict[str, Any] | None:
    p=_safe_private_directory(root) / INCOMING.name
    try:
        st=p.lstat()
        if (p.is_symlink() or not stat.S_ISREG(st.st_mode)
            or stat.S_IMODE(st.st_mode)!=0o600 or st.st_uid!=os.geteuid()
            or not 100 <= st.st_size <= 12000):
            return None
        with p.open("rb") as f:
            fst=os.fstat(f.fileno())
            if (fst.st_ino!=st.st_ino or fst.st_dev!=st.st_dev
                or fst.st_size!=st.st_size or fst.st_nlink!=1):
                return None
            report=json.load(f)
        return report if isinstance(report,dict) else None
    except (OSError, ValueError, TypeError, UnicodeError):
        return None

def _valid_sent_receipt(report: Any) -> bool:
    if (not isinstance(report, Mapping)
        or report.get("schema_version")!="empire.tender_ca18567_approved_outreach_receipt.v1"
        or report.get("reference")!="CA18567"
        or report.get("source")!="Gmail connected business mailbox send_draft responses"
        or report.get("state")!="PROVIDER_SENT_CONFIRMED_NOT_DELIVERY_CONFIRMED"
        or report.get("sent_count")!=5
        or report.get("delivery_confirmed_count")!=0
        or report.get("replies_verified_count")!=0
        or report.get("supplier_quotes_verified_count")!=0
        or report.get("supplier_contracts_verified_count")!=0
        or report.get("rfq_obtained") is not False
        or report.get("bid_submitted") is not False
        or report.get("crm_writes") is not False
        or report.get("payment_actions") is not False):
        return False
    rows=report.get("messages")
    if not isinstance(rows,list) or len(rows)!=5:
        return False
    found=set()
    for row in rows:
        if not isinstance(row,Mapping):
            return False
        recipient=row.get("recipient")
        if not isinstance(recipient,str) or recipient not in EXPECTED_SENDS or recipient in found:
            return False
        msg,thread,_=EXPECTED_SENDS[recipient]
        if row.get("message_id")!=msg or row.get("thread_id")!=thread or row.get("provider_label")!="SENT":
            return False
        found.add(recipient)
    return found==set(EXPECTED_SENDS)

def _money(value:Decimal) -> str:
    return format(value.quantize(Decimal("0.01")),"f")

def _hypothetical_economics() -> dict[str,Any]:
    # These are ONLY our illustrative planning scenarios, NEVER supplier quotes.
    bid=Decimal("24500")
    lean=Decimal("20104")
    full=Decimal("32487.50")
    return {
        "source_status":"INTERNAL_UNQUOTED_SCENARIOS_NOT_SUPPLIER_COSTS",
        "illustrative_bid_ex_vat_gbp":_money(bid),
        "buyer_advertised_estimate_gbp":"25000.00",
        "buyer_estimate_is_our_bid":False,
        "hypothetical_lean_all_in_cost_gbp":_money(lean),
        "hypothetical_full_specialist_cost_gbp":_money(full),
        "hypothetical_lean_contribution_gbp":_money(bid-lean),
        "hypothetical_lean_contribution_margin_pct":_money((bid-lean)*Decimal("100")/bid),
        "hypothetical_full_contribution_gbp":_money(bid-full),
        "hypothetical_full_contribution_margin_pct":_money((bid-full)*Decimal("100")/bid),
        "max_all_in_cost_at_20pct_contribution_gbp":_money(bid*Decimal("0.80")),
        "max_all_in_cost_at_25pct_contribution_gbp":_money(bid*Decimal("0.75")),
        "actual_supplier_quote_count":0,
        "actual_verified_delivery_cost_gbp":None,
        "actual_bid_price_approved_gbp":None,
        "verified_margin_gbp":None,
        "revenue_gbp":None,
        "note":"20pct/25pct are illustrative sensitivity scenarios, not preexisting formal minimum-margin policy.",
    }

def assess(root:Path, *, now:datetime|None=None) -> dict[str,Any]:
    at=now or datetime.now(timezone.utc)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    original=_read_receipt(root)
    good=_valid_sent_receipt(original)
    supplier_docs=inventory(root,now=at)
    # Public status depends on independent portal/issuer access; local document
    # presence alone can never promote full RFQ, supplier capability or readiness.
    rows=[
        {
            "recipient":address, "purpose":spec[2],
            "dispatch_status":"GMAIL_PROVIDER_SENT" if good else "SENT_EVIDENCE_NOT_VALIDATED",
            "message_id":spec[0] if good else None,
            "thread_id":spec[1] if good else None,
            "recipient_delivery_verified_at_original_receipt":False,
            "current_delivery_and_reply_status":"UNKNOWN_REQUIRES_FRESH_GMAIL_CHECK",
            "named_specialist_verified":False,
            "confirmed_capacity":False,
            "real_quotation_verified":False,
            "human_partner_approval":False,
        }
        for address,spec in EXPECTED_SENDS.items()
    ]
    now_local=at.astimezone(FOUNDER_DEADLINE_TZ)
    questions_left=max(0,int((QUESTIONS_AT-at).total_seconds()))
    bids_left=max(0,int((BIDS_AT-at).total_seconds()))
    report={
        "schema_version":SCHEMA,
        "tender_ref":"CA18567",
        "observed_at_utc":at.astimezone(timezone.utc).isoformat(),
        "status":"NOT_BID_READY_AUTHENTIC_RFQ_AND_PARTNER_CAPACITY_MISSING" if good else "HELD_INVALID_OR_MISSING_SENT_RECEIPT",
        "now_uk":now_local.isoformat(),
        "official_source":SOURCE_OFFICIAL,
        "public_portal":SOURCE_PORTAL,
        "questions_deadline_uk":QUESTIONS_AT.isoformat(),
        "submission_deadline_uk":BIDS_AT.isoformat(),
        "questions_window_open":questions_left>0,
        "submission_window_open":bids_left>0,
        "seconds_until_clarification_deadline":questions_left,
        "seconds_until_submission_deadline":bids_left,
        "public_portal_row_observed_as_of_date":"2026-10-24",
        "public_portal_row_live_rechecked_by_this_module":False,
        "public_portal_row_documents_accessible_as_of_2026_10_24":False,
        "outreach_provider_receipt_valid":good,
        "approved_emails_sent_provider_count":5 if good else 0,
        "confirmed_deliveries_on_original_send_receipt":0,
        "genuine_inbound_partner_replies_at_receipt_creation":0,
        "current_inbound_replies_live_checked_by_module":False,
        "current_partner_reply_count":None,
        "current_delivery_and_bounce_status":"UNKNOWN_REQUIRES_FRESH_GMAIL_CHECK",
        "suppression_check_new_results":"UNVERIFIED_REQUIRES_LIVE_EMAIL_CHECK",
        "suppliers_with_verified_qualifications":0,
        "genuine_supplier_quotes":0,
        "supplier_document_inventory_status":supplier_docs["status"],
        "supplier_document_count":supplier_docs["document_count"],
        "authenticated_complete_rfq_verified":False,
        "scored_quality_subcriteria_verified":False,
        "buyer_subcontract_or_consortium_permission_verified":False,
        "professional_signoff_obtained":False,
        "required_insurance_and_suitability_verified":False,
        "priced_delivery_approved":False,
        "bid_submission_authorised":False,
        "bid_submitted":False,
        "crm_writes":False,
        "empiredb_writes":False,
        "outbound_sent_by_this_module":False,
        "new_portal_actions":False,
        "payments":False,
        "realised_revenue_gbp":None,
        "dispatches":rows,
        "illustrative_economics":_hypothetical_economics(),
        "decision":"NO_BID_DEFAULT_UNTIL_ALL_GATES_INDEPENDENTLY_SATISFIED",
        "founder_final_bid_no_bid_recorded":False,
        "urgent_next_actions":[
            {
                "owner":"PROCUREMENT_OWNER",
                "priority":1,
                "by":"2026-10-26T12:00:00+00:00",
                "action":"Gain lawful MultiQuote supplier RFQ access and use official clarification channel if needed; confirm dates and registration eligibility",
                "evidence":"Actual authenticated specification, detailed quality criteria, contract terms and portal timestamp",
                "status":"NOT_VERIFIED",
            },
            {
                "owner":"DELIVERY_SPECIALIST_OWNER",
                "priority":2,
                "by":"BEFORE_INTERNAL_BID_GATE",
                "action":"Receive actual written reply and named qualified land/planning/economic/GIS specialist capacity, permissions, independently checked references and insurance",
                "evidence":"Specific genuine replies, documents and consent to named bid inclusion",
                "status":"NOT_VERIFIED",
            },
            {
                "owner":"FINANCE_OWNER",
                "priority":3,
                "by":"BEFORE_INTERNAL_BID_GATE",
                "action":"Obtain written priced work packages, VAT/tax treatment, contingencies, deliverables and founder-approved actual margin",
                "evidence":"Genuine source-backed signed or attributable quotes, not hypothetical day rates",
                "status":"NOT_VERIFIED",
            },
            {
                "owner":"FOUNDER",
                "priority":4,
                "by":"2026-10-30T12:00:00+00:00",
                "action":"Review the full truthful final bid/no-bid and any binding terms before any application or submission",
                "evidence":"Express final authority after professional, legal and economic review",
                "status":"NOT_VERIFIED",
            },
        ],
    }
    if bids_left==0:
        report["status"]="SUBMISSION_DEADLINE_PASSED_NO_BID_AUTHORITY"
    elif questions_left==0:
        report["status"]="CLARIFICATION_WINDOW_CLOSED_BID_STILL_NOT_READY"
    return report

def save_private(root:Path,report:Mapping[str,Any])->Path:
    directory=_safe_private_directory(root)
    out=directory/OUTPUT.name
    if out.is_symlink() or (out.exists() and (
        not out.is_file() or out.stat().st_uid!=os.geteuid()
        or stat.S_IMODE(out.stat().st_mode)!=0o600)):
        raise ValueError("UNSAFE_PRIVATE_READINESS_REPORT")
    fd,tmp=tempfile.mkstemp(prefix=".tender-ca18567-commercial-",suffix=".json",dir=directory)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(dict(report),f,sort_keys=True,indent=2,allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,out)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return out
