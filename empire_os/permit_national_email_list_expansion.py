"""Expansion of EXISTING Permit Intelligence buyer research, not a new CRM.

20 additional publicly listed first-party business addresses, plus canonical
10 national + 8 NYC researched companies. Source-link provenance, distinct
recipient purposes, duplicate suppression and value-first prioritisation.

NEVER treats an email as verified inbox, consent, lead response or authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse
import re

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_company_email_research import build_research, validate_research
from empire_os.permit_prospect_wave2 import SOURCE_ROWS as NYC_EXISTING_SOURCE_ROWS

SCHEMA="empire.permit_data.national_qualified_contact_research_expansion.v1"

# Each URL is the original business's own public page, verified in research.
# The four-tuple is (market, company, trade, general-or-purpose-specific
# email, evidence URL, email intent context).
# Email's domain may differ legitimately from website's primary domain; we
# keep the exact company-published address rather than guessing a pattern.
ADDITIONAL_FIRST_PARTY=(
    ("seattle","PSR Mechanical","commercial_hvac","info@psrmechanical.com",
     "https://www.psrmechanical.com/contact-us","GENERAL_COMPANY"),
    ("seattle","Sound Roof Services","commercial_roofing","info@soundroofservices.com",
     "https://soundroofservices.com/","GENERAL_COMPANY"),
    ("seattle","Premier Roofing & Waterproofing","commercial_roofing","info@premierroofingwa.com",
     "https://www.premierroofingandwaterproofing.com/contact-roofing-waterproofing-seattle/","GENERAL_COMPANY"),
    ("seattle","Washington Weather Shield","commercial_roofing","info@waweathershield.com",
     "https://waweathershield.com/contact/","GENERAL_COMPANY"),
    ("seattle","EDCA Roofing","commercial_roofing","info@edcaroofing.com",
     "https://edcaroofing.com/commercial/","GENERAL_COMPANY"),
    ("seattle","Alliant Roofing Company","commercial_roofing","info@alliantroofing.com",
     "https://www.alliantroofing.com/contact-alliant/","GENERAL_COMPANY"),
    ("san_francisco","Airco Mechanical","commercial_hvac","info@aircomech.com",
     "https://aircomech.com/contact/","GENERAL_COMPANY"),
    ("san_francisco","Bacon Plumbing","commercial_plumbing","info@baconplumbing.com",
     "https://www.baconplumbing.com/","GENERAL_COMPANY"),
    ("san_francisco","Gleaves Contractors","structural_steel","info@gleavescontractors.com",
     "https://www.gleavescontractors.com/","BIDS_AND_INFORMATION"),
    ("austin","QA Roofing","commercial_roofing","info@qacsi.com",
     "https://www.qaroofinginc.com/contact/","GENERAL_COMPANY"),
    ("austin","Fire King","fire_protection","info@firekingllc.com",
     "https://firekingllc.com/","GENERAL_COMPANY"),
    ("chicago","RMV Roofing","commercial_roofing","info@rmvroofing.com",
     "https://rmvroofing.com/contact-us","GENERAL_COMPANY"),
    ("chicago","Solaris Roofing","commercial_roofing","info@solarisroofing.com",
     "https://solarisroofing.com/contact/","GENERAL_COMPANY"),
    ("chicago","Benchmark Roofing","commercial_roofing","info@benchmarkroofingco.com",
     "https://benchmarkroofingco.com/contact-us","GENERAL_COMPANY"),
    ("chicago","Chicago Flat Roofs","commercial_roofing","info@chicagoflatroofs.com",
     "https://chicagoflatroofs.com/contact/","ROOF_ESTIMATING_AND_GENERAL"),
    ("chicago","Chicago Roofing & Tuckpointing Guru","commercial_roofing","info@chicagoroofingcompany.net",
     "https://www.chicagoroofingcompany.net/contact/","GENERAL_COMPANY"),
    ("philadelphia","Herman Goldner Co.","commercial_hvac","info@goldner.com",
     "https://goldner.com/contact","GENERAL_COMPANY"),
    ("philadelphia","MAS Construction Services","commercial_hvac","info@masconstructionservices.com",
     "https://www.masconstructionservices.com/contact-us","GENERAL_COMPANY"),
    ("philadelphia","RAMM Inc.","commercial_hvac","business@ramm-inc.com",
     "https://ramm-inc.com/contact/","GENERAL_BUSINESS"),
    ("philadelphia","Madsen Inc.","commercial_hvac","estimating@madseninc.com",
     "https://www.madseninc.com/commercial/installations/","BID_INVITATIONS_ONLY"),
)
MARKETS=("nyc","seattle","san_francisco","austin","chicago","philadelphia")
GENERIC_LOCALPARTS=frozenset({"info","hello","office","services","business"})
_EMAIL=re.compile(r"^[a-z0-9][a-z0-9._%+-]{0,63}@[a-z0-9.-]+\.[a-z]{2,20}$")


def _category(*, address:str, context:str, source:str)->str:
    local=address.split("@")[0]
    if context in ("BID_INVITATIONS_ONLY","BIDS_AND_INFORMATION","ESTIMATING_DEPARTMENT",
                   "NEW_CONSTRUCTION_BIDS","SERVICE_TEAM","ROOF_ESTIMATING_AND_GENERAL"):
        return "RESTRICTED_PURPOSE_RECONFIRM"
    if local in GENERIC_LOCALPARTS and source=="FIRST_PARTY_COMPANY_PAGE":
        return "FIRST_PARTY_GENERAL_ROLE_INBOX_REVIEW"
    if source=="FIRST_PARTY_COMPANY_PAGE":
        return "FIRST_PARTY_NONSTANDARD_ROUTE_REVIEW"
    return "THIRD_PARTY_OR_NAMED_RECONFIRM"


def build_expanded_list(*,at:datetime)->dict:
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("expanded_national_list_requires_aware_clock")
    legacy=build_research(at=at)
    validate_research(legacy)
    entries=[]
    for item in legacy["contacts"]:
        entries.append({
            "market_id":item["market_id"],"company":item["company"],
            "sector":item["sector"],"email":item["published_email_address"],
            "source_url":item["public_evidence_url"],
            "source_type":item["evidence_source_type"],
            "mailbox_context":item["contact_route_context"],
            "cohort":"ORIGINAL_NATIONAL_TEN",
            "original_contact_hold":item["research_state"],
        })
    for market,company,sector,address,source,context in ADDITIONAL_FIRST_PARTY:
        entries.append({
            "market_id":market,"company":company,"sector":sector,
            "email":address,"source_url":source,
            "source_type":"FIRST_PARTY_COMPANY_PAGE","mailbox_context":context,
            "cohort":"NEW_FIRST_PARTY_TWENTY",
            "original_contact_hold":"HOLD_SUPPRESSION_AND_ROUTE_AUTHORITY",
        })
    for item in NYC_EXISTING_SOURCE_ROWS:
        address=item.get("generic_inbox")
        entries.append({
            "market_id":"nyc",
            "company":item["company"],
            "sector":"fire_protection",
            "email":address.lower() if isinstance(address,str) else None,
            "source_url":item["contact"],
            "source_type":"EARLIER_FIRST_PARTY_NYC_RESEARCH",
            "mailbox_context":"GENERAL_COMPANY" if address else "CONTACT_FORM_ONLY",
            "cohort":"ORIGINAL_NYC_EIGHT",
            "original_contact_hold":"HOLD_NYC_EXACT_RECIPIENT_SUPPRESSION_AND_CONTACT_OWNER",
        })
    seen_company=set();seen_emails=set()
    for row in entries:
        name=row["company"].strip().casefold()
        ident=(row["market_id"],name)
        if ident in seen_company:raise ValueError("duplicate_national_prospect_company")
        seen_company.add(ident)
        if row["market_id"] not in MARKETS:raise ValueError("unknown_source_market")
        if (not row["source_url"].startswith("https://")
            or not (urlparse(row["source_url"]).hostname or "")
            or not row["original_contact_hold"].startswith("HOLD_")):
            raise ValueError("untrustworthy_prospect_source_url_or_hold")
        email=row["email"]
        if email is not None:
            if email!=email.lower() or not _EMAIL.fullmatch(email):
                raise ValueError("unsafe_national_business_contact_address")
            if email in seen_emails:raise ValueError("duplicate_national_email_across_companies")
            seen_emails.add(email)
        context=row["mailbox_context"]
        class_source=("FIRST_PARTY_COMPANY_PAGE" if row["source_type"]=="EARLIER_FIRST_PARTY_NYC_RESEARCH"
                      else row["source_type"])
        route=(_category(address=email,context=context,source=class_source)
               if email else "FORM_ONLY_NOT_AN_EMAIL_ADDRESS")
        row["route_quality"]=route
        row["recipient_business_role_confirmed"]=False
        row["email_deliverability_verified"]=False
        row["email_mx_verified"]=False
        row["recipient_level_suppression_cleared"]=False
        row["domain_level_suppression_cleared"]=False
        row["recipient_has_opted_in"]=False
        row["authentic_buyer_signal_verified"]=False
        row["licensed_permit_data_to_deliver"]=False
        row["vendor_outreach_authorized"]=False
        row["contact_sent"]=False
        row["ranking_signal_not_buyer_intent"]=(
            75 if route=="FIRST_PARTY_GENERAL_ROLE_INBOX_REVIEW" else
            35 if route=="FIRST_PARTY_NONSTANDARD_ROUTE_REVIEW" else
            20 if route=="RESTRICTED_PURPOSE_RECONFIRM" else 5
        )
    if (len(entries)!=38 or len(seen_company)!=38 or len(seen_emails)!=37
        or len(ADDITIONAL_FIRST_PARTY)!=20 or len(NYC_EXISTING_SOURCE_ROWS)!=8):
        raise ValueError("original_permit_list_research_universe_drift")
    entries.sort(key=lambda r:(-r["ranking_signal_not_buyer_intent"],r["market_id"],r["company"]))
    summary={
        "schema_version":SCHEMA,
        "as_of_utc":at.astimezone(timezone.utc).isoformat(),
        "original_national_email_research_sha256":legacy["email_research_sha256"],
        "original_nyc_company_count":8,
        "original_national_company_count":10,
        "additional_company_count":20,
        "total_research_companies":38,
        "public_email_candidates":37,
        "contact_form_only_company_count":1,
        "first_party_general_role_review_count":sum(
            r["route_quality"]=="FIRST_PARTY_GENERAL_ROLE_INBOX_REVIEW" for r in entries),
        "restricted_purpose_reconfirmation_count":sum(
            r["route_quality"]=="RESTRICTED_PURPOSE_RECONFIRM" for r in entries),
        "third_party_named_reconfirmation_count":sum(
            r["route_quality"]=="THIRD_PARTY_OR_NAMED_RECONFIRM" for r in entries),
        "six_market_coverage":list(MARKETS),
        "inbox_deliverability_verified":0,
        "recipient_suppression_cleared":0,
        "send_ready_recipients":0,
        "real_buyer_replies":0,
        "emails_sent":0,
        "new_http_crawls":0,
        "canonical_empiredb_writes":0,
        "smart_crm_writes":0,
        "revenue_verified_usd":"0.00",
        "execution_authority":"none",
        "companies":entries,
    }
    summary["expanded_list_sha256"]=digest(summary)
    return summary


def validate_expanded_list(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping) or report.get("schema_version")!=SCHEMA
        or report.get("expanded_list_sha256")!=digest({
            k:v for k,v in report.items() if k!="expanded_list_sha256"})
        or report.get("total_research_companies")!=38
        or report.get("public_email_candidates")!=37
        or report.get("additional_company_count")!=20
        or report.get("contact_form_only_company_count")!=1
        or report.get("inbox_deliverability_verified")!=0
        or report.get("recipient_suppression_cleared")!=0
        or report.get("send_ready_recipients")!=0
        or report.get("real_buyer_replies")!=0
        or report.get("emails_sent")!=0
        or report.get("new_http_crawls")!=0
        or report.get("canonical_empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("revenue_verified_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("untrusted_national_permit_lead_list")
    expected=build_expanded_list(at=datetime.fromisoformat(report["as_of_utc"]))
    if report!=expected:
        raise ValueError("national_permit_source_or_company_changed")


def render_expanded_list(report:Mapping[str,Any])->str:
    validate_expanded_list(report)
    lines=[
        "# EmpireOS National Permit Intelligence — sourced contractor contacts",
        "",
        "**Research-only. 38 distinct businesses, 37 public email candidates. 0 verified buyers, 0 send-ready contacts.**",
        "",
        "| Market | Company | Public business email | Route | First-party/source link |",
        "|---|---|---|---|---|",
    ]
    for row in report["companies"]:
        lines.append(f'| {row["market_id"]} | {row["company"]} | {row["email"] or "No email / form only"} | '
                     f'{row["route_quality"]} | {row["source_url"]} |')
    lines.extend([
        "", "## Qualification, not permission", "",
        "Ranking prioritises general business role inboxes over estimating/bid/service/named contacts.",
        "No mailbox verification, recipient/domain suppression, contact consent, buyer demand or commercial source data clearance is implied.",
        "Original one Smart CRM must reconcile historic sends, suppressions, STOPs, duplicate organisations and the send owner before any approach.",
        "First message: relevant first-party researched value/rapport; only offer a sample after buyer signal and source rights are cleared.",
        "", "**0 source permit-row GETs · 0 prospect emails sent · $0 realised revenue.**",
    ])
    return "\n".join(lines)+"\n"
