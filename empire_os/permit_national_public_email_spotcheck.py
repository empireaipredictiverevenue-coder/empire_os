"""One bounded, read-only audit of 20 specified public company-owned pages.

No discovery crawling, no personal-email harvesting, no permit source pulls,
no CRM, no SMTP probing and no automatic scheduling. Never treats a published
website address as delivery, consent, permission or purchase intent.
"""
from __future__ import annotations

from datetime import datetime,timezone
from html import unescape
from typing import Any,Callable,Mapping
from urllib.parse import urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
import re

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_email_list_expansion import (
    ADDITIONAL_FIRST_PARTY,build_expanded_list,validate_expanded_list,
)

SCHEMA="empire.permit_data.national_public_business_email_source_spotcheck.v1"
USER_AGENT="EmpireOSPermitCompanyResearch/1.0 (public business evidence only)"
MAX_HTML_BYTES=900_000
MAX_ROBOTS_BYTES=150_000
MAX_SITES=20
TIMEOUT_SECONDS=6


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError("unapproved_company_site_redirect")


def _url_get(url:str,*,max_bytes:int)->str:
    # URLs are *only* selected from the fixed, reviewed company source list.
    # No arbitrary user-supplied host or path accepted by fetcher.
    allowed={row[4] for row in ADDITIONAL_FIRST_PARTY}
    robots={f'{urlparse(x).scheme}://{urlparse(x).netloc}/robots.txt' for x in allowed}
    if url not in allowed|robots:
        raise ValueError("url_not_in_fixed_first_party_allowlist")
    req=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"text/html,text/plain,*/*"})
    with build_opener(_NoRedirect()).open(req,timeout=TIMEOUT_SECONDS) as response:
        if response.geturl()!=url or response.status!=200:
            raise ValueError("source_http_not_exact_approved_url")
        mime=str(response.headers.get("Content-Type","")).lower()
        if url in robots:
            if not any(v in mime for v in ("text/plain","text/html","application/octet-stream")):
                raise ValueError("robots_mime_invalid")
        elif not any(v in mime for v in ("text/html","text/plain")):
            raise ValueError("website_mime_invalid")
        body=response.read(max_bytes+1)
        if len(body)>max_bytes:raise ValueError("website_response_exceeds_explicit_limit")
        return body.decode("utf-8",errors="replace")


def fetch_approved_company_page(url:str,*,robots_fetch:Callable[[str,int],str]|None=None,
                                page_fetch:Callable[[str,int],str]|None=None)->tuple[str,str]:
    if url not in {row[4] for row in ADDITIONAL_FIRST_PARTY}:
        raise ValueError("not_a_pre_reviewed_company_page")
    robot_url=f'{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt'
    fetch_robots=robots_fetch or (lambda u,limit:_url_get(u,max_bytes=limit))
    fetch_page=page_fetch or (lambda u,limit:_url_get(u,max_bytes=limit))
    robots=fetch_robots(robot_url,MAX_ROBOTS_BYTES)
    parser=RobotFileParser()
    parser.parse(robots.splitlines())
    if not parser.can_fetch(USER_AGENT,url):
        return "ROBOTS_DISALLOW_HOLD",""
    page=fetch_page(url,MAX_HTML_BYTES)
    return "PAGE_FETCHED",page


def build_public_email_spotcheck(*,at:datetime,fetch:Callable[[str],tuple[str,str]]|None=None)->dict:
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("website_spotcheck_clock_required")
    original=build_expanded_list(at=at)
    validate_expanded_list(original)
    candidate_by_company={(r["market_id"],r["company"]):r for r in original["companies"]}
    get=fetch or fetch_approved_company_page
    results=[]
    for market,company,sector,email,url,purpose in ADDITIONAL_FIRST_PARTY:
        state="FETCH_FAILED_HOLD";match=False
        error_type=None
        try:
            state,page=get(url)
            if state not in ("PAGE_FETCHED","ROBOTS_DISALLOW_HOLD"):
                raise ValueError("unexpected_spotcheck_fetcher_response")
            if state=="PAGE_FETCHED":
                # Literal appearance in publicly visible HTML or mailto.
                # We do not store arbitrary harvested addresses/page content.
                cleaned=unescape(page).lower()
                match=bool(re.search(r"(?<![\w.+-])"+re.escape(email.lower())+r"(?![\w.-])",cleaned))
                state="EXACT_PUBLIC_ADDRESS_OBSERVED" if match else "EMAIL_NOT_FOUND_IN_RESPONSE_HOLD"
        except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
            error_type=type(exc).__name__
            state="FETCH_FAILED_HOLD"
        results.append({
            "market_id":market,"company":company,
            "source_url":url,"candidate_email":email,
            "original_company_email_present_in_site_response":match,
            "source_observation_state":state,
            "error_type":error_type,
            "website_html_retained":False,
            "additional_discovered_addresses_retained":0,
            "site_person_identifiers_retained":0,
            "robots_permission_does_not_override_terms_or_outreach_consent":True,
            "inbox_deliverability_verified":False,
            "recipient_suppression_cleared":False,
            "outbound_authorized":False,
        })
    result={
        "schema_version":SCHEMA,
        "original_list_sha256":original["expanded_list_sha256"],
        "researched_at_utc":at.astimezone(timezone.utc).isoformat(),
        "fixed_company_source_count":20,
        "company_page_match_count":sum(r["original_company_email_present_in_site_response"] for r in results),
        "robots_or_website_hold_count":sum(r["source_observation_state"]!="EXACT_PUBLIC_ADDRESS_OBSERVED" for r in results),
        "new_prospect_companies_discovered":0,
        "new_addresses_harvested":0,
        "new_permit_row_requests":0,
        "sender_or_recipient_suppression_approved":0,
        "outbound_sent":0,
        "empiredb_writes":0,"smart_crm_writes":0,
        "verified_revenue_usd":"0.00",
        "execution_authority":"none",
        "results":results,
    }
    result["spotcheck_sha256"]=digest(result)
    return result


def validate_spotcheck(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("spotcheck_sha256")!=digest({
            k:v for k,v in report.items() if k!="spotcheck_sha256"})
        or report.get("fixed_company_source_count")!=20
        or report.get("new_prospect_companies_discovered")!=0
        or report.get("new_addresses_harvested")!=0
        or report.get("new_permit_row_requests")!=0
        or report.get("sender_or_recipient_suppression_approved")!=0
        or report.get("outbound_sent")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("verified_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_public_business_source_spotcheck")
    rows=report.get("results")
    if not isinstance(rows,list) or len(rows)!=20 or report.get("company_page_match_count")!=sum(
        r.get("original_company_email_present_in_site_response") is True for r in rows):
        raise ValueError("invalid_company_website_spotcheck_counts")
    if report.get("robots_or_website_hold_count")!=20-report["company_page_match_count"]:
        raise ValueError("spotcheck_missing_held_company_count")
    for row,original in zip(rows,ADDITIONAL_FIRST_PARTY):
        if (row.get("market_id")!=original[0]
            or row.get("company")!=original[1]
            or row.get("candidate_email")!=original[3]
            or row.get("source_url")!=original[4]
            or row.get("source_observation_state") not in {
                "FETCH_FAILED_HOLD","ROBOTS_DISALLOW_HOLD",
                "EMAIL_NOT_FOUND_IN_RESPONSE_HOLD","EXACT_PUBLIC_ADDRESS_OBSERVED"}
            or row.get("website_html_retained") is not False
            or row.get("additional_discovered_addresses_retained")!=0
            or row.get("site_person_identifiers_retained")!=0
            or row.get("inbox_deliverability_verified") is not False
            or row.get("recipient_suppression_cleared") is not False
            or row.get("outbound_authorized") is not False):
            raise ValueError("unsafe_company_site_evidence_or_contact_claim")
