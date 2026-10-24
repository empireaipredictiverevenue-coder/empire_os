"""Read-only multi-sector procurement qualification, original Tender Consultant owner.

Uses UK Cabinet Office official OCDS records and two fixed Innovate UK
challenge pages. This is a proposal/eligibility REVIEW, not an ingestion
system, canonical EmpireDB write, bidder or autonomous outreach agent.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from empire_os.tender_land_gis_evidence import BASE, _private_path
from empire_os.data_exchange_procurement_context import OGL_V3

INPUT = "empire_multisector_official_deal_research_20261024.json"
OUTPUT = "empire_multisector_qualified_portfolio_latest.json"
SCHEMA = "empire.tender_multisector_qualified_portfolio.v1"
FTS = "https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages/"
CHALLENGE = "https://www.ktninnovationexchange.co.uk/challenges/"
OCID_RE = re.compile(r"ocds-h6vhtk-[0-9a-f]{6}\Z")
NOTICE_RE = re.compile(r"[0-9]{6}-2026\Z")
MAX_RECORDS = 15

# Practical fit to CURRENT evidence, not proof of bid suitability or buying intent.
CAPABILITY_GATES = {
    "healthcare_data":("NHS_WORKFORCE_SUBJECT_MATTER_LEAD","NHS_ATAMIS_RFQ_AND_CAPACITY"),
    "healthcare_research":("INDEPENDENT_HEALTH_WORKFORCE_EVALUATOR","NHS_ATAMIS_RFQ_AND_MIXED_METHODS_PLAN"),
    "education_built_environment":("CHARTERED_STRUCTURAL_ENGINEER_AND_SAFE_CAPTURE_PARTNER","INNOVATE_UK_FULL_CHALLENGE_AND_TECHNICAL_PILOT_RIGHTS"),
    "housing_fintech":("PUBLIC_SECTOR_HOUSING_FINANCE_SECURITY_PROVIDER","NO_CURRENT_OPEN_BID_PRE_MARKET_ONLY"),
    "energy_fuel_poverty":("QUALIFIED_ENERGY_ADVISER_AND_VULNERABLE_CLIENT_SAFEGUARDS","PROCONTRACT_PME_NOT_OPEN_BID"),
    "environment_conservation":("QUALIFIED_HABITAT_ECOLOGIST","PROTECTED_AREA_CONSERVATION_METHODOLOGY"),
    "environment_geoscience":("QUALIFIED_GEOLOGIST_OR_GEODIVERSITY_SPECIALIST","LOCAL_NATURE_RECOVERY_AUDIT_CREDENTIALS"),
    "flood_infrastructure":("QUALIFIED_FLOOD_CIVIL_ENGINEER","ENGINEERING_RISK_AND_PROFESSIONAL_INDEMNITY"),
    "land_regeneration":("AUTHORIZED_DEVELOPER_OR_LAND_CONSULTANT","PME_PROPERTY_INVESTMENT_NOT_DATA_CONTRACT"),
    "digital_marketing":("MEDIA_AND_PUBLIC_REALM_SPECIALIST","PAID_ADVERTISING_POLICY_AND_DATA_RIGHTS_HOLD"),
}
EXISTING_PRODUCT_COMPONENTS = {
    "healthcare_data":("entity_graph_export",),
    "healthcare_research":("market_signal_feed",),
    "education_built_environment":("spatial_physical_intelligence",),
    "housing_fintech":("forecast_snapshot",),
    "energy_fuel_poverty":("property_intelligence_monitor",),
    "environment_conservation":("spatial_physical_intelligence",),
    "environment_geoscience":("spatial_physical_intelligence",),
    "flood_infrastructure":("spatial_physical_intelligence",),
    "land_regeneration":("property_intelligence_monitor",),
    "digital_marketing":(),
    "defence_supply_chain_evidence":("entity_graph_export","market_signal_feed"),
}

PRIORITY_ORDER = {
    "healthcare_data":2,"healthcare_research":3,"education_built_environment":4,
    "environment_conservation":5,"environment_geoscience":6,
    "flood_infrastructure":7,"energy_fuel_poverty":8,
    "housing_fintech":9,"land_regeneration":10,"digital_marketing":11,
}
CHALLENGES={
    "446":{
        "title":"Verified reporting of the value created by defence contracts",
        "sector":"defence_supply_chain_evidence",
        "due_date":"2026-11-06",
        "screening_reason":"direct_existing_provenance_custody_deduplication_architecture_fit",
        "release_dependent_on_login":True,
    },
    "447":{
        "title":"Systemic capture and analysis of structural condition data",
        "sector":"education_built_environment",
        "due_date":"2026-12-04",
        "screening_reason":"relevant_data_analysis_but_structural_engineering_and_physical_capture_unverified",
        "release_dependent_on_login":True,
    },
}


def _read_private(root:Path)->dict:
    p=_private_path(root,INPUT)
    st=p.lstat()
    if (p.is_symlink() or not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid()
        or st.st_nlink!=1 or stat.S_IMODE(st.st_mode)!=0o600
        or not 600<=st.st_size<=160000):
        raise ValueError("PRIVATE_BASELINE_SOURCE_REQUIRED")
    with p.open("rb") as f:
        opened=os.fstat(f.fileno())
        if opened.st_ino!=st.st_ino or opened.st_dev!=st.st_dev or opened.st_size!=st.st_size:
            raise ValueError("BASELINE_CHANGED_WHILE_READING")
        obj=json.load(f)
    if not isinstance(obj,dict):
        raise ValueError("INVALID_BASELINE")
    return obj


def _dt(t:Any)->datetime|None:
    if not isinstance(t,str):return None
    try:
        d=datetime.fromisoformat(t.replace("Z","+00:00"))
    except (ValueError,OverflowError):
        return None
    if d.tzinfo is None or d.utcoffset() is None:return None
    return d.astimezone(timezone.utc)


def _validate_baseline(data:Any)->list[dict]:
    if (not isinstance(data,Mapping)
        or data.get("schema_version")!="empire.cross_sector_official_deals_research.v1"
        or data.get("verification")!="PUBLIC_OCDS_API_READ_ONLY_VERIFIED_EACH_RECORD"
        or data.get("canonical_empiredb_writes") is not False
        or data.get("contact_emails_sent") is not False
        or data.get("formal_submissions")!=0
        or data.get("actual_fees_earned_gbp")!=0):
        raise ValueError("ORIGINAL_RESEARCH_SCOPE_NOT_VERIFIED")
    rows=data.get("opportunities")
    if (not isinstance(rows,list) or not 1<=len(rows)<=MAX_RECORDS
        or data.get("discovery_evidence_count")!=len(rows)):
        raise ValueError("SOURCE_COUNT_INVALID")
    seen=set()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("INVALID_PORTFOLIO_RECORD")
        ocid=row.get("ocid")
        if (not isinstance(ocid,str) or not OCID_RE.fullmatch(ocid)
            or ocid in seen
            or row.get("record_api_url")!=FTS+ocid
            or row.get("sector") not in CAPABILITY_GATES
            or row.get("empire_ai_bid_submitted") is not False
            or row.get("external_outreach_authorised") is not False
            or row.get("paid_buyer_order_verified") is not False):
            raise ValueError("SOURCE_IDENTITY_OR_AUTHORITY_INVALID")
        seen.add(ocid)
    return rows


def _published_record(payload: Any, *, ocid:str)->dict:
    if not isinstance(payload,Mapping) or payload.get("license")!=OGL_V3:
        raise ValueError("OFFICIAL_OCDS_LICENSE_MISSING")
    if not isinstance(payload.get("publisher"),Mapping) or payload["publisher"].get("name")!="Cabinet Office":
        raise ValueError("UNTRUSTED_PROCUREMENT_PUBLISHER")
    records=payload.get("records")
    if not isinstance(records,list) or len(records)!=1 or records[0].get("ocid")!=ocid:
        raise ValueError("RECORD_OCID_NOT_CORROBORATED")
    rec=records[0]
    if not isinstance(rec.get("compiledRelease"),Mapping):
        raise ValueError("NO_SOURCE_COMPILED_RELEASE")
    notice=rec["compiledRelease"]
    tender=notice.get("tender")
    if not isinstance(tender,Mapping):
        raise ValueError("SOURCE_MISSING_TENDER")
    stage=tender.get("status")
    if stage not in ("active","planning","planned"):
        raise ValueError("NO_CURRENT_PROCUREMENT_OR_ENGAGEMENT")
    buyer=(notice.get("buyer") or {}).get("name")
    title=tender.get("title")
    if (not isinstance(buyer,str) or not buyer.strip()
        or not isinstance(title,str) or not title.strip()
        or not _dt(notice.get("date"))):
        raise ValueError("TENDER_PUBLISHER_CORE_FIELDS_MISSING")
    notices=[]
    for rel in rec.get("releases",[]):
        if not isinstance(rel,Mapping):raise ValueError("INVALID_RELEASE")
        ident=rel.get("id")
        if not isinstance(ident,str) or not NOTICE_RE.fullmatch(ident):
            raise ValueError("INVALID_PUBLISHED_NOTICE_ID")
        notices.append(ident)
    if not notices:
        raise ValueError("PUBLISHED_NOTICE_MISSING")
    bid_due=_dt((tender.get("tenderPeriod") or {}).get("endDate"))
    questions_due=_dt((tender.get("enquiryPeriod") or {}).get("endDate"))
    val=tender.get("value") or {}
    amount=val.get("amount")
    if val:
        if (val.get("currency")!="GBP" or type(amount) not in (float,int)
            or amount<0 or amount>2_000_000_000):
            raise ValueError("ADVERTISED_VALUE_MALFORMED")
    return {
        "ocid":ocid,"latest_notice":"https://www.find-tender.service.gov.uk/Notice/"+notices[-1],
        "buyer":buyer.strip()[:180],"title":title.strip()[:300],
        "stage":stage,"latest_notice_timestamp":_dt(notice.get("date")).isoformat(),
        "published_estimate_ex_vat_gbp":amount if val else None,
        "questions_deadline_utc":questions_due.isoformat() if questions_due else None,
        "tender_submission_deadline_utc":bid_due.isoformat() if bid_due else None,
        "public_official_record":FTS+ocid,
        "raw_record_pii_not_copied":True,
    }


def _challenge_page(html:Any, challenge_id:str)->dict:
    if challenge_id not in CHALLENGES or not isinstance(html,str) or not 400<=len(html)<=350000:
        raise ValueError("CHALLENGE_PAGE_MISSING_OR_OVERSIZED")
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    c=CHALLENGES[challenge_id]
    if c["title"].lower() not in title.lower():
        raise ValueError("CHALLENGE_TITLE_CHANGED")
    text=" ".join(soup.get_text(" ",strip=True).split())
    opens=re.search(r"Challenge opens\s+(\d\d/\d\d/\d{4})",text,re.I)
    closes=re.search(r"Challenge closes\s+(\d\d/\d\d/\d{4})",text,re.I)
    if not opens or not closes:
        raise ValueError("CHALLENGE_DATE_MISSING")
    day=datetime.strptime(closes.group(1),"%d/%m/%Y").date().isoformat()
    if day!=c["due_date"]:
        raise ValueError("CHALLENGE_DEADLINE_CHANGED_REQUIRES_OWNER_REVIEW")
    return {
        "challenge_id":challenge_id,
        "source_url":CHALLENGE+challenge_id,
        "title":c["title"],"sector":c["sector"],
        "opens_date":datetime.strptime(opens.group(1),"%d/%m/%Y").date().isoformat(),
        "closes_date":day,
        "closes_clock_time":"NOT_PUBLISHED_ON_PUBLIC_CHALLENGE_PAGE",
        "full_conditions_requiring_registration":c["release_dependent_on_login"],
        "screening_reason":c["screening_reason"],
        "challenge_is_signed_purchase_order":False,
        "first_party_pilot_revenue_guaranteed":False,
    }


def qualify(
    original:Any, official:Mapping[str,Any], challenge_pages:Mapping[str,str], *,
    observed_at:datetime
)->dict:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    now=observed_at.astimezone(timezone.utc)
    rows=_validate_baseline(original)
    if set(official)!={x["ocid"] for x in rows}:
        raise ValueError("SOURCE_RECORD_SET_INCOMPLETE")
    if set(challenge_pages)!=set(CHALLENGES):
        raise ValueError("CHALLENGE_COVERAGE_INCOMPLETE")
    published_challenges={key:_challenge_page(challenge_pages[key],key) for key in CHALLENGES}
    from empire_os.intelligence_data_products import get_data_product
    if set(EXISTING_PRODUCT_COMPONENTS)!=set(CAPABILITY_GATES)|{"defence_supply_chain_evidence"}:
        raise ValueError("SECTOR_PRODUCT_COVERAGE_INCOMPLETE")
    for keys in EXISTING_PRODUCT_COMPONENTS.values():
        if any(get_data_product(k) is None for k in keys):
            raise ValueError("UNKNOWN_CANONICAL_PRODUCT_COMPONENT")
    output=[]
    for row in rows:
        valid=_published_record(official[row["ocid"]],ocid=row["ocid"])
        sector=row["sector"]
        expected=row.get("notice_title")
        if not isinstance(expected,str) or expected.strip()!=valid["title"]:
            raise ValueError("BASELINE_NOTICE_TITLE_CHANGED")
        published_stage=valid["stage"]
        expected_stage=row.get("stage")
        if published_stage!=expected_stage:
            raise ValueError("PROCUREMENT_STAGE_CHANGED_REQUIRES_NEW_SOURCE_REVIEW")
        deadline=_dt(valid["tender_submission_deadline_utc"])
        closed=deadline is not None and deadline<=now
        active=published_stage=="active" and not closed
        specialist,details=CAPABILITY_GATES[sector]
        rank=PRIORITY_ORDER[sector]
        route=("OFFICIAL_BID_ACCESS_AND_PROFESSIONAL_PARTNER_REVIEW" if active
               else "PRELIMINARY_ENGAGEMENT_ONLY_NOT_OPEN_TENDER" if published_stage!="active"
               else "SUBMISSION_CLOSED_NO_BID")
        if sector=="education_built_environment":
            route="INNOVATE_UK_CHALLENGE_PARTNER_CAPABILITY_REVIEW_ONLY"
        output.append({
            **valid,
            "sector":sector,"rank_for_manual_review":rank,
            "review_status":route,
            "specialist_or_delivery_gate":specialist,
            "unverified_access_scope":details,
            "founder_bid_authority":False,
            "empire_ai_supplier_eligibility_verified":False,
            "signed_professional_partner":False,
            "buyer_interest_in_empire_ai_verified":False,
            "evidence_backed_platform_workpackage_fit":"HYPOTHESIS_ONLY",
            "candidate_existing_product_components":list(EXISTING_PRODUCT_COMPONENTS[sector]),
            "complete_customer_deliverable_verified":False,
            "bid_or_interest_form_submitted":False,
            "outbound_sent":False,
            "is_a_direct_paid_data_order":False,
        })
    # Challenge 447 is part of DfE's same requirement, not a second sale.
    dfe=next(x for x in output if x["sector"]=="education_built_environment")
    dfe["related_innovate_uk_challenge"]=published_challenges["447"]["source_url"]
    dfe["challenge_closing_date"]=published_challenges["447"]["closes_date"]
    # New, different industry and genuinely close technical fit.
    defence={
        "sector":"defence_supply_chain_evidence",
        "rank_for_manual_review":1,
        "review_status":"OPEN_INNOVATION_CHALLENGE_REQUIRES_LOGIN_AND_ELIGIBILITY_REVIEW",
        "specialist_or_delivery_gate":"INDEPENDENT_THIRD_PARTY_VERIFICATION_AND_CONSENTED_SUPPLY_CHAIN_PILOT_REQUIRED",
        "unverified_access_scope":"FULL_APPLICATION_TERMS_BEHIND_LOGIN_NO_FUNDED_ORDER_VERIFIED",
        "published_estimate_ex_vat_gbp":None,
        "buyer":"e50K / Innovate UK Business Connect",
        "title":published_challenges["446"]["title"],
        "source_url":published_challenges["446"]["source_url"],
        "challenge_closing_date":published_challenges["446"]["closes_date"],
        "challenge_closing_clock_time":"UNKNOWN",
        "founder_bid_authority":False,
        "empire_ai_supplier_eligibility_verified":False,
        "signed_professional_partner":False,
        "buyer_interest_in_empire_ai_verified":False,
        "evidence_backed_platform_workpackage_fit":"HYPOTHESIS_ONLY",
        "candidate_existing_product_components":list(EXISTING_PRODUCT_COMPONENTS["defence_supply_chain_evidence"]),
        "complete_customer_deliverable_verified":False,
        "bid_or_interest_form_submitted":False,
        "outbound_sent":False,
        "is_a_direct_paid_data_order":False,
        "challenge_is_signed_purchase_order":False,
    }
    output.append(defence)
    output.sort(key=lambda x:x["rank_for_manual_review"])
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "owner":"ORIGINAL_TENDER_CONSULTANT_COMMERCIAL_PROCUREMENT",
        "observed_at_utc":now.isoformat(),
        "public_procurement_cases_verified":len(rows),
        "innovation_challenge_pages_verified":len(published_challenges),
        "independent_opportunities_count":len(output),
        "cross_notice_duplicate_dfe_challenge_count":1,
        "distinct_sectors_count":len(set(x["sector"] for x in output)),
        "status":"MULTISECTOR_PUBLIC_OPPORTUNITIES_REVIEW_ONLY",
        "classification_is_not_award_probability":True,
        "bid_ready_count":0,
        "qualified_to_deliver_count":0,
        "actual_clients_contracted":0,
        "cash_revenue_verified_gbp":None,
        "requested_new_outbound":False,
        "source_data_accepted_to_canonical_empiredb":False,
        "crm_writes":False,
        "new_emails_sent":False,
        "new_tender_submissions":False,
        "funds_moved":False,
        "next_action":"Founder and procurement owner review top niche-fit opportunities; access full original application/RFQ and validate capability/rights with named partners before any send.",
        "opportunities":output,
    }


def collect_public_sources(original:Mapping)->tuple[dict,dict]:
    rows=_validate_baseline(original)
    import requests
    session=requests.Session()
    official={}
    pages={}
    for entry in rows:
        ocid=entry["ocid"]
        try:
            with session.get(FTS+ocid,stream=True,timeout=(4,14),allow_redirects=False,
                  headers={"User-Agent":"EmpireOS-Original-Tender-Observer/1.0"}) as res:
                if (res.status_code!=200
                    or int(res.headers.get("Content-Length","0"))>360000):
                    raise ValueError("OFFICIAL_SOURCE_BAD_STATUS_OR_TOO_LARGE")
                buff=bytearray()
                for chunk in res.iter_content(chunk_size=8192):
                    buff.extend(chunk)
                    if len(buff)>360000:
                        raise ValueError("OFFICIAL_SOURCE_OVERSIZED")
        except requests.RequestException as exc:
            raise ValueError("OFFICIAL_SOURCE_NETWORK_FAILURE") from exc
        try:official[ocid]=json.loads(buff)
        except (UnicodeError,ValueError) as exc:
            raise ValueError("OFFICIAL_SOURCE_NOT_JSON") from exc
    for key in CHALLENGES:
        try:
            with session.get(CHALLENGE+key,stream=True,timeout=(4,14),
                  allow_redirects=False,headers={"User-Agent":"EmpireOS-Original-Tender-Observer/1.0"}) as res:
                if res.status_code!=200 or int(res.headers.get("Content-Length","0"))>350000:
                    raise ValueError("INNOVATION_CHALLENGE_BAD_STATUS_OR_SIZE")
                buff=bytearray()
                for chunk in res.iter_content(chunk_size=8192):
                    buff.extend(chunk)
                    if len(buff)>350000:raise ValueError("INNOVATION_CHALLENGE_OVERSIZED")
        except requests.RequestException as exc:
            raise ValueError("CHALLENGE_SOURCE_NETWORK_FAILURE") from exc
        try:pages[key]=buff.decode("utf-8")
        except UnicodeError as exc:
            raise ValueError("CHALLENGE_SOURCE_BAD_ENCODING") from exc
    return official,pages


def materialize(root:Path, *, now:datetime|None=None)->dict:
    """Explicit on-demand review; no service, CRON, DB or external outbound."""
    original=_read_private(root)
    official,challenge_pages=collect_public_sources(original)
    report=qualify(original,official,challenge_pages,observed_at=now or datetime.now(timezone.utc))
    from empire_os.tender_land_gis_evidence import _save
    _save(root,OUTPUT,report)
    return report
