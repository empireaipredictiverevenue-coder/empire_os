"""Read-only bid/no-bid decision desk for original EmpireOS official UK tenders.

Source of truth: the existing bounded official tender review, never a lead CRM.
No network requests, outbound sends, bid submission, terms, or payment mutation.
Costs are mathematical *internal hypothetical scenarios*, not actual bid prices.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping

from scripts.review_official_tender_founder_deadlines_20261024 import (
    READY_STATUS as DEADLINE_READY,
    review_existing_report,
)

DEFAULT_ROOT = Path("/srv/empire_os")
OUTPUT = Path("runtime/acquisition_research/official_tender_bid_no_bid_latest.json")
SCHEMA = "empire.official_tender_bid_no_bid.v1"
STATUS_READY = "RESEARCH_ONLY_BID_NO_BID_TRIAGED"
STATUS_HELD = "HELD_OFFICIAL_TENDER_RECEIPT_UNVERIFIED"
UNVERIFIED = "NOT_VERIFIED"
REQUIREMENTS = (
    "LATEST_ISSUER_DOCUMENTS_AND_AMENDMENTS",
    "EXACT_DELIVERABLE_SCOPE_AND_ACCEPTANCE",
    "SUPPLIER_LEGAL_ENTITY_AND_ELIGIBILITY",
    "VERIFIABLE_TEAM_CAPABILITY_AND_REFERENCES",
    "INSURANCE_PRIVACY_SECURITY_AND_CONFLICT_CHECKS",
    "SUBCONTRACT_AND_SOURCE_DATA_RIGHTS",
    "RESOURCE_AVAILABILITY_AND_DELIVERY_TIMELINE",
    "BUDGET_PAYMENT_TERMS_TAX_AND_COST_BASIS",
)
PROJECT_PAIN = {
    "GDPR Data Audit": "CONDITIONAL_PRIVACY_AUDIT_INDEPENDENCE_EXPERTISE_AND_INFORMATION_SECURITY_REVIEW",
    "CA18567 - RFQ 2026/43 - Development of a Dublin Belfast Economic Corridor Investment Land Guide": "CONDITIONAL_LAND_ECONOMICS_GIS_STAKEHOLDER_RESEARCH_AND_PUBLICATION_REVIEW",
}


def _amount(value: Any, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise ValueError("VALID_DECIMAL_AMOUNT_REQUIRED")
    try:
        item=Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("INVALID_SCENARIO_DECIMAL") from None
    if (not item.is_finite() or item > Decimal("1000000000") or
        (item <= 0 if positive else item < 0)):
        raise ValueError("OUT_OF_RANGE_SCENARIO_AMOUNT")
    return item


def hypothetical_margin(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic cash delivery economics, excl VAT/tax, never a quote.

    Requires all material cash/effort cost classes to be present explicitly.
    Intentional: no missing value silently defaults to zero.
    """
    names = {
        "proposed_net_price_gbp", "staff_hours", "loaded_hourly_cost_gbp",
        "subcontractor_cost_gbp", "software_and_data_cost_gbp",
        "insurance_and_compliance_cost_gbp", "travel_and_misc_cost_gbp",
        "overhead_allocation_gbp", "contingency_percentage",
    }
    if not isinstance(inputs, Mapping) or set(inputs) != names:
        raise ValueError("EXACT_HYPOTHETICAL_COST_COMPONENTS_REQUIRED")
    money = {k: _amount(v, positive=k in (
        "proposed_net_price_gbp","staff_hours","loaded_hourly_cost_gbp"
    )) for k, v in inputs.items()}
    cont = money["contingency_percentage"]
    if cont > 100:
        raise ValueError("UNREALISTIC_CONTINGENCY_RATE")
    labour = money["staff_hours"] * money["loaded_hourly_cost_gbp"]
    base = labour + sum(
        money[name] for name in (
            "subcontractor_cost_gbp","software_and_data_cost_gbp",
            "insurance_and_compliance_cost_gbp","travel_and_misc_cost_gbp",
            "overhead_allocation_gbp",
        )
    )
    contingency = base * cont / Decimal(100)
    total = base + contingency
    price = money["proposed_net_price_gbp"]
    gross = price - total
    margin = gross / price * 100
    fmt=lambda x: str(x.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
    return {
        "status": "HYPOTHETICAL_UNAPPROVED_SCENARIO_ONLY",
        "currency": "GBP",
        "vat_and_corporation_tax_accounted_for": False,
        "amount_basis": "EXCLUDES_VAT_AND_TAXES",
        "source_cost_evidence_verified": False,
        "price_approved": False,
        "bid_authorized": False,
        "revenue_verified": False,
        "labour_cost_gbp": fmt(labour),
        "base_delivery_cost_gbp": fmt(base),
        "contingency_cost_gbp": fmt(contingency),
        "total_delivery_cost_gbp": fmt(total),
        "contribution_gbp": fmt(gross),
        "contribution_margin_percent": fmt(margin),
        "profitable_in_this_hypothetical": gross > 0,
    }


def decide(triage: Mapping[str, Any]) -> dict[str, Any]:
    held={
        "schema_version": SCHEMA,
        "status": STATUS_HELD,
        "verified_empire_ai_customers": 0,
        "supplier_eligible_count": 0,
        "bid_ready_count": 0,
        "external_bids_submitted": 0,
        "new_emails_sent": False,
        "new_crm_writes": False,
        "payment_activation": False,
        "outbound_governor_activated": False,
        "automatic_bid_submission": False,
        "realised_revenue": None,
    }
    if (not isinstance(triage,Mapping)
        or triage.get("status") != DEADLINE_READY
        or triage.get("external_bids_authorized") is not False
        or triage.get("outbound_sent") is not False
        or triage.get("crm_writes") is not False
        or triage.get("bid_ready_count") != 0
        or triage.get("source_qualified_customer_count") != 0
        or not isinstance(triage.get("items"),list)
        or type(triage.get("notice_count")) is not int
        or triage["notice_count"] != len(triage["items"])):
        return held
    entries=[]
    seen=set()
    for notice in triage["items"]:
        if (not isinstance(notice, Mapping)
            or notice.get("bid_authorized") is not False
            or notice.get("bid_eligible") is not False
            or notice.get("contact_authorized") is not False
            or notice.get("document_reviewed") is not False
            or notice.get("buyer_verified_for_empire_ai") is not False
            or notice.get("individual_document_and_amendment_recheck_required") is not True):
            return held
        original = str(notice.get("official_notice_url") or "")
        if not original or original in seen:
            return held
        seen.add(original)
        urgency = notice.get("deadline_urgency")
        gate = notice.get("policy_or_supplier_hold")
        if urgency == "CLOSED_AFTER_LAST_SOURCE_OBSERVATION":
            outcome="NO_BID_DEADLINE_PASSED"
        elif gate == "HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE":
            outcome="NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER"
        elif gate == "HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT":
            outcome="HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE"
        else:
            return held
        fields={
            "official_notice_url": original,
            "buyer_organisation": notice.get("buyer_organisation"),
            "title": notice.get("title"),
            "ocid": notice.get("ocid"),
            "tender_closes_at_utc": notice.get("tender_closes_at_utc"),
            "deadline_urgency": urgency,
            "source_checked_at_utc": notice.get("deadline_last_confirmed_by_aggregated_feed_at_utc"),
            "decision": outcome,
            "missing_evidence": list(REQUIREMENTS),
            "specific_capability_question": PROJECT_PAIN.get(notice.get("title"),"REQUIRES_ORIGINAL_SCOPE_OWNER_REVIEW"),
            "supplier_eligibility": UNVERIFIED,
            "capability_and_references": UNVERIFIED,
            "issuer_documents_checked": False,
            "binding_contract_value_gbp": None,
            "proposed_net_price_gbp": None,
            "verified_delivery_cost_gbp": None,
            "verified_profit_or_margin": None,
            "cost_economics": "NOT_CALCULABLE_WITHOUT_SOURCE_DOCUMENTS_AND_REVIEWED_COSTS",
            "bid_no_bid_final_authority": False,
            "quote_approved": False,
            "bid_submission_authorized": False,
            "outreach_authorized": False,
            "payment_authorized": False,
        }
        entries.append(fields)
    entries.sort(key=lambda item: (item["tender_closes_at_utc"],item["ocid"]))
    return {
        **held,
        "status": STATUS_READY,
        "original_feed_observed_at_utc": triage.get("original_feed_observed_at_utc"),
        "notices_assessed": len(entries),
        "policy_no_bid_or_scope_hold_count": sum(x["decision"]=="NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER" for x in entries),
        "supplier_scope_hold_count": sum(x["decision"]=="HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE" for x in entries),
        "closed_no_bid_count": sum(x["decision"]=="NO_BID_DEADLINE_PASSED" for x in entries),
        "actual_bid_economics_verified_count": 0,
        "founder_review_items": entries,
    }


def _join_original_ryde_issuer_proof(root: Path, report: dict[str, Any],
                                    *, now: datetime) -> dict[str, Any]:
    """Trusted read-only source overlay; never changes the underlying bid hold."""
    if report.get("status") != STATUS_READY:
        return report
    from scripts.reconcile_ryde_original_issuer_documents_20261024 import (
        OUTPUT as SOURCE_FILE, SCHEMA as SOURCE_SCHEMA, READY as SOURCE_READY,
        OCID as RYDE_OCID, FILES as REVIEWED_FILES, PAGE as ISSUER_PAGE,
    )
    target = next((x for x in report["founder_review_items"]
                   if x["ocid"] == RYDE_OCID), None)
    if target is None:
        return report
    target["issuer_primary_source_reconciliation"] = "SOURCE_PROOF_NOT_CURRENT"
    path = root / SOURCE_FILE
    try:
        if (path.is_symlink() or path.parent.is_symlink()
            or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or path.stat().st_size > 30000):
            return report
        source = json.loads(path.read_text(encoding="utf-8"))
        reviewed = datetime.fromisoformat(source["source_review_verified_at_utc"])
        if (reviewed.tzinfo is None
            or not timedelta(0) <= now.astimezone(timezone.utc)-reviewed.astimezone(timezone.utc) <= timedelta(hours=24)
            or source.get("schema_version") != SOURCE_SCHEMA
            or source.get("status") != SOURCE_READY
            or source.get("ocid") != RYDE_OCID
            or target.get("official_notice_url") != source.get("official_contracts_finder_notice")
            or target.get("tender_closes_at_utc") != source.get("feed_closing_datetime")
            or source.get("issuer_transparency_page") != ISSUER_PAGE
            or source.get("source_deadline_conflict") is not True
            or source.get("buyer_closing_date_authoritatively_reconciled") is not False
            or source.get("bid_authorized") is not False
            or source.get("bid_eligibility_verified") is not False
            or source.get("contact_authorized") is not False
            or source.get("verified_contract_value_gbp") is not None
            or source.get("verified_profit_margin") is not None
            or source.get("issuer_document_count") != 4
            or not isinstance(source.get("documents"),list)
            or not isinstance(source.get("published_requirements"),list)
            or len(source["published_requirements"]) < 10
            or not all(isinstance(text,str) and 10 <= len(text) <= 300
                       for text in source["published_requirements"])
            or {x.get("content_sha256") for x in source["documents"]}
            != {entry[2] for entry in REVIEWED_FILES.values()}):
            return report
    except (OSError,ValueError,TypeError,KeyError,OverflowError):
        return report
    # The aggregation may still say 26 Oct; issuer PDF asks for quotes by
    # 2 Nov. This discrepancy is NEVER resolved by a single source.
    target.update({
        "issuer_primary_source_reconciliation": "VERIFIED_PUBLIC_ISSUER_DOCUMENTS_WITH_UNRESOLVED_DEADLINE_CONFLICT",
        "issuer_document_page": source["issuer_transparency_page"],
        "issuer_quotation_datetime_unconfirmed": source["quotation_deadline_from_issuer_document"],
        "issuer_clarification_date": source["clarification_deadline_from_issuer_document"],
        "aggregated_feed_deadline": source["feed_closing_datetime"],
        "issuer_deadline_discrepancy": True,
        "issuer_required_qualifications": list(source["published_requirements"]),
        "issuer_supplier_capability_evidence": "NOT_VERIFIED",
        "issuer_payment_terms_percent_unaccepted": list(source["payment_terms_as_stated_percent"]),
        "issuer_original_document_reviewed_at_utc": source["source_review_verified_at_utc"],
        "required_next_action": "REQUEST_OWNER_CONFIRMATION_OF_COMPETING_DEADLINES_AND_SUPPLIER_REQUIREMENTS",
        "cost_economics": "NOT_CALCULABLE_WITHOUT_CONFIRMED_SCOPE_AND_COSTS",
        "verified_profit_or_margin": None,
        "bid_submission_authorized": False,
        "quote_approved": False,
    })
    report["original_issuer_documents_reconciled_count"] = 1
    report["unresolved_issuer_deadline_conflict_count"] = 1
    return report


def review_live(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    existing=review_existing_report(root,now=current)
    return _join_original_ryde_issuer_proof(root,decide(existing),now=current)


def write_private(root: Path, report: Mapping[str, Any]) -> Path:
    if report.get("status")!=STATUS_READY:
        raise ValueError("NO_PRIVATE_WRITE_FOR_HELD_REPORT")
    root=Path(root).resolve(strict=True)
    target=root/OUTPUT
    folder=target.parent
    if (folder.is_symlink() or not folder.is_dir()
        or stat.S_IMODE(folder.stat().st_mode)!=0o700
        or target.is_symlink() or (target.exists() and (
          not target.is_file() or stat.S_IMODE(target.stat().st_mode)!=0o600))):
        raise ValueError("UNSAFE_PRIVATE_TENDER_RESEARCH_LOCATION")
    fd,temp=tempfile.mkstemp(prefix=".bid-nobid-",suffix=".json",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as file:
            os.fchmod(file.fileno(),0o600)
            json.dump(report,file,indent=2,sort_keys=True)
            file.write("\n")
            file.flush();os.fsync(file.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return target


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description="Original EmpireOS tender bid/no-bid research desk")
    parser.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    try:
        result=review_live(Path(args.repo_root))
        saved=False
        if result["status"]==STATUS_READY and args.write_private:
            write_private(Path(args.repo_root),result)
            saved=True
    except (ValueError,OSError):
        result=decide({})
        saved=False
    summary={key:value for key,value in result.items() if key!="founder_review_items"}
    summary["private_workbench_written"]=saved
    print(json.dumps(summary,sort_keys=True))
    return 0 if result["status"]==STATUS_READY else 2


if __name__=="__main__":
    raise SystemExit(main())
