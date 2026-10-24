"""Existing EmpireOS acquisition observer: official UK RFPs and requirements.

Use original public OCDS notices from Find a Tender / Contracts Finder, reuse
canonical product catalog and gated qualification. No second CRM, no sends,
no claims that a notice implies commercial permission or verified client fit.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import json
import re
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from empire_os.data_exchange_procurement_context import OGL_V3
from empire_os.acquisition_yc_first_party_sweep import _ready_products
from empire_os.acquisition_pool_qualification import qualify_pool
from empire_os.jev_client_pain_discovery import discover_client_pains

ROOTS = {
    "contracts_finder": "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
    "find_a_tender": "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages",
}
MAX_PAGES = 3
MAX_RELEASES = 100
SERVICE_TITLE = re.compile(
    r"\b(?:digital marketing|marketing services|media (?:planning|buying)|"
    r"GDPR data audit|investment land guide|technical seo|search engine optimi[sz]ation|"
    r"market research|competitor search|web analytics|search marketing|"
    r"SEO audit|advertising services)\b", re.I,
)
PAID_TRAFFIC = re.compile(
    r"\b(?:paid media|media buying|media planning|OOH|out of home advertising|"
    r"paid advertising|paid campaigns?|ad spend|PPC|Google Ads)\b", re.I,
)
SEO = re.compile(r"\b(?:SEO|search engine optimi[sz]ation|organic search|technical search audit)\b",re.I)
NO_FIT = re.compile(r"\b(?:GDPR data audit|investment land guide)\b",re.I)
FTS_NOTICE = re.compile(r"\d{6}-20\d{2}")
CF_NOTICE = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",re.I)


def _time(value: object) -> datetime | None:
    if not isinstance(value,str):
        return None
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        if d.tzinfo is None or d.utcoffset() is None:
            return None
        return d.astimezone(timezone.utc)
    except ValueError:
        return None


def _url_for_notice(source: str, release: Mapping, tender: Mapping) -> str | None:
    if source=="find_a_tender":
        notice=release.get("id")
        if isinstance(notice,str) and FTS_NOTICE.fullmatch(notice):
            return "https://www.find-tender.service.gov.uk/Notice/"+notice
        return None
    for document in tender.get("documents") or []:
        if not isinstance(document,Mapping) or document.get("documentType")!="tenderNotice":
            continue
        u=document.get("url")
        p=urlsplit(u if isinstance(u,str) else "")
        if p.scheme=="https" and p.hostname=="www.contractsfinder.service.gov.uk" and CF_NOTICE.fullmatch(p.path.removeprefix("/Notice/")) and p.path.startswith("/Notice/"):
            return u
    return None


def _public_gbp_estimate(tender: Mapping) -> str | None:
    """OCDS advertised estimate, never a final price or expected revenue."""
    value=tender.get("value")
    if not isinstance(value,Mapping) or value.get("currency")!="GBP":
        return None
    amount=value.get("amount")
    if type(amount) not in (int,float,str,Decimal):
        return None
    try:
        money=Decimal(str(amount))
        if (not money.is_finite() or not Decimal(0)<money<=Decimal("1000000000")
            or money.as_tuple().exponent < -2):
            return None
        return str(money.quantize(Decimal("0.01")))
    except (ValueError, InvalidOperation):
        return None


def review_official_releases(
    *,
    source: str,
    package: Mapping,
    catalog: Mapping,
    now: datetime,
) -> dict:
    if source not in ROOTS or now.tzinfo is None:
        raise ValueError("official source and timezone-aware clock required")
    if not isinstance(package,Mapping) or package.get("license")!=OGL_V3:
        raise ValueError("official OCDS licence not validated")
    publisher=package.get("publisher")
    if not isinstance(publisher,Mapping):
        raise ValueError("missing official publisher")
    # Both actual UK publication feeds identify Cabinet Office.
    if publisher.get("name")!="Cabinet Office":
        raise ValueError("unknown official OCDS publisher")
    releases=package.get("releases")
    if not isinstance(releases,list) or len(releases)>MAX_RELEASES:
        raise ValueError("bounded release package required")
    ready=_ready_products(catalog,now)
    results=[]
    for release in releases:
        if not isinstance(release,Mapping):
            continue
        tender=release.get("tender")
        if not isinstance(tender,Mapping) or tender.get("status")!="active":
            continue
        if not set(release.get("tag") or []).intersection({"tender","tenderAmendment"}):
            continue
        deadline=_time((tender.get("tenderPeriod") or {}).get("endDate"))
        stamp=_time(release.get("date"))
        if not stamp or stamp>now or not deadline or deadline<=now:
            continue
        title=str(tender.get("title") or "").strip()
        if not SERVICE_TITLE.search(title):
            continue
        buyer_names=[str(p.get("name") or "").strip() for p in release.get("parties",[])
                     if isinstance(p,Mapping) and "buyer" in (p.get("roles") or []) and p.get("name")]
        url=_url_for_notice(source,release,tender)
        if not buyer_names or not url:
            continue
        description=str(tender.get("description") or "")[:3600]
        combined=title+" "+description
        if PAID_TRAFFIC.search(combined):
            status="NO_PAID_TRAFFIC_POLICY_HOLD"
            product=None
        elif NO_FIT.search(title):
            status="CUSTOM_SCOPE_NO_VERIFIED_PRODUCT_FIT"
            product=None
        elif re.search(r"\bdigital marketing\b",title,re.I) and not SEO.search(title):
            # Unknown organic-vs-paid split; never assume compliant traffic.
            status="DIGITAL_MARKETING_PAID_SCOPE_NOT_EXCLUDED_HOLD"
            product=None
        elif SEO.search(title):
            product=("technical_search_audit" if re.search(r"\baudit\b",title,re.I)
                     else "search_growth_command")
            if product not in ready:
                product=None
            status="PRODUCT_HYPOTHESIS_REQUIRES_SCOPE_REVIEW" if product else "CATALOG_PRODUCT_NOT_READY"
        else:
            status="SERVICE_SCOPE_NEEDS_INDEPENDENT_FIT_REVIEW"
            product=None
        results.append({
            "source":source,
            "notice_ref":str(release.get("id") or "")[:110],
            "ocid":str(release.get("ocid") or "")[:110],
            "buyer_organisation":buyer_names[0][:220],
            "title":title[:220],
            "notice_url":url,
            "notice_release_at":stamp.isoformat(),
            "tender_closes_at":deadline.isoformat(),
            "published_estimated_value_gbp": _public_gbp_estimate(tender),
            "published_value_source": "OFFICIAL_OCDS_TENDER_VALUE_NOT_BINDING",
            "published_sme_suitable":(
                (tender.get("suitability") or {}).get("sme")
                if type((tender.get("suitability") or {}).get("sme")) is bool
                else None
            ),
            "published_contract_start_at": (
                _time((tender.get("contractPeriod") or {}).get("startDate"))
                or None
            ).isoformat() if _time((tender.get("contractPeriod") or {}).get("startDate")) else None,
            "published_contract_end_at": (
                _time((tender.get("contractPeriod") or {}).get("endDate"))
                or None
            ).isoformat() if _time((tender.get("contractPeriod") or {}).get("endDate")) else None,
            "request_status":"PUBLIC_TENDER_OPEN_AS_OF_OBSERVATION",
            "review_status":status,
            "candidate_product_code":product,
            "product_fit_verified":False,
            "external_purchasing_requirement_evidence":True,
            "buyer_interest_in_empire_ai_verified":False,
            "bid_eligibility_verified":False,
            "tender_documents_reviewed":False,
            "contact_permission_cleared":False,
            "suppression_checked":False,
            "outbound_authorized":False,
            "source_sha256":sha256(json.dumps(release,sort_keys=True,default=str).encode()).hexdigest(),
        })
    return {
        "schema_version":"empire.acquisition_official_tender_observer.v1",
        "mode":"OBSERVE",
        "source":source,
        "releases_inspected":len(releases),
        "explicit_current_service_requests":len(results),
        "records":results,
        "crm_writes":False,
        "outbound_authorized":False,
        "model_training_authorized":False,
        "verified_revenue":None,
    }


def combine_official_reviews(reviews: list[Mapping]) -> dict:
    if not isinstance(reviews,list) or len(reviews)>MAX_PAGES*len(ROOTS):
        raise ValueError("bounded source review pages required")
    by_key={}
    inspected=0
    for r in reviews:
        if r.get("schema_version")!="empire.acquisition_official_tender_observer.v1" or r.get("outbound_authorized") is not False:
            raise ValueError("non-executing official review contract required")
        inspected+=r["releases_inspected"]
        for item in r["records"]:
            key=(item["source"],item["ocid"])
            old=by_key.get(key)
            if old is None or item["notice_release_at"]>old["notice_release_at"]:
                by_key[key]=item
    records=sorted(by_key.values(),key=lambda r:r["notice_release_at"],reverse=True)
    # Read-only qualification adapter: public tender evidence does not assert
    # company decision maker, permitted direct marketing or bespoke delivery fit.
    canonical=qualify_pool(lane="vc_portfolio",records=[
        {"prospect_ref":sha256((r["source"]+"|"+r["ocid"]).encode()).hexdigest()[:24],
         "company":r["buyer_organisation"],
         "company_identity_verified":False,
         "dated_commercial_trigger_verified":False,
         "product_fit_verified":False,
         "trigger_independently_verified":False,
         "offer_approved":False,
         "suppression_checked":False,
         "contact_permission_cleared":False}
        for r in records])
    if canonical["qualified_for_review"] or canonical["contact_review_ready"]:
        raise ValueError("public tenders cannot automatically authorize buyer contacts")
    # Jev sees genuine published public requests, not simulated buyer messages.
    jev=discover_client_pains([
        {"source":"public_rfp","url":r["notice_url"],"title":r["title"],
         "text":r["title"],"observed_at":r["notice_release_at"],
         "niche":"public_procurement"}
        for r in records],now=datetime.now(timezone.utc))
    return {
        "schema_version":"empire.acquisition_official_procurement_review.v1",
        "mode":"OBSERVE",
        "releases_inspected":inspected,
        "open_service_requirements_identified":len(records),
        "policy_held_paid_media":sum(r["review_status"]=="NO_PAID_TRAFFIC_POLICY_HOLD" for r in records),
        "product_hypotheses":sum(r["candidate_product_code"] is not None for r in records),
        "canonical_qualification_contract":canonical["schema_version"],
        "canonical_qualified":canonical["qualified_for_review"],
        "jev_observations_submitted":jev["observations_submitted"],
        "records":records,
        "crm_writes":False,
        "outbound_authorized":False,
        "model_training_authorized":False,
        "verified_revenue":None,
    }


def _fetch_package(url: str) -> Mapping:
    parts=urlsplit(url)
    if (parts.scheme!="https" or parts.hostname not in {
            "www.find-tender.service.gov.uk","www.contractsfinder.service.gov.uk"}):
        raise ValueError("official open procurement source only")
    with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"EmpireOS-ReadOnly-Research/1.0"}),timeout=14) as response:
        raw=response.read(9_000_001)
    if len(raw)>9_000_000:
        raise ValueError("bounded official notice package required")
    obj=json.loads(raw)
    if not isinstance(obj,Mapping):
        raise ValueError("OCDS release package mapping required")
    return obj


def retrieve_bounded_notices(*, source:str, from_iso:str,to_iso:str, fetch:Callable[[str],Mapping]=_fetch_package):
    if source not in ROOTS:
        raise ValueError("unknown official procurement source")
    start=_time(from_iso)
    end=_time(to_iso)
    if not start or not end or not start<=end or (end-start).days>30:
        raise ValueError("bounded publication window required")
    criteria="updatedFrom" if source=="find_a_tender" else "publishedFrom"
    finish="updatedTo" if source=="find_a_tender" else "publishedTo"
    query=urlencode({criteria:start.strftime("%Y-%m-%dT%H:%M:%S"),
                      finish:end.strftime("%Y-%m-%dT%H:%M:%S"),
                      "stages":"tender","limit":100})
    requested=ROOTS[source]+"?"+query
    history=set()
    result=[]
    for _ in range(MAX_PAGES):
        if requested in history:
            raise ValueError("repeated official pagination URL")
        history.add(requested)
        current=_fetch_package(requested) if fetch is _fetch_package else fetch(requested)
        result.append(current)
        continuation=(current.get("links") or {}).get("next")
        if not continuation:
            break
        parts=urlsplit(continuation)
        expected_host=urlsplit(ROOTS[source]).hostname
        if parts.scheme!="https" or parts.hostname!=expected_host or not parts.path.endswith(urlsplit(ROOTS[source]).path):
            raise ValueError("off-origin pagination blocked")
        requested=continuation
    if continuation and len(result)==MAX_PAGES:
        raise ValueError("official source pagination exceeds safe review bound; incomplete scan")
    return result


def run_manual_official_intake(
    *,
    repo: Path,
    now: datetime | None=None,
    fetch: Callable[[str],Mapping]=_fetch_package,
    save: bool=True,
) -> dict:
    """Explicit founder-triggered OBSERVE run, never a background task.

    Reuses existing commercial-catalog readiness and Jev/canonical acquisition
    reviewer. Writes only private research evidence, never a CRM or send action.
    """
    current=(now or datetime.now(timezone.utc))
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("timezone-aware run required")
    current=current.astimezone(timezone.utc)
    catalog_path=repo/"runtime/commercial_catalog/latest.json"
    catalog=json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog,Mapping):
        raise ValueError("canonical catalog snapshot required")
    start=current-timedelta(days=21)
    reviews=[]
    page_counts={}
    for source in ("contracts_finder","find_a_tender"):
        packages=retrieve_bounded_notices(
            source=source,from_iso=start.isoformat(),to_iso=current.isoformat(),
            fetch=fetch)
        page_counts[source]=len(packages)
        reviews.extend(
            review_official_releases(source=source,package=p,catalog=catalog,now=current)
            for p in packages)
    report={
        **combine_official_reviews(reviews),
        "observed_at":current.isoformat(),
        "source_window_from":start.isoformat(),
        "source_window_to":current.isoformat(),
        "source_page_counts":page_counts,
        "commercial_offer_terms_authorized":False,
        "supplier_eligibility_verified":False,
        "external_bid_submitted":False,
        "verified_customer_inquiry":False,
        "rights_review": "OFFICIAL_OGL_METADATA_OBSERVED_REUSE_SCOPE_NOT_APPROVED",
    }
    if save:
        target=repo/"runtime/acquisition_research/official_procurement_requirements_latest.json"
        target.parent.mkdir(parents=True,exist_ok=True)
        import os
        temp=target.with_suffix(".json.tmp")
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(report,stream,indent=2)
        os.chmod(temp,0o600)
        os.replace(temp,target)
    return report


if __name__ == "__main__":
    report=run_manual_official_intake(repo=Path(__file__).resolve().parents[1])
    print(json.dumps({k:report[k] for k in (
        "observed_at","releases_inspected","open_service_requirements_identified",
        "policy_held_paid_media","product_hypotheses","canonical_qualified",
        "jev_observations_submitted","outbound_authorized"
    )},indent=2))
