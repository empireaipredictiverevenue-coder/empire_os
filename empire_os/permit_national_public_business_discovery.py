"""Bounded first-party business discovery for original EmpireOS Permit pipeline.

Exactly thirteen manually researched official company contact pages; no search
crawl, off-site following, SMTP, guessing, personal contact capture, permits
or external messaging. Only original expected role inbox is checked; no
arbitrary discovered emails are retained. Explicit result states + SHA custody.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from html import unescape
import re
from typing import Any,Callable,Mapping
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_volume_intake import (
    EXTERNAL_SCHEMA,validate_import_candidate,
)

SCHEMA="empire.permit_data.first_party_permit_business_discovery.v1"
USER_AGENT="EmpireOSPermitBusinessSourceObserver/1.0"
MAX_HTML=500000
MAX_ROBOTS=120000
TIMEOUT=6

# Independently researched official company-owned published-contact pages.
# Market/trade are research fit, NOT confirmed buyer need. Exactly one
# generic role email retained per business; bid/quote-purpose route flagged.
SEEDS=(
    ("chicago","Windward Roofing & Construction","commercial_roofing",
     "info@windwardroofing.com","https://windwardroofing.com/contact/","GENERAL_COMPANY"),
    ("chicago","Chicago Roofing Solutions","commercial_roofing",
     "info@chicagoroofingsolution.com","https://www.chicagoroofingsolution.com/contact/","GENERAL_COMPANY"),
    ("chicago","Chicago Promar Roofing","commercial_roofing",
     "info@chicagopromarroofing.com","https://chicagopromarroofing.com/contact-us/","GENERAL_COMPANY"),
    ("chicago","Cardoso Roofing","commercial_roofing",
     "info@cardosoroofing.com","https://cardosoroofing.com/contact/","ESTIMATING_SERVICE"),
    ("chicago","Buk Roofing","commercial_roofing",
     "info@bukroofing.com","https://bukroofing.com/contact/","GENERAL_COMPANY"),
    ("chicago","Chicago Flat Roof Company","commercial_roofing",
     "info@chicagoflatroofcompany.com","https://chicagoflatroofcompany.com/contact-us/","SERVICE_REQUESTS"),
    ("austin","Commercial Roofing of Austin","commercial_roofing",
     "info@commercialroofingofaustin.com","https://commercialroofingofaustin.com/contact/","ESTIMATING_SERVICE"),
    ("austin","JM Roofing & Siding","commercial_roofing",
     "info@jmroofingatx.com","https://www.jmroofingatx.com/commercial","GENERAL_COMPANY"),
    ("austin","Ace Roofing Texas","commercial_roofing",
     "info@aceroofingtexas.com","https://aceroofingtexas.com/contact-us/","ESTIMATING_SERVICE"),
    ("austin","Allies Roofing & Construction","commercial_roofing",
     "info@alliesrc.com","https://www.alliesrc.com/contact","SALES_SUPPORT"),
    ("austin","North Face Exterior","commercial_roofing",
     "info@northfaceexterior.com","https://northfaceexterior.com/","GENERAL_COMPANY"),
    ("austin","Austin Roofer","commercial_roofing",
     "info@austinroofer.com","https://austinroofer.com/contact","ESTIMATING_SERVICE"),
    ("philadelphia","Oliver Fire Protection & Security","fire_protection",
     "sales@oliverfps.com","https://oliverfps.com/contact/","QUOTE_SALES_INBOX"),
)

# Second first-party source wave. Exact current company-owned pages reviewed
# in October 2026. These are candidate public business addresses, not leads,
# permission to pitch, active jobs or deliverability evidence.
WAVE2_SEEDS=(
    ("seattle","Northwest Aire Services","commercial_hvac",
     "info@nwaireservices.com","https://nwaireservices.com/","GENERAL_COMPANY"),
    ("seattle","Steele Mechanical","commercial_hvac",
     "info@steelemech.com","https://www.steelemech.com/contact-us","GENERAL_COMPANY"),
    ("san_francisco","Phase One Fire","fire_protection",
     "info@phaseonefire.com","https://www.phaseonefire.com/contact-us","COMMERCIAL_PROJECT_INQUIRY"),
    ("austin","Fortified Fire Systems","fire_protection",
     "info@fortified-fire.com","https://fortified-fire.com/contact","QUOTE_AND_GENERAL"),
    ("austin","TRUE Construction","general_contractor",
     "info@trueconstructiontx.com","https://www.trueconstructiontx.com/contact","BID_REQUEST_ROUTE"),
    ("austin","J&F Construction","general_contractor",
     "info@jfbuild.com","https://jfbuild.com/contact","PROJECT_ENQUIRIES"),
    ("austin","CM Constructors","general_contractor",
     "info@cmconstructors.com","https://www.cmconstructors.com/","GENERAL_COMPANY"),
    ("austin","Gage Commercial Construction","general_contractor",
     "info@gagecc.com","https://gagecc.com/contact/","PROJECT_ENQUIRIES"),
    ("austin","KDK Group","general_contractor",
     "info@kdkgroupatx.com","https://kdkgroupatx.com/contact/","GENERAL_COMPANY"),
    ("austin","ATX Capital Construction","general_contractor",
     "info@atxcapitalconstruction.com","https://www.atxcapitalconstruction.com/contact-us","GENERAL_COMPANY"),
    ("austin","Concrete Contractors of Austin","construction",
     "info@concretecontractorsofaustin.com","https://www.concretecontractorsofaustin.com/contact","BID_REQUEST_ROUTE"),
    ("austin","The General Contractor Austin","general_contractor",
     "info@thegeneralcontractor.me","https://thegeneralcontractor.me/","PROJECT_ENQUIRIES"),
    ("chicago","Core Mechanical Inc","commercial_hvac",
     "info@coremechanicalinc.com","https://www.coremechanicalinc.com/contact","GENERAL_COMPANY"),
    ("chicago","Hayes Mechanical","commercial_hvac",
     "info@hayesmechanical.com","https://www.hayesmechanical.com/locations/chicago","GENERAL_COMPANY"),
    ("chicago","JAB Electrical Construction","electrical",
     "info@jabelec.com","https://jabelec.com/","QUOTE_REQUEST_ROUTE"),
    ("chicago","Hy-Power Electric","electrical",
     "info@hypowerelectric.com","https://hypowerelectric.com/","GENERAL_COMPANY"),
    ("chicago","MGD Electric","electrical",
     "info@mgdelectric.com","https://www.mgdelectric.com/contact/","GENERAL_COMPANY"),
    ("chicago","Rocha Electric","electrical",
     "info@rocha-electric.com","https://www.rocha-electric.com/contact","GENERAL_COMPANY"),
    ("chicago","CCR Electrical Contractors","electrical",
     "info@ccrelectric.com","https://www.ccrelectric.com/contact/","GENERAL_COMPANY"),
    ("chicago","Fitzgerald Electrical Contracting","electrical",
     "info@fitzec.com","https://www.fitzec.com/","SERVICE_REQUEST_ROUTE"),
    ("chicago","Powerplay Electric","electrical",
     "info@powerplay-electric.com","https://www.powerplay-electric.com/","GENERAL_COMPANY"),
    ("chicago","Expert Building Maintenance","general_contractor",
     "info@ebmchicago.com","https://ebmchicago.com/contact","PROJECT_QUOTE_ROUTE"),
    ("philadelphia","Precision Mechanical Services","commercial_hvac",
     "info@premechllc.com","https://www.premechllc.com/","GENERAL_COMPANY"),
    ("philadelphia","Polar Mechanical Services","commercial_hvac",
     "info@polarmechanical.com","https://www.polarmechanicalservices.com/contact","SERVICE_REQUEST_ROUTE"),
)
SOURCE_WAVE2_KEY="OWNER_RESEARCH_FIRST_PARTY_SECOND_WAVE"

ALLOWED={x[4] for x in SEEDS}|{x[4] for x in WAVE2_SEEDS}
ROBOT_URLS={f"https://{urlparse(u).netloc}/robots.txt" for u in ALLOWED}


class DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError("unapproved_site_redirect")


def fetch_fixed_page(url:str,max_bytes:int)->str:
    if (url not in ALLOWED|ROBOT_URLS or
        max_bytes not in (MAX_HTML,MAX_ROBOTS)):
        raise ValueError("unapproved_source_or_size_for_public_observation")
    req=Request(url,headers={"User-Agent":USER_AGENT,
                             "Accept":"text/html,text/plain"})
    try:
        with build_opener(DenyRedirect()).open(req,timeout=TIMEOUT) as response:
            if response.geturl()!=url or response.status!=200:
                raise ValueError("unapproved_source_response")
            content_type=str(response.headers.get("Content-Type","")).lower()
            if url in ROBOT_URLS:
                if not content_type.startswith(("text/plain","text/html")):
                    raise ValueError("robots_response_type_not_plaintext")
            elif not content_type.startswith(("text/html","text/plain")):
                raise ValueError("business_contact_not_html")
            payload=response.read(max_bytes+1)
    except HTTPError as exc:
        if url in ROBOT_URLS and exc.code==404:
            return ""  # missing robots does not automatically disallow access
        raise
    if len(payload)>max_bytes:
        raise ValueError("source_response_exceeded_explicit_size_limit")
    return payload.decode("utf-8",errors="replace")


def observe_one(url:str,robots_get:Callable[[str,int],str]|None=None,
                page_get:Callable[[str,int],str]|None=None)->tuple[str,str]:
    if url not in ALLOWED:
        raise ValueError("public_discovery_source_not_allowlisted")
    robots_url=f"https://{urlparse(url).netloc}/robots.txt"
    robots=(robots_get or fetch_fixed_page)(robots_url,MAX_ROBOTS)
    parser=RobotFileParser()
    parser.parse(robots.splitlines())
    if not parser.can_fetch(USER_AGENT,url):
        return "ROBOTS_RESTRICTED",""
    page=(page_get or fetch_fixed_page)(url,MAX_HTML)
    return "FETCHED",page


def build_discovery(*,at:datetime,
                    observe:Callable[[str],tuple[str,str]]|None=None,
                    source_wave:str|None=None)->dict:
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("discovery_requires_aware_clock")
    now=at.astimezone(timezone.utc)
    if source_wave not in (None,SOURCE_WAVE2_KEY):
        raise ValueError("unrecognised_original_permit_source_wave")
    seeds=WAVE2_SEEDS if source_wave==SOURCE_WAVE2_KEY else SEEDS
    client=observe or observe_one
    items=[];candidates=[]
    for market,company,sector,email,url,purpose in seeds:
        state="HTTP_UNAVAILABLE";error=None;matched=False
        try:
            result,page=client(url)
            if result not in {"FETCHED","ROBOTS_RESTRICTED"}:
                raise ValueError("unknown_observation_state")
            if result=="FETCHED":
                # Detect exact publicly displayed address in HTML/mailto.
                # Drop the page; never capture any other addresses.
                clean=unescape(page).casefold()
                matched=bool(re.search(r"(?<![\w.+-])"+re.escape(email.casefold())+
                                       r"(?![\w.-])",clean))
                state=("EXACT_FIRST_PARTY_EMAIL_OBSERVED" if matched
                       else "EXPECTED_EMAIL_NOT_ON_PAGE")
            else:
                state=result
        except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
            error=type(exc).__name__
        item={
            "market_id":market,"company":company,"sector":sector,
            "expected_public_business_email":email,"official_company_contact_url":url,
            "contact_route_purpose":purpose,
            "source_observation_state":state,
            "expected_email_exactly_present":matched,
            "observation_error_type":error,
            "source_checked_at_utc":now.isoformat(),
            "raw_html_or_other_emails_retained":False,
            "route_or_legal_permission_to_pitch":False,
            "recipient_suppression_cleared":False,
            "buyer_intent_verified":False,
            "outbound_authorized":False,
        }
        items.append(item)
        if matched:
            row={
                "schema_version":EXTERNAL_SCHEMA,
                "company":company,"market_id":market,"sector":sector,
                "official_company_url":url,"public_business_email":email,
                "business_email_evidence_url":url,
                "evidence_observed_at_utc":now.isoformat(),
            }
            validate_import_candidate(row,at=now)
            candidates.append(row)
    output={
        "schema_version":SCHEMA,
        "observed_at_utc":now.isoformat(),
        "allowlisted_company_count":len(seeds),
        "exact_first_party_email_match_count":len(candidates),
        "source_unavailable_or_no_exact_match_count":len(seeds)-len(candidates),
        "new_pages_or_domains_discovered_by_crawler":0,
        "personal_contact_addresses_harvested":0,
        "unverified_candidate_records_produced":len(candidates),
        "verified_deliverable_mailboxes":0,
        "qualified_buyers":0,
        "recipient_suppression_clearances":0,
        "sent_messages":0,
        "source_permit_row_queries":0,
        "empiredb_writes":0,"smart_crm_writes":0,
        "revenue_usd":"0.00","execution_authority":"none",
        "observations":items,
        "candidate_intake_json_rows":candidates,
    }
    # V1 source receipts must remain byte-for-byte valid. Only newly
    # observed wave2 records carry the explicit original-stack wave marker.
    if source_wave is not None:
        output["source_wave_key"]=source_wave
    output["discovery_sha256"]=digest(output)
    return output


def validate_discovery(report:Mapping[str,Any])->None:
    if not isinstance(report,Mapping):
        raise ValueError("unsafe_first_party_business_discovery")
    wave=report.get("source_wave_key")
    if wave not in (None,SOURCE_WAVE2_KEY):
        raise ValueError("unrecognised_original_permit_source_wave")
    seeds=WAVE2_SEEDS if wave==SOURCE_WAVE2_KEY else SEEDS
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("discovery_sha256")!=digest({
            k:v for k,v in report.items() if k!="discovery_sha256"})
        or report.get("allowlisted_company_count")!=len(seeds)
        or report.get("new_pages_or_domains_discovered_by_crawler")!=0
        or report.get("personal_contact_addresses_harvested")!=0
        or report.get("verified_deliverable_mailboxes")!=0
        or report.get("qualified_buyers")!=0
        or report.get("recipient_suppression_clearances")!=0
        or report.get("sent_messages")!=0
        or report.get("source_permit_row_queries")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_first_party_business_discovery")
    obs=report.get("observations")
    candidates=report.get("candidate_intake_json_rows")
    if (not isinstance(obs,list) or len(obs)!=len(seeds)
        or not isinstance(candidates,list)
        or report.get("exact_first_party_email_match_count")!=len(candidates)
        or report.get("unverified_candidate_records_produced")!=len(candidates)
        or report.get("source_unavailable_or_no_exact_match_count")!=len(seeds)-len(candidates)):
        raise ValueError("first_party_source_discovery_counts_invalid")
    allowed={u: (market,company,sector,email,purpose) for market,company,sector,email,u,purpose in seeds}
    matched=set()
    for x in obs:
        original=allowed.get(x.get("official_company_contact_url"))
        if (original is None
            or (x.get("market_id"),x.get("company"),x.get("sector"),
                x.get("expected_public_business_email"),x.get("contact_route_purpose"))!=original
            or x.get("source_observation_state") not in {
                "EXACT_FIRST_PARTY_EMAIL_OBSERVED",
                "EXPECTED_EMAIL_NOT_ON_PAGE","ROBOTS_RESTRICTED","HTTP_UNAVAILABLE"}
            or x.get("expected_email_exactly_present") is not (
                x.get("source_observation_state")=="EXACT_FIRST_PARTY_EMAIL_OBSERVED")
            or x.get("raw_html_or_other_emails_retained") is not False
            or x.get("route_or_legal_permission_to_pitch") is not False
            or x.get("recipient_suppression_cleared") is not False
            or x.get("buyer_intent_verified") is not False
            or x.get("outbound_authorized") is not False):
            raise ValueError("first_party_source_or_permission_forged")
        if x["expected_email_exactly_present"]:
            matched.add(x["official_company_contact_url"])
    recorded=set()
    now=datetime.fromisoformat(report["observed_at_utc"])
    for x in candidates:
        checked=validate_import_candidate(x,at=now)
        if (x["official_company_url"] not in matched
            or x["official_company_url"] in recorded
            or x["public_business_email"]!=allowed[x["official_company_url"]][3]):
            raise ValueError("unobserved_business_email_falsely_admitted")
        recorded.add(x["official_company_url"])
    if matched!=recorded:raise ValueError("public_business_source_receipt_missing_candidate")
