"""Company-level, cited public contact research for ten EXISTING permit prospects.

This is a manually source-reviewed evidence overlay, not a crawler or
personal-email enrichment API. Six company-owned pages and four external
public source records; no invented patterns, SMTP probing, CRM writes,
suppression clearance, commercial permission or outbound authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from urllib.parse import urlparse
from typing import Any, Mapping

from empire_os.permit_multimarket_commercial_preflight import COMPANIES, PRIORITY, build_preflight, validate_preflight
from empire_os.permit_multimarket_registry import digest

SCHEMA = "empire.permit_data.national_company_email_evidence.v1"
# Each source is publicly displayed; third-party or old records must not be
# claimed as validated, current, consented or a genuine decision-maker.
CONTACT_OBSERVATIONS = (
    ("seattle", "AAA Fire Protection",
     "info@aaafire.com",
     "https://rentonrfa.com/wp-content/uploads/2024/10/10.01.24-Commercial-Kitchen-Suppression-System-Contractors.pdf",
     "PUBLIC_FIRE_AUTHORITY_LIST_HISTORICAL", "GENERAL_BUSINESS_LISTING",
     "HOLD_OUTDATED_OFFICIAL_LISTING_RECONFIRM"),
    ("seattle", "Columbia Fire",
     "services@columbiafire.net",
     "https://www.columbiafire.net/contact-us/",
     "FIRST_PARTY_COMPANY_PAGE", "SERVICE_TEAM",
     "HOLD_SERVICE_INBOX_NOT_VENDOR_PERMISSION"),
    ("san_francisco", "AR&B Mechanical",
     "info@arbmechanical.com",
     "https://www.arbmechanical.com/contact",
     "FIRST_PARTY_COMPANY_PAGE", "GENERAL_COMPANY",
     "HOLD_EXACT_CRM_SUPPRESSION_NOT_CHECKED"),
    ("san_francisco", "Cooper & Hawkins",
     "keri@cooperhawkins.com",
     "https://www.mylocalservices.com/Cooper%2Bandamp%2BHawkins%2BIncorporated-Berkeley-California-22945812.html",
     "THIRD_PARTY_BUSINESS_DIRECTORY", "NAMED_BUSINESS_CONTACT",
     "HOLD_THIRD_PARTY_UNCONFIRMED_AND_PERSON_LEVEL_SUPPRESSION"),
    ("austin", "Kidd Roofing",
     "info@kiddroof.com",
     "https://www.kiddroof.com/new-construction/",
     "FIRST_PARTY_COMPANY_PAGE", "NEW_CONSTRUCTION_BIDS",
     "HOLD_BID_INBOX_NOT_VENDOR_PERMISSION"),
    ("austin", "Texas Fifth Wall Roofing Systems",
     "hello@fifthwallroofing.com",
     "https://fifthwallroofing.com/privacy/",
     "FIRST_PARTY_COMPANY_PAGE", "GENERAL_PRIVACY_SITE_ENQUIRIES",
     "HOLD_CONTACT_PURPOSE_AND_CRM_SUPPRESSION"),
    ("chicago", "Funderburk Roofing",
     "ryan@funderburkroofing.com",
     "https://www.naperville.il.us/contentassets/5ae3d413e47048979e5157867e068ea6/2025-7/07-25-epl-contractor-listing.pdf",
     "PUBLIC_CITY_PERMIT_REPORT_HISTORICAL", "NAMED_PERMIT_CONTRACTOR",
     "HOLD_PERSON_LEVEL_SUPPRESSION_AND_CURRENT_ROLE"),
    ("chicago", "Stergo Roofing",
     "info@stergoroofing.com",
     "https://stergoroofing.com/contact-us/",
     "FIRST_PARTY_COMPANY_PAGE", "GENERAL_COMPANY",
     "HOLD_EXACT_CRM_SUPPRESSION_NOT_CHECKED"),
    ("philadelphia", "Independence Fire Sprinkler Company",
     "kevin@indpfire.com",
     "https://sprinklerfitters692.org/contractors.aspx",
     "THIRD_PARTY_TRADE_UNION_DIRECTORY", "NAMED_CONTRACTOR",
     "HOLD_NAMED_CONTACT_AND_PHILADELPHIA_DATA_RIGHTS"),
    ("philadelphia", "TriState HVAC",
     "Estimates@TriStateHVAC.com",
     "https://tristatehvac.com/contact/",
     "FIRST_PARTY_COMPANY_PAGE", "ESTIMATING_DEPARTMENT",
     "HOLD_ESTIMATING_MAILBOX_NOT_GENERAL_SALES"),
)
REQUIRED = ("FIRST_PARTY_COMPANY_PAGE", "PUBLIC_FIRE_AUTHORITY_LIST_HISTORICAL",
            "THIRD_PARTY_BUSINESS_DIRECTORY", "PUBLIC_CITY_PERMIT_REPORT_HISTORICAL",
            "THIRD_PARTY_TRADE_UNION_DIRECTORY")
_EMAIL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
KNOWN_EMAIL_DOMAINS = {
    "AAA Fire Protection": "aaafire.com",
    "Columbia Fire": "columbiafire.net",
    "AR&B Mechanical": "arbmechanical.com",
    "Cooper & Hawkins": "cooperhawkins.com",
    "Kidd Roofing": "kiddroof.com",
    "Texas Fifth Wall Roofing Systems": "fifthwallroofing.com",
    "Funderburk Roofing": "funderburkroofing.com",
    "Stergo Roofing": "stergoroofing.com",
    "Independence Fire Sprinkler Company": "indpfire.com",
    "TriState HVAC": "tristatehvac.com",
}


def build_research(*, at: datetime) -> dict:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("national_email_evidence_requires_aware_clock")
    current = build_preflight(at=at)
    validate_preflight(current)
    known = {(market, name): (trade,site) for market,name,trade,site in COMPANIES}
    if len(known) != 10 or len(CONTACT_OBSERVATIONS) != 10:
        raise ValueError("national_email_company_universe_changed")
    items = []
    for market,company,email,url,provenance,purpose,hold in CONTACT_OBSERVATIONS:
        if (market,company) not in known or provenance not in REQUIRED:
            raise ValueError("contact_not_in_original_permit_prospect_registry")
        urlhost = urlparse(url).hostname or ""
        if (not url.startswith("https://")
            or not _EMAIL.fullmatch(email)
            or email.lower().rsplit("@",1)[1] != KNOWN_EMAIL_DOMAINS[company]
            or not hold.startswith("HOLD_")
            or (provenance == "FIRST_PARTY_COMPANY_PAGE"
                and urlhost.removeprefix("www.") != KNOWN_EMAIL_DOMAINS[company])):
            raise ValueError("source_or_email_not_research_verified")
        items.append({
            "market_id":market,
            "company":company,
            "sector":known[(market,company)][0],
            "original_first_party_company_url":known[(market,company)][1],
            "published_email_address":email.lower(),
            "public_evidence_url":url,
            "evidence_source_type":provenance,
            "source_is_company_owned":provenance=="FIRST_PARTY_COMPANY_PAGE",
            "contact_route_context":purpose,
            "research_state":hold,
            "first_party_published_address":provenance=="FIRST_PARTY_COMPANY_PAGE",
            "current_inbox_deliverability_verified":False,
            "email_mx_verified":False,
            "person_current_role_verified":False,
            "recipient_has_opted_in":False,
            "recipient_suppression_checked":False,
            "domain_suppression_checked":False,
            "genuine_buyer_reply_observed":False,
            "source_rights_commercially_cleared":False,
            "outbound_authorized":False,
            "sample_delivery_authorized":False,
        })
    if { (r["market_id"],r["company"]) for r in items }!=set(known):
        raise ValueError("duplicate_or_missing_national_company_email")
    output={
        "schema_version":SCHEMA,
        "original_platform":"EMPIREOS_ORIGINAL_NATIONAL_PERMIT_INTELLIGENCE",
        "original_research_preflight_sha256":current["audit_sha256"],
        "researched_at_utc":at.astimezone(timezone.utc).isoformat(),
        "market_count":5,
        "research_company_count":10,
        "unique_public_email_candidates":len(set(row["published_email_address"] for row in items)),
        "company_owned_source_email_count":sum(row["first_party_published_address"] for row in items),
        "external_public_source_email_count":sum(not row["first_party_published_address"] for row in items),
        "inbox_deliverability_verified_count":0,
        "recipient_suppression_cleared_count":0,
        "lawfully_approved_outreach_recipients":0,
        "emails_sent":0,
        "site_http_requests_from_this_report":0,
        "email_smtp_probes":0,
        "canonical_empiredb_writes":0,
        "smart_crm_writes":0,
        "customer_buyer_signals_verified":0,
        "realised_revenue_usd":"0.00",
        "execution_authority":"none",
        "contacts":items,
    }
    output["email_research_sha256"]=digest(output)
    return output


def validate_research(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("email_research_sha256")!=digest({k:v for k,v in report.items() if k!="email_research_sha256"})
        or report.get("original_platform")!="EMPIREOS_ORIGINAL_NATIONAL_PERMIT_INTELLIGENCE"
        or report.get("market_count")!=5
        or report.get("research_company_count")!=10
        or report.get("unique_public_email_candidates")!=10
        or report.get("company_owned_source_email_count")!=6
        or report.get("external_public_source_email_count")!=4
        or report.get("inbox_deliverability_verified_count")!=0
        or report.get("recipient_suppression_cleared_count")!=0
        or report.get("lawfully_approved_outreach_recipients")!=0
        or report.get("emails_sent")!=0
        or report.get("site_http_requests_from_this_report")!=0
        or report.get("email_smtp_probes")!=0
        or report.get("canonical_empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("customer_buyer_signals_verified")!=0
        or report.get("realised_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("national_email_research_not_safe")
    items=report.get("contacts")
    expected={(m,n): (e.lower(),u,s,p,h) for m,n,e,u,s,p,h in CONTACT_OBSERVATIONS}
    if not isinstance(items,list) or len(items)!=10:
        raise ValueError("national_email_source_rows_incomplete")
    for row in items:
        ident=(row.get("market_id"),row.get("company"))
        if ident not in expected:
            raise ValueError("unknown_company_in_email_report")
        email,url,kind,purpose,hold=expected[ident]
        if (row.get("published_email_address")!=email
            or row.get("public_evidence_url")!=url
            or row.get("evidence_source_type")!=kind
            or row.get("contact_route_context")!=purpose
            or row.get("research_state")!=hold
            or row.get("first_party_published_address") is not (kind=="FIRST_PARTY_COMPANY_PAGE")
            or row.get("current_inbox_deliverability_verified") is not False
            or row.get("recipient_suppression_checked") is not False
            or row.get("domain_suppression_checked") is not False
            or row.get("genuine_buyer_reply_observed") is not False
            or row.get("source_rights_commercially_cleared") is not False
            or row.get("outbound_authorized") is not False):
            raise ValueError("unsafe_national_business_email_claim")
    if len({(r["market_id"],r["company"]) for r in items})!=10:
        raise ValueError("duplicate_business_email_claim")


def render_research(report:Mapping[str,Any])->str:
    validate_research(report)
    lines=[
        "# National Permit Intelligence — public company email research",
        "",
        "**Founder-private research, not a send-ready list. Original EmpireOS / Smart CRM.**",
        "",
        "| Market | Company | Published email | Evidence | Contact context |",
        "|---|---|---|---|---|",
    ]
    for r in report["contacts"]:
        lines.append(f'| {r["market_id"]} | {r["company"]} | {r["published_email_address"]} | '
                     f'{r["evidence_source_type"]} — {r["public_evidence_url"]} | {r["research_state"]} |')
    lines.extend([
        "", "**Important:** Six addresses appear on company-owned pages; four appear only in public external records.",
        "Company-owned estimating/service/bid addresses are not automatically suitable for unsolicited B2B vendor pitches.",
        "AAA's public authority listing is historical; Funderburk's municipal permit report is historical; named contacts need independent revalidation.",
        "No guesses, role-pattern inference, SMTP mailbox verification or scraped personal residential addresses.",
        "No original Smart CRM suppression, previous-intent or Gmail history clearance has been completed by this research.",
        "Buyer signal, legal contact permission, exact recipient approval, source-data distribution rights and founder send authority remain separate.",
        "", "**10 research candidates · 0 cleared recipients · 0 sent · $0 verified revenue.**", "",
    ])
    return "\n".join(lines)
