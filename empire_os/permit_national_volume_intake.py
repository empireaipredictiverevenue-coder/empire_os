"""Bounded, reproducible high-volume research intake into EXISTING PermitOS.

Seed exact source-backed 38 company/37 business-email inventory, reconcile
the ORIGINAL wave3 NYC eight and original four first-party-only candidates,
then accept ≤5,000 EXTRA externally sourced candidate records per batch.

Additional records are unverified research until independent source checks.
Dedupe is conservative, conflicting identities quarantined. No guesses,
proxies, crawls, personal/social harvesting, email sending, SMTP probing,
customer distribution, CRM/DB writes or invented buyer qualification.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timedelta,timezone
import json,re
from typing import Any,Mapping
from urllib.parse import urlparse

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_email_list_expansion import MARKETS,build_expanded_list,validate_expanded_list
from empire_os.permit_prospect_wave3 import ROWS as ORIGINAL_NYC_WAVE3
from empire_os.permit_national_list_quality_engine import build_quality_board,validate_quality_board

SCHEMA="empire.permit_data.national_qualified_contact_volume_intake.v1"
EXTERNAL_SCHEMA="empire.permit_data.national_external_business_candidate.v1"
MAX_IMPORTED=5000
BATCH_FIELDS=frozenset({
    "schema_version","company","market_id","sector","official_company_url",
    "public_business_email","business_email_evidence_url","evidence_observed_at_utc",
})
DOMAIN=re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,250}[a-z0-9])?\.[a-z]{2,24}$")
EMAIL=re.compile(r"^[a-z0-9][a-z0-9._%+-]{0,63}@[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
PERSONAL_DOMAINS=frozenset({"gmail.com","yahoo.com","hotmail.com","outlook.com",
                           "icloud.com","aol.com","live.com","proton.me"})
TRADE_SECTORS=frozenset({
    "fire_protection","commercial_hvac","hvac","hvac_fire_protection",
    "commercial_roofing","commercial_plumbing","structural_steel",
    "construction","general_contractor","electrical","commercial_solar",
})
EARLIER_FOUR=(
    ("FireQuest Corp.","nyc","fire_protection","https://www.nycfireprotection.com/"),
    ("Buckmiller Automatic Sprinkler","nyc","fire_protection","https://buckmillersprinkler.com/"),
    ("Five Borough Sprinkler","nyc","fire_protection","https://fiveboroughsprinkler.com/"),
    ("Bedrock Mechanical","nyc","fire_protection","https://bedrockmechanical.com/fire-suppression-installation/"),
)


def _domain(url:str)->str:
    if not isinstance(url,str) or len(url)>350 or not url.startswith("https://"):
        raise ValueError("original_intake_https_business_url_required")
    parsed=urlparse(url)
    if (parsed.scheme!="https" or parsed.username or parsed.password
        or parsed.port is not None or parsed.query or parsed.fragment
        or not parsed.hostname):
        raise ValueError("intake_business_source_url_unsafe")
    host=parsed.hostname.lower().removeprefix("www.")
    if not DOMAIN.fullmatch(host) or host.startswith("localhost."):
        raise ValueError("intake_non_public_or_invalid_business_domain")
    return host


def _name(value:str)->str:
    if not isinstance(value,str) or not 3<=len(value.strip())<=115:
        raise ValueError("invalid_company_intake_identity")
    normalized=" ".join(value.casefold().split())
    if any(ord(char)<32 for char in value):
        raise ValueError("unsafe_company_control_character")
    return normalized


def _email(value:str|None)->str|None:
    if value is None:return None
    if not isinstance(value,str):
        raise ValueError("intake_business_email_invalid")
    address=value.strip().lower()
    if not EMAIL.fullmatch(address) or address.rsplit("@",1)[1] in PERSONAL_DOMAINS:
        raise ValueError("intake_business_email_invalid_or_personal_provider")
    return address


def _stamp(value:str,*,at:datetime)->str:
    if not isinstance(value,str):
        raise ValueError("company_source_evidence_timestamp_invalid")
    try:date=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise ValueError("company_source_evidence_timestamp_invalid") from exc
    if (date.utcoffset() is None or date>at+timedelta(minutes=5)
        or at-date>timedelta(days=730)):
        raise ValueError("company_source_evidence_stale_future_or_unbounded")
    return date.astimezone(timezone.utc).isoformat()


def validate_import_candidate(item:Mapping[str,Any],*,at:datetime)->dict:
    if not isinstance(item,Mapping) or set(item)!=BATCH_FIELDS or item.get("schema_version")!=EXTERNAL_SCHEMA:
        raise ValueError("imported_company_evidence_schema_invalid")
    if item.get("market_id") not in MARKETS or item.get("sector") not in TRADE_SECTORS:
        raise ValueError("unknown_permit_market_or_trade")
    company=item["company"].strip()
    _name(company)
    website=_domain(item["official_company_url"])
    source=_domain(item["business_email_evidence_url"])
    if source!=website:
        # Separate business brands, trade directories and third-party contacts
        # require individual provenance review, not auto-admission as company-owned.
        raise ValueError("unverified_source_domain_vs_company_domain")
    email=_email(item["public_business_email"])
    stamp=_stamp(item["evidence_observed_at_utc"],at=at)
    return {
        "market_id":item["market_id"],"company":company,
        "sector":item["sector"],"canonical_company_domain":website,
        "public_business_email":email,
        "official_company_url":item["official_company_url"],
        "evidence_url":item["business_email_evidence_url"],
        "source_observed_at_utc":stamp,
        "research_cohort":"EXTERNAL_USER_EVIDENCE_PENDING_OWNER",
        "source_quality_state":"UNVERIFIED_IMPORTED_SOURCE_NEEDS_INDEPENDENT_CHECK",
        "source_receipt_attached_not_corroborated":True,
    }


def build_volume_intake(*,quality:Mapping[str,Any],at:datetime,
                        candidates:list[Mapping[str,Any]]|None=None,
                        previous:Mapping[str,Any]|None=None)->dict:
    validate_quality_board(quality)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("intake_requires_aware_review_clock")
    now=at.astimezone(timezone.utc)
    qtime=datetime.fromisoformat(quality["evaluated_at_utc"])
    if now<qtime or now-qtime>timedelta(days=30):
        raise ValueError("original_quality_evidence_outside_intake_window")
    baseline=build_expanded_list(at=datetime.fromisoformat(quality["evaluated_at_utc"]))
    # The baseline's generated SHA depends on its observation clock, while the
    # quality report retains original source list SHA. Read the existing source
    # hash from the already-validated quality rows, not a regenerated date.
    if set((r["market_id"],r["company"],r["business_email"])
           for r in quality["quality_rows"])!=set(
               (r["market_id"],r["company"],r["email"]) for r in baseline["companies"]):
        raise ValueError("quality_source_companies_not_original_national_38")
    if candidates is None:candidates=[]
    if not isinstance(candidates,list) or len(candidates)>MAX_IMPORTED:
        raise ValueError("bounded_external_company_batch_limit")
    # Original company email/source records are preserved; the owner may
    # subsequently recheck one specific source without overwriting originals.
    records=[]
    for r in baseline["companies"]:
        # Earlier source link may be a third-party directory, so deliberately
        # do not infer a publisher-host domain as canonical business identity.
        site=(r["email"].rsplit("@",1)[1] if r["email"]
              else _domain(r["source_url"]))
        records.append({
            "market_id":r["market_id"],"company":r["company"],
            "sector":r["sector"],"canonical_company_domain":site,
            "public_business_email":r["email"],
            "official_company_url":r["source_url"],"evidence_url":r["source_url"],
            "source_observed_at_utc":None,
            "research_cohort":"ORIGINAL_NATIONAL_38_SHA_BACKED",
            "source_quality_state":"EXISTING_ORIGINAL_CONTACT_RESEARCH",
            "source_receipt_attached_not_corroborated":False,
        })
    for r in ORIGINAL_NYC_WAVE3:
        records.append({
            "market_id":"nyc","company":r[0],
            "sector":"fire_protection",
            "canonical_company_domain":r[1],
            "public_business_email":_email(r[2]),
            "official_company_url":r[3],
            "evidence_url":r[4],
            "source_observed_at_utc":"2026-10-24T00:00:00+00:00",
            "research_cohort":"ORIGINAL_NYC_WAVE3_EIGHT",
            "source_quality_state":"HISTORICAL_FIRST_PARTY_RESEARCH_PENDING_REFRESH",
            "source_receipt_attached_not_corroborated":False,
        })
    for name,market,sector,website in EARLIER_FOUR:
        records.append({
            "market_id":market,"company":name,
            "sector":sector,"canonical_company_domain":_domain(website),
            "public_business_email":None,
            "official_company_url":website,"evidence_url":website,
            "source_observed_at_utc":"2026-10-24T00:00:00+00:00",
            "research_cohort":"ORIGINAL_NYC_SOURCE_COHORT_FOUR",
            "source_quality_state":"SERVICE_FIT_RESEARCH_NO_BUSINESS_EMAIL",
            "source_receipt_attached_not_corroborated":False,
        })
    assert len(records)==50
    previous_imports=0
    if previous is not None:
        validate_volume_intake(previous)
        prior_at=datetime.fromisoformat(previous["reviewed_at_utc"])
        if (previous["source_quality_board_sha256"]!=quality["quality_board_sha256"]
            or prior_at>now or len(previous["companies"])<50):
            raise ValueError("previous_volume_batch_does_not_match_original_quality")
        # Check the first fifty original records are unchanged. Never accept
        # a previous report that silently rewrote a known contact identity.
        for current,former in zip(records,previous["companies"][:50]):
            for name in ("market_id","company","sector","canonical_company_domain",
                         "public_business_email","official_company_url","evidence_url",
                         "research_cohort"):
                if current[name]!=former.get(name):
                    raise ValueError("previous_volume_original_fifty_source_modified")
        for former in previous["companies"][50:]:
            if former.get("research_cohort")!="EXTERNAL_USER_EVIDENCE_PENDING_OWNER":
                raise ValueError("untrusted_prior_external_volume_cohort")
            record={k:former[k] for k in (
                "market_id","company","sector","canonical_company_domain",
                "public_business_email","official_company_url","evidence_url",
                "source_observed_at_utc","research_cohort","source_quality_state",
                "source_receipt_attached_not_corroborated")}
            records.append(record)
            previous_imports+=1
    added=[validate_import_candidate(x,at=now) for x in candidates]
    # Bounded hash indexes: O(N), avoiding quadratic checks for large batches.
    brand_to_domain={}
    domain_to_brand={}
    emails={}
    unique=[]
    duplicate_count=0
    quarantine=[]
    for row in records+added:
        company_key=(row["market_id"],_name(row["company"]))
        dom=row["canonical_company_domain"]
        address=row["public_business_email"]
        existing_brand=brand_to_domain.get(company_key)
        known_email=emails.get(address) if address else None
        known_domain=domain_to_brand.get(dom)
        conflict=None
        if existing_brand is not None and existing_brand!=dom:
            conflict="SAME_MARKET_COMPANY_DIFFERENT_DOMAIN"
        elif known_domain is not None and _name(known_domain)!=_name(row["company"]):
            conflict="DOMAIN_SHARED_BY_DISTINCT_COMPANY_NAMES_REVIEW"
        elif known_email is not None and known_email!=company_key:
            conflict="SAME_BUSINESS_EMAIL_DIFFERENT_ORGANISATION"
        if conflict:
            quarantine.append({
                "company":row["company"],"market_id":row["market_id"],
                "source_url":row["evidence_url"],"reason":conflict,
                "research_only":True,"outreach_allowed":False,
            })
            continue
        if existing_brand is not None:
            duplicate_count+=1
            continue
        brand_to_domain[company_key]=dom
        domain_to_brand[dom]=row["company"]
        if address:emails[address]=company_key
        research_score=(80 if row["research_cohort"]=="ORIGINAL_NATIONAL_38_SHA_BACKED"
                        else 50 if row["research_cohort"]=="ORIGINAL_NYC_WAVE3_EIGHT"
                        else 30 if row["research_cohort"]=="ORIGINAL_NYC_SOURCE_COHORT_FOUR"
                        else 10)
        unique.append({
            **row,
            "stable_research_company_id":digest({
                "market":row["market_id"],"company":_name(row["company"]),
                "domain":dom})[:24],
            "evidence_coverage_score_not_buying_probability":research_score,
            "enrichment_needs":(
                ["RECHECK_FIRST_PARTY_SOURCE","CHECK_CURRENT_BUSINESS_MAILBOX_CONTEXT",
                 "CHECK_SMART_CRM_HISTORY_AND_SUPPRESSION"]
                if address else
                ["FIND_OFFICIAL_GENERAL_BUSINESS_CONTACT","RECHECK_FIRST_PARTY_TRADE_FIT"]),
            "enrichment_stage":"UNVERIFIED_RESEARCH_NOT_BUYER",
            "email_deliverable_verified":False,
            "company_buyer_intent_verified":False,
            "person_suppression_cleared":False,
            "recipient_send_authorized":False,
            "source_data_customer_distribution_authorized":False,
            "qualified_lead":False,
            "outbound_sent":False,
        })
    if len(quarantine)>MAX_IMPORTED or len(unique)>50+MAX_IMPORTED*20:
        raise ValueError("unbounded_company_intake_custody")
    counts=Counter(x["research_cohort"] for x in unique)
    cumulative_imports=counts.get("EXTERNAL_USER_EVIDENCE_PENDING_OWNER",0)
    if cumulative_imports<previous_imports:
        raise ValueError("prior_admitted_company_research_dropped")
    out={
        "schema_version":SCHEMA,
        "reviewed_at_utc":now.isoformat(),
        "source_quality_board_sha256":quality["quality_board_sha256"],
        "canonical_stack":"ONE_EMPIREOS_EMPIREDB_SMART_CRM",
        "source_legacy_company_count":50,
        "source_existing_national_count":38,
        "source_existing_nyc_wave3_count":8,
        "source_existing_first_party_no_email_count":4,
        "previous_volume_intake_sha256":previous["volume_intake_sha256"] if previous is not None else None,
        "import_candidates_submitted":len(added),
        "previously_admitted_external_research_companies":previous_imports,
        "new_external_companies_in_this_run":cumulative_imports-previous_imports,
        "new_external_companies_admitted_as_unverified_research":cumulative_imports,
        "import_duplicates_excluded":duplicate_count,
        "conflicting_company_identifiers_quarantined":len(quarantine),
        "deduplicated_research_companies":len(unique),
        "public_business_email_candidates":sum(x["public_business_email"] is not None for x in unique),
        "no_email_company_count":sum(x["public_business_email"] is None for x in unique),
        "confirmed_buyers":0,"approved_recipients":0,"outbound_sent":0,
        "source_permit_row_queries":0,
        "empiredb_writes":0,"smart_crm_writes":0,
        "payment_moved":False,"verified_revenue_usd":"0.00",
        "execution_authority":"none",
        "cohort_counts":dict(sorted(counts.items())),
        "companies":unique,"quarantine":quarantine,
    }
    out["volume_intake_sha256"]=digest(out)
    return out


def validate_volume_intake(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping) or report.get("schema_version")!=SCHEMA
        or report.get("volume_intake_sha256")!=digest({
            k:v for k,v in report.items() if k!="volume_intake_sha256"})
        or report.get("canonical_stack")!="ONE_EMPIREOS_EMPIREDB_SMART_CRM"
        or report.get("source_legacy_company_count")!=50
        or report.get("confirmed_buyers")!=0
        or report.get("approved_recipients")!=0
        or report.get("outbound_sent")!=0
        or report.get("source_permit_row_queries")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("payment_moved") is not False
        or report.get("verified_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_national_volume_intake_report")
    rows=report.get("companies")
    quarantine=report.get("quarantine")
    if (not isinstance(rows,list) or len(rows)!=report.get("deduplicated_research_companies")
        or not isinstance(quarantine,list)
        or len(quarantine)!=report.get("conflicting_company_identifiers_quarantined")
        or len(rows)>50+MAX_IMPORTED*20
        or len({r.get("stable_research_company_id") for r in rows})!=len(rows)
        or report.get("public_business_email_candidates")!=sum(
            r.get("public_business_email") is not None for r in rows)
        or report.get("no_email_company_count")!=sum(
            r.get("public_business_email") is None for r in rows)):
        raise ValueError("inaccurate_company_email_volume_counts")
    count_external=sum(r.get("research_cohort")=="EXTERNAL_USER_EVIDENCE_PENDING_OWNER" for r in rows)
    # Read-compatible with the original, already SHA-sealed 50-company
    # evidence-only baseline from BEFORE incremental intake existed.
    # This is NOT a generic bypass for a purported historic imported batch.
    legacy_baseline = (
        "new_external_companies_in_this_run" not in report
        and "previously_admitted_external_research_companies" not in report
        and "previous_volume_intake_sha256" not in report
        and report.get("deduplicated_research_companies")==50
        and count_external==0
        and report.get("import_candidates_submitted")==0
        and report.get("new_external_companies_admitted_as_unverified_research")==0
    )
    if not legacy_baseline and (
        count_external!=report.get("new_external_companies_admitted_as_unverified_research")
        or report.get("previously_admitted_external_research_companies",0)>count_external
        or report.get("new_external_companies_in_this_run")!=(
            count_external-report.get("previously_admitted_external_research_companies",0))
        or report.get("import_candidates_submitted",0)>MAX_IMPORTED):
        raise ValueError("cumulative_volume_intake_counts_not_reconciled")
    for row in rows:
        if (row.get("enrichment_stage")!="UNVERIFIED_RESEARCH_NOT_BUYER"
            or row.get("email_deliverable_verified") is not False
            or row.get("company_buyer_intent_verified") is not False
            or row.get("person_suppression_cleared") is not False
            or row.get("recipient_send_authorized") is not False
            or row.get("source_data_customer_distribution_authorized") is not False
            or row.get("qualified_lead") is not False
            or row.get("outbound_sent") is not False):
            raise ValueError("company_research_illegitimately_promoted_to_customer")
