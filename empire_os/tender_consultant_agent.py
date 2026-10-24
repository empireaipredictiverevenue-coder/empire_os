"""EmpireOS Tender Consultant Agent — private, evidence-led bid advisor.

Original existing official tender intake -> bid/no-bid receipt -> controlled
consultant assignment. This agent does analysis and drafts an internal plan;
it is NOT a qualified human specialist, supplier of record or autonomous bidder.

Authority: observe only. No HTTP, DB, email, supplier login, model calls,
bid submission, customer-facing output or revenue events in this module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import stat
import tempfile
from typing import Any, Mapping

from empire_os.agent_execution_plane import ExecutionJob, route_execution_job

INPUT = Path("runtime/acquisition_research/official_tender_bid_no_bid_latest.json")
OUTPUT = Path("runtime/acquisition_research/tender_consultant_founder_brief_latest.json")
SCHEMA = "empire.tender_consultant_founder_brief.v1"
READY = "CONSULTANT_BRIEF_PREPARED_REVIEW_ONLY"
HELD = "HELD_TENDER_CONSULTANT_SOURCE_OR_AUTHORITY"
LAND_OCID = "ocds-b5fd17-4321ebe7-2ddb-47fa-81f9-fa095553b41b"
RYDE_OCID = "ocds-b5fd17-4f1d763a-8ba8-4b2c-9b97-6ea1e7ab3a42"
LAND_URL = "https://www.contractsfinder.service.gov.uk/Notice/cab39ee0-c192-4fb2-9253-472214e58ca7"
RYDE_URL = "https://www.contractsfinder.service.gov.uk/Notice/5f4d9841-b30a-42bb-b122-3f7758606443"
LAND_PUBLIC = "https://www.sell2wales.gov.wales/search/show/search_view.aspx?ID=OCT667975&catID="
RYDE_PUBLIC = "https://rydetowncouncil.gov.uk/transparency/"
EXPECTED = {
    RYDE_OCID: "GDPR Data Audit",
    LAND_OCID: "CA18567 - RFQ 2026/43 - Development of a Dublin Belfast Economic Corridor Investment Land Guide",
}
UNVERIFIED = "NOT_VERIFIED"


def _base(status: str = HELD) -> dict[str, Any]:
    return {
        "schema_version":SCHEMA,
        "status":status,
        "agent_key":"tender_consultant",
        "department":"commercial_procurement",
        "reports_to":"CHIEF_OF_STAFF_FOUNDER_REVIEW",
        "run_mode":"ON_DEMAND_OBSERVE_ONLY",
        "execution_authority":"none",
        "bid_ready_count":0,
        "qualified_suppliers":0,
        "approved_quotes":0,
        "customer_contracts":0,
        "verified_revenue":None,
        "outbound_sent":False,
        "bid_submissions":0,
        "portal_logins":0,
        "crm_writes":False,
        "payment_actions":False,
        "outbound_governor_enabled":False,
        "automatic_bid_enabled":False,
        "ai_is_qualified_professional":False,
    }


def _check_row(row: Mapping[str, Any], *, ocid: str, title: str, url: str) -> bool:
    return (
        row.get("ocid")==ocid and row.get("title")==title
        and row.get("official_notice_url")==url
        and row.get("decision")=="HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE"
        and row.get("bid_submission_authorized") is False
        and row.get("bid_no_bid_final_authority") is False
        and row.get("outreach_authorized") is False
        and row.get("quote_approved") is False
        and row.get("supplier_eligibility")==UNVERIFIED
        and row.get("verified_profit_or_margin") is None
        and row.get("binding_contract_value_gbp") is None
        and isinstance(row.get("missing_evidence"),list)
        and len(row["missing_evidence"])>=7
    )


def consult(receipt: Any, *, now: datetime) -> dict[str, Any]:
    """Produce two actionable, source-qualified consultancy briefs or HOLD."""
    held=_base()
    if now.tzinfo is None or now.utcoffset() is None:
        return held
    try:
        if (not isinstance(receipt,Mapping)
            or receipt.get("status")!="RESEARCH_ONLY_BID_NO_BID_TRIAGED"
            or receipt.get("bid_ready_count")!=0
            or receipt.get("supplier_eligible_count")!=0
            or receipt.get("actual_bid_economics_verified_count")!=0
            or receipt.get("external_bids_submitted")!=0
            or receipt.get("new_emails_sent") is not False
            or receipt.get("new_crm_writes") is not False
            or receipt.get("payment_activation") is not False
            or receipt.get("outbound_governor_activated") is not False
            or receipt.get("automatic_bid_submission") is not False
            or receipt.get("realised_revenue") is not None
            or receipt.get("notices_assessed")!=6
            or receipt.get("supplier_scope_hold_count")!=2
            or receipt.get("policy_no_bid_or_scope_hold_count")!=4):
            return held
        observed=datetime.fromisoformat(receipt["original_feed_observed_at_utc"])
        if (observed.tzinfo is None or
            not timedelta(0) <= now.astimezone(timezone.utc)-observed.astimezone(timezone.utc)
            <= timedelta(hours=24)):
            return held
        entries=receipt["founder_review_items"]
        if not isinstance(entries,list) or len(entries)!=6:
            return held
        lookup={}
        for item in entries:
            if not isinstance(item,Mapping) or not isinstance(item.get("ocid"),str):
                return held
            if item["ocid"] in lookup:
                return held
            lookup[item["ocid"]]=item
        if not set(EXPECTED).issubset(lookup):
            return held
        if any(
            e.get("bid_submission_authorized") is not False
            or e.get("outreach_authorized") is not False
            or e.get("quote_approved") is not False
            for e in entries
        ):
            return held
        route=route_execution_job(ExecutionJob(
            job_id="existing-uk-public-tenders-consultant",
            capability="tender_bid_consultation",
            department="commercial_procurement",
            authority="observe",
            risk_class="medium",
            source_ref="original-private-official-tender-receipt",
        ))
        if not route.eligible or route.worker_key!="tender_consultant" or route.execution_authority!="none":
            return held
        ryde=lookup[RYDE_OCID]
        land=lookup[LAND_OCID]
        if not _check_row(ryde,ocid=RYDE_OCID,title=EXPECTED[RYDE_OCID],url=RYDE_URL):
            return held
        if not _check_row(land,ocid=LAND_OCID,title=EXPECTED[LAND_OCID],url=LAND_URL):
            return held
        if (
            ryde.get("issuer_primary_source_reconciliation")
            !="VERIFIED_PUBLIC_ISSUER_DOCUMENTS_WITH_UNRESOLVED_DEADLINE_CONFLICT"
            or ryde.get("issuer_deadline_discrepancy") is not True
            or ryde.get("tender_closes_at_utc")!="2026-10-26T12:00:00+00:00"
            or ryde.get("issuer_quotation_datetime_unconfirmed")!="2026-11-02T12:00:00+00:00"
            or not isinstance(ryde.get("issuer_required_qualifications"),list)
            or len(ryde["issuer_required_qualifications"])<10
            or ryde.get("issuer_supplier_capability_evidence")!=UNVERIFIED
            or land.get("second_government_notice_reconciliation")
            !="PUBLISHED_AWARD_WEIGHTS_CORROBORATED_SUPPLIER_RFQ_STILL_HELD"
            or land.get("published_estimated_value_gbp")!="25000.00"
            or land.get("estimated_value_receipt_status")
            !="OFFICIAL_OCDS_ADVERT_ESTIMATE_NOT_A_QUOTE"
            or land.get("published_quality_weight_percent")!=80
            or land.get("published_price_weight_percent")!=20
            or land.get("public_page_displays_different_deadline") is not True
            or land.get("full_supplier_rfq_documents_reviewed") is not False
            or land.get("tender_closes_at_utc")!="2026-10-30T12:00:00+00:00"
        ):
            return held
        return {
            **held,
            "status":READY,
            "generated_at_utc":now.astimezone(timezone.utc).isoformat(),
            "original_release_observed_at_utc":observed.isoformat(),
            "source_notice_count":len(entries),
            "review_only_public_notice_count":2,
            "blocked_paid_traffic_or_undefined_scope_count":4,
            "portfolio_owner_instruction":"NO_EXTERNAL_CONTACT_OR_BID_WITHOUT_GENUINE_SUPPLIER_ELIGIBILITY_AND_FOUNDER_APPROVAL",
            "commercial_lane":"TENDER_CONSULTING_EXISTING_EMPIREOS",
            "briefs":[
                _ryde_brief(ryde),
                _land_brief(land),
            ],
        }
    except (ValueError,KeyError,TypeError,OverflowError):
        return held


def _task(number: int, owner: str, decision: str, evidence: str) -> dict[str,str|int]:
    return {
        "priority":number,
        "owner":owner,
        "task":decision,
        "acceptance_evidence":evidence,
        "status":"NOT_VERIFIED",
        "external_action_authorized":False,
    }


def _ryde_brief(x: Mapping[str,Any]) -> dict[str,Any]:
    return {
        "ocid":RYDE_OCID,
        "title":EXPECTED[RYDE_OCID],
        "official_notice_url":RYDE_URL,
        "issuer_documents_public_url":RYDE_PUBLIC,
        "consultant_recommendation":"NO_BID_UNLESS_QUALIFIED_INDEPENDENT_AUDITOR_AND_ALL_MANDATORY_PROOFS",
        "capability_boundary":"AI_CANNOT_ACT_AS_ACCREDITED_INDEPENDENT_GDPR_AUDITOR",
        "publication_verified_not_supplier_eligible":True,
        "aggregated_feed_deadline_utc":"2026-10-26T12:00:00+00:00",
        "issuer_quote_deadline_unconfirmed_utc":"2026-11-02T12:00:00+00:00",
        "deadline_status":"CONFLICT_ISSUER_CONFIRMATION_REQUIRED",
        "advertised_contract_estimate_gbp":None,
        "winning_bid_probability":"NOT_ESTIMABLE",
        "validated_supplier_evidence_count":0,
        "qualification_requirements":[
            {"issuer_requirement":text,"supplier_proof":"NOT_VERIFIED",
             "evidence_url":RYDE_PUBLIC}
            for text in x["issuer_required_qualifications"]
        ],
        "consultant_owner_tasks":[
            _task(1,"PROCUREMENT_OWNER","Confirm legally operative final deadline, latest clarifications and amendments with issuer","Written authoritative clarification; do not presume 2 Nov"),
            _task(2,"DPO_COMPLIANCE_SPECIALIST","Verify appropriately accredited, independent named data protection auditor, equivalent qualification and completed public authority work","Actual qualification and dated client references"),
            _task(3,"ORIGINAL_BUSINESS_OWNER","Verify £5m professional indemnity and £5m public liability policies, ICO registration and data security controls","Real current certificates and registration; no invented credentials"),
            _task(4,"DELIVERY_OWNER","Confirm site visits to Ryde, reports, ROPA, findings, security and staff resources","Named people, availability, work programme and rights"),
            _task(5,"FINANCE_OWNER","Only after specialist qualification: cost labour, travel, liability and subcontracting; secure original founder price approval","Written source-backed net cost, tax and margin model"),
        ],
        "provisional_delivery_method_not_buyer_approved": [
            "Independent scoping and conflict review",
            "Onsite interviews, sampling and lawful data access under confidentiality",
            "Professional regulatory testing and evidence-led RAG audit findings",
            "ROPA, data-flow artefacts and prioritised compliance action plan",
            "Qualified lead auditor signs final findings and councillor presentation",
        ],
        "ready_to_bid":False,
        "signed_quote":False,
        "revenue_verified":False,
    }


def _land_brief(x: Mapping[str,Any]) -> dict[str,Any]:
    return {
        "ocid":LAND_OCID,
        "title":EXPECTED[LAND_OCID],
        "official_notice_url":LAND_URL,
        "second_official_government_notice_url":LAND_PUBLIC,
        "consultant_recommendation":"HOLD_FULL_RFQ_AND_LAND_ECONOMIC_CONSULTANT_REQUIREMENTS",
        "capability_boundary":"AI_RESEARCH_ASSISTANT_NOT_VERIFIED_SPECIALIST_LAND_AND_INVESTMENT_CONSULTANCY",
        "published_estimate_gbp":"25000.00",
        "advertised_value_is_sale_or_price":False,
        "evaluation_quality_percent":80,
        "evaluation_price_percent":20,
        "winning_bid_probability":"NOT_ESTIMABLE",
        "full_rfq_scoring_questions":"NOT_VERIFIED",
        "published_questions_deadline_utc":"2026-10-26T12:00:00+00:00",
        "published_full_notice_submit_deadline_utc":"2026-10-30T12:00:00+00:00",
        "public_summary_displays_2026_10_31":True,
        "multi_quote_portal_deadline_reconciled":False,
        "procurement_reference":"CA18567",
        "rfq_portal":"https://suppliers.multiquote.com",
        "supplier_evidence_status":"NOT_VERIFIED",
        "consultant_owner_tasks":[
            _task(1,"PROCUREMENT_OWNER","Access full CA18567 RFQ through authorised supplier portal and verify exact dates and amendments","Complete lawful supplier documents, binding deadline and 80% quality subcriteria"),
            _task(2,"LAND_INVESTMENT_SPECIALIST","Determine mandatory planning/GIS/investment-market expertise and comparable signed references","Independent named consultant, credentials and legitimate case studies"),
            _task(3,"RESEARCH_DATA_RIGHTS_OWNER","Confirm statutory planning, land ownership, site availability, data licensing and cross-border constraints","Documented approved data sources, usage rights and method"),
            _task(4,"DELIVERY_OWNER","Validate content of investment land guide, stakeholder consultations, design and the public body acceptance procedure","Buyer-spec work breakdown with reviewable hours/ownership"),
            _task(5,"FINANCE_OWNER","Obtain sourced costs for specialist labour, GIS/data, site research, design, travel, compliance and contingencies","Real GBP cost inputs and minimum acceptable margin; 25000 is only an estimate"),
            _task(6,"FOUNDER","Make final bid/no-bid judgment only after full RFQ, supplier capability and net margin can be independently verified","Explicit price and legally binding terms approval; no automatic quote or submission"),
        ],
        "provisional_delivery_method_not_buyer_approved":[
            "Review RFQ and identify mandatory quality evidence, outcomes and constraints",
            "Define sites and corridor investment geography with responsible land/urban expertise",
            "Develop source-cited public land/market/GIS evidence and exclude unverified sites",
            "Cross-check transport, infrastructure, permissions, title/ownership and strategic planning risks",
            "Draft an investor-facing guide with specialist visual design and a traceable evidence appendix",
            "Human commercial and legal QA before submitting deliverables under accepted terms",
        ],
        "internal_economic_readiness":"NOT_CALCULABLE_WITHOUT_RFQ_AND_VERIFIED_DELIVERY_COSTS",
        "ready_to_bid":False,
        "quote_approved":False,
        "revenue_verified":False,
    }


def read_original_private_source(root: Path) -> dict[str,Any] | None:
    p=root/INPUT
    try:
        st=p.stat()
        if (p.is_symlink() or p.parent.is_symlink()
            or not stat.S_ISREG(st.st_mode)
            or stat.S_IMODE(st.st_mode)!=0o600
            or st.st_size>80000 or st.st_size<300):
            return None
        data=json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else None
    except (OSError,UnicodeError,ValueError):
        return None


def review(root: Path, *, now: datetime|None=None) -> dict[str,Any]:
    src=read_original_private_source(root)
    return consult(src,now=now or datetime.now(timezone.utc))


def save_private(root: Path, report: Mapping[str,Any]) -> Path:
    if report.get("status")!=READY:
        raise ValueError("HELD_CONSULTANT_REVIEW_NOT_SAVED")
    root=Path(root).resolve(strict=True)
    path=root/OUTPUT
    folder=path.parent
    if (folder.is_symlink() or not folder.is_dir()
        or stat.S_IMODE(folder.stat().st_mode)!=0o700
        or path.is_symlink()
        or (path.exists() and
            (not path.is_file() or stat.S_IMODE(path.stat().st_mode)!=0o600))):
        raise ValueError("UNSAFE_PRIVATE_TENDER_CONSULTANT_OUTPUT")
    fd,tmp=tempfile.mkstemp(prefix=".tender-consultant-",suffix=".json",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(report,f,indent=2,sort_keys=True)
            f.write("\n");f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return path


def local_shadow_advice(
    verified_report: Mapping[str, Any],
    *,
    call: Any = None,
) -> dict[str, Any]:
    """Optional local-only model brainstorming; NEVER imported as source truth.

    Inputs are *fixed public facts*, not supplier/person credentials, secrets,
    private PDF bodies or external tender portal content. No model output may
    modify the deterministic consultant dossier or canonical authority.
    """
    held={
        "status":"SHADOW_ADVICE_HELD_NO_NEW_CLAIMS",
        "authority":"none",
        "source_evidence_upgraded":False,
        "qualified_supplier_inferred":False,
        "bid_allowed":False,
        "human_review_required":True,
        "questions":[],
    }
    if (not isinstance(verified_report,Mapping)
        or verified_report.get("status")!=READY
        or len(verified_report.get("briefs",[]))!=2
        or verified_report.get("bid_ready_count")!=0
        or verified_report.get("outbound_sent") is not False):
        return held
    system=(
        "You are a SHADOW research assistant to a UK public tender consultant. "
        "You cannot certify qualifications, advise on specific law as a solicitor, "
        "claim a contract won or read a private portal. "
        "Return exactly FOUR numbered short review QUESTIONS starting 'Q1:', "
        "'Q2:', 'Q3:', 'Q4:', each ending in '?'. "
        "Ask two about the land guide and two about GDPR audit. "
        "Do not invent documents, people, amounts, credentials, quotations or external actions. "
        "Only ask what a qualified consultant must VERIFY."
    )
    user=(
        "PUBLIC FACTS ONLY: Land Guide CA18567: government-advertised GBP25000 estimate, "
        "80% quality and 20% price, RFQ detail not public, buyer expects experienced land "
        "and investment consultancy, published bid closing Oct 30 2026 at noon, "
        "portal deadline not verified. "
        "Ryde GDPR Data Audit: named qualified independent data auditor, public sector "
        "references, GBP5m PI and GBP5m PL insurance required. Government notice suggests "
        "Oct 26, issuer PDF says Nov 2 for submission and Oct 26 for clarifications. "
        "Empire AI supplier compliance, delivery capacity and actual cost not verified. "
        "Ask questions only; no unsupported conclusions."
    )
    try:
        if call is None:
            import requests
            def call(payload: dict[str,Any]) -> Mapping[str,Any]:
                r=requests.post(
                    "http://127.0.0.1:11435/v1/chat/completions",
                    json=payload,timeout=(3,35),allow_redirects=False,
                )
                if r.status_code!=200 or len(r.content)>12000:
                    raise ValueError("LOCAL_MODEL_UNAVAILABLE")
                return r.json()
        data=call({
            "model":"qwen2.5-coder:1.5b",
            "messages":[{"role":"system","content":system},
                        {"role":"user","content":user}],
            "temperature":0.15,"max_tokens":320,"stream":False,
        })
        raw=data["choices"][0]["message"]["content"]
        if not isinstance(raw,str) or len(raw)>3000:
            return held
        import re
        questions=[]
        for line in raw.splitlines():
            candidate=line.strip()
            if not re.fullmatch(r"Q[1-4]:\s+.{12,200}\?",candidate):
                continue
            if any(forbidden in candidate.casefold() for forbidden in (
                "http", "www.", "@", "submit a bid", "send an email",
                "you are qualified", "you have certification", "contact the buyer",
                "pay the", "guaranteed", "automatically")):
                continue
            questions.append(candidate)
        if (len(questions)!=4 or
            [x.split(":",1)[0] for x in questions]!=["Q1","Q2","Q3","Q4"]):
            return held
        return {
            **held,
            "status":"LOCAL_SHADOW_QUESTIONS_UNVERIFIED_FOR_HUMAN_REVIEW",
            "model":"qwen2.5-coder:1.5b",
            "model_location":"EXISTING_LOOPBACK",
            "questions":questions,
        }
    except Exception:
        return held
