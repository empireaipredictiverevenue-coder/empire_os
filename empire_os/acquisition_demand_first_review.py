"""Demand-first research admission for the existing YC company universe.

Reuses the committed source pool, existing catalog readiness and acquisition
qualification contracts. Only company-owned, dated external-service requests
may advance to *evidence review*, never to outreach or buyer verification.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import re
from urllib.parse import urlsplit

from empire_os.acquisition_yc_first_party_sweep import _ready_products
from empire_os.acquisition_pool_qualification import qualify_pool

MAX_BATCH = 20
REQUEST_TERMS = (
    re.compile(r"\b(?:request(?:ing)? (?:for )?proposals?|rfp|rfq|invitation to tender)\b", re.I),
    re.compile(r"\b(?:seeking|looking for|invite|solicit(?:ing)?)\b.{0,100}\b(?:external|third.party|independent|agency|vendor|suppliers?|service providers?|consultants?)\b", re.I),
)
SERVICES = {
    "competitor_search_gap": re.compile(r"\b(?:competitor|competitive)\b.{0,65}\b(?:search|seo|organic|market)\b", re.I),
    "technical_search_audit": re.compile(r"\b(?:technical seo|seo audit|website technical audit)\b", re.I),
    "search_growth_command": re.compile(r"\b(?:seo|organic search|search growth|search engine optimization)\b", re.I),
}
HIRING = re.compile(r"\b(?:we are hiring|we're hiring|apply for this role|job description|employment|careers|salary|open positions|join our team|full.time position|job vacancy)\b", re.I)
SELLER = re.compile(r"\b(?:we offer|our services|we provide|buy our|book a demo|schedule a consultation)\b", re.I)


def _company_host(website: object) -> str:
    if not isinstance(website, str):
        return ""
    p = urlsplit(website.strip())
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        return ""
    host = p.hostname.casefold().removeprefix("www.")
    if not host or host in ("example.com", "localhost") or host.endswith((".local", ".test", ".invalid")):
        return ""
    return host


def demand_first_tasks(
    rows: Sequence[Mapping[str, str]],
    *, excluded_prospect_refs: set[str],
    limit: int = MAX_BATCH,
) -> dict:
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= 1000:
        raise ValueError("bounded committed company pool required")
    if not isinstance(excluded_prospect_refs, set) or not 1 <= limit <= MAX_BATCH:
        raise ValueError("bounded review and exclusion required")
    groups: dict[str, list[dict]] = defaultdict(list)
    seen = set()
    for row in rows:
        profile = row.get("yc_profile")
        if not isinstance(profile, str) or not profile.startswith("https://www.ycombinator.com/companies/"):
            raise ValueError("committed YC company source required")
        ref = sha256(profile.encode("utf-8")).hexdigest()[:24]
        if ref in seen:
            raise ValueError("duplicate YC source")
        seen.add(ref)
        if ref in excluded_prospect_refs:
            continue
        if (row.get("verification_status") != "public_directory_only"
                or row.get("buyer_intent") != "UNVERIFIED"
                or row.get("approval_state") != "RESEARCH_ONLY"):
            raise ValueError("unexpected upstream evidence promotion")
        host = _company_host(row.get("website"))
        if not host:
            continue
        segment = str(row.get("research_segment") or "unclassified")[:80]
        groups[segment].append({
            "prospect_ref": ref,
            "company": str(row.get("company") or "")[:120],
            "company_website": row["website"],
            "verified_official_domain": False,
            "source_yc_profile": profile,
            "niche": segment,
            "product_code": None,
            "research_goal": "Find original company-owned, dated request for external vendor services or procurement requirements",
            "status": "INDEPENDENT_PURCHASING_REQUIREMENT_RESEARCH",
            "external_buying_intent_verified": False,
            "outbound_authorized": False,
        })
    # Balanced round-robin over segments, not a disguised purchase-likelihood score.
    for group in groups.values():
        group.sort(key=lambda x: (x["company"].casefold(), x["prospect_ref"]))
    chosen: list[dict] = []
    while len(chosen) < limit and any(groups.values()):
        for niche in sorted(groups):
            if len(chosen) >= limit:
                break
            if groups[niche]:
                chosen.append(groups[niche].pop(0))
    return {
        "schema_version": "empire.acquisition_demand_first_tasks.v1",
        "mode": "OBSERVE",
        "source_pool_count": len(rows),
        "previously_reviewed_count": len(seen & excluded_prospect_refs),
        "new_company_research_count": len(chosen),
        "next_company_reviews": chosen,
        "buyer_request_verified": False,
        "crm_writes": False,
        "outbound_authorized": False,
        "model_training_authorized": False,
    }


def screen_original_requirement(
    *,
    company_website: str,
    source_url: str,
    published_at: str | None,
    excerpt: str,
    now: datetime,
    catalog: Mapping,
) -> dict:
    if now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    host = _company_host(company_website)
    p = urlsplit(source_url if isinstance(source_url, str) else "")
    # A search snippet, YC directory page, third-party post, or job board
    # cannot authenticate a company-owned external buying requirement.
    if not host or p.scheme != "https" or p.hostname not in {host, "www."+host} or p.username or p.password:
        return {"status":"UNVERIFIED_SOURCE_OWNERSHIP", "product_hypotheses":[],
                "buyer_request_verified":False, "outbound_authorized":False}
    if not isinstance(excerpt, str) or not 12 <= len(excerpt) <= 6000:
        raise ValueError("bounded original-source excerpt required")
    if HIRING.search(excerpt) or SELLER.search(excerpt):
        return {"status":"HIRING_OR_SELLER_CONTENT", "product_hypotheses":[],
                "buyer_request_verified":False, "outbound_authorized":False}
    try:
        posted = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        if posted.tzinfo is None or posted.utcoffset() is None:
            raise ValueError("source has no authoritative timezone")
        age = now.astimezone(timezone.utc) - posted.astimezone(timezone.utc)
        current = timedelta(0) <= age <= timedelta(days=60)
    except (ValueError, TypeError, AttributeError):
        current = False
    if not current:
        return {"status":"UNDATED_OR_STALE_SOURCE", "product_hypotheses":[],
                "buyer_request_verified":False, "outbound_authorized":False}
    if not any(pattern.search(excerpt) for pattern in REQUEST_TERMS):
        return {"status":"NO_EXPLICIT_EXTERNAL_PURCHASE_REQUEST", "product_hypotheses":[],
                "buyer_request_verified":False, "outbound_authorized":False}
    catalog_codes = _ready_products(catalog, now.astimezone(timezone.utc))
    hypotheses = sorted(code for code, pattern in SERVICES.items()
                        if code in catalog_codes and pattern.search(excerpt))
    return {
        "status": "ORIGINAL_BUYER_REQUEST_REQUIRES_OWNER_ATTESTATION" if hypotheses else "REQUEST_WITHOUT_MATCHED_PRODUCT",
        "source_url":source_url,
        "source_sha256": sha256(excerpt.encode()).hexdigest(),
        "published_at_claimed":published_at,
        "product_hypotheses":hypotheses,
        "source_identity_verified_by_canonical_owner": False,
        "decision_maker_authority_verified":False,
        "contact_permission_cleared":False,
        "buyer_request_verified":False,
        "outbound_authorized":False,
    }


def screen_candidates_against_canonical_qualification(
    *,
    candidates: Sequence[Mapping],
    catalog: Mapping,
    now: datetime,
) -> dict:
    if not isinstance(candidates, (list, tuple)) or len(candidates) > MAX_BATCH:
        raise ValueError("bounded sourced candidate evidence required")
    screening = []
    research = []
    seen = set()
    for candidate in candidates:
        ref = candidate.get("prospect_ref")
        if not isinstance(ref, str) or not ref or ref in seen:
            raise ValueError("unique canonical reference required")
        seen.add(ref)
        outcome = screen_original_requirement(
            company_website=candidate["company_website"],
            source_url=candidate["source_url"],
            published_at=candidate.get("published_at"),
            excerpt=candidate["original_excerpt"],
            now=now, catalog=catalog)
        screening.append({"prospect_ref":ref, **outcome})
        research.append({
            "prospect_ref":ref, "company":str(candidate.get("company") or ""),
            "company_identity_verified":False,
            "dated_commercial_trigger_verified":False,
            "product_fit_verified":False,
            "trigger_independently_verified":False,
            "offer_approved":False,
            "suppression_checked":False,
            "contact_permission_cleared":False,
        })
    canonical = qualify_pool(lane="vc_portfolio", records=research)
    if canonical["qualified_for_review"] or canonical["contact_review_ready"]:
        raise ValueError("untrusted source observations cannot establish buyer authority")
    return {
        "schema_version":"empire.acquisition_demand_first_canonical_review.v1",
        "mode":"OBSERVE",
        "screened":len(screening),
        "source_candidates_for_owner_attestation":sum(
            r["status"] == "ORIGINAL_BUYER_REQUEST_REQUIRES_OWNER_ATTESTATION"
            for r in screening),
        "canonical_qualification_contract":canonical["schema_version"],
        "canonical_qualified":canonical["qualified_for_review"],
        "records":screening,
        "crm_writes":False,"outbound_authorized":False,
        "model_training_authorized":False,"verified_revenue":None,
    }


def discover_original_requirement_candidates(
    *,
    research_queue: Mapping,
    provider_state: Mapping,
    lookup,
) -> dict:
    """Use the existing Search Fabric discovery contract, never a new crawler.

    Search snippets are not proof. Only candidate first-party links are
    returned for a later original-source rights/date/intent verification.
    """
    if (research_queue.get("schema_version") != "empire.acquisition_demand_first_tasks.v1"
        or research_queue.get("mode") != "OBSERVE"
        or research_queue.get("outbound_authorized") is not False):
        raise ValueError("canonical read-only acquisition research tasks required")
    tasks = research_queue.get("next_company_reviews")
    if not isinstance(tasks, list) or len(tasks) > MAX_BATCH:
        raise ValueError("bounded existing research task list required")
    if not isinstance(provider_state, Mapping):
        raise ValueError("original Search Fabric health required")
    # Stale last_state can say CIRCUIT_OPEN after cooldown expires.
    # Let the owning Search Fabric perform exactly one half-open probe.
    if provider_state.get("circuit_open") is not False:
        return {
            "schema_version":"empire.acquisition_demand_discovery.v1",
            "mode":"OBSERVE",
            "status":"SEARCH_PROVIDER_UNAVAILABLE_NOT_NO_BUYING_DEMAND",
            "search_queries_attempted":0,
            "original_source_candidates":[],
            "searched_companies":0,
            "unsearched_companies":len(tasks),
            "buyer_requests_verified":0,
            "crm_writes":False,
            "outbound_authorized":False,
            "model_training_authorized":False,
        }
    results = []
    searched = 0
    stopped_for_provider_failure = False
    stale_discovery = False
    for entry in tasks:
        if (not isinstance(entry, Mapping)
            or entry.get("status") != "INDEPENDENT_PURCHASING_REQUIREMENT_RESEARCH"
            or entry.get("outbound_authorized") is not False):
            raise ValueError("only unpromoted sourced YC tasks permitted")
        host = _company_host(entry.get("company_website"))
        if not host:
            continue
        # Short query avoids diluting the canonical lexical quality filter
        # with OR syntax. Hits still require original-source verification.
        query = f'site:{host} procurement marketing' 
        searched += 1
        try:
            response = lookup(query, num=5)
        except Exception:
            stopped_for_provider_failure = True
            break
        if not isinstance(response, Mapping):
            stopped_for_provider_failure = True
            break
        operational = response.get("search_operational_status")
        params = response.get("searchParameters")
        state = params.get("search_state") if isinstance(params, Mapping) else None
        if operational in {"CIRCUIT_OPEN", "DEGRADED"}:
            stopped_for_provider_failure = True
            break
        if operational == "DEGRADED_WITH_LAST_KNOWN_GOOD" or state == "STALE_RESULTS":
            stale_discovery = True
        elif operational not in {"RECOVERED", "HEALTHY"}:
            stopped_for_provider_failure = True
            break
        rows = response.get("organic")
        if not isinstance(rows, list):
            stopped_for_provider_failure = True
            break
        for row in rows[:5]:
            if not isinstance(row, Mapping):
                continue
            url = row.get("link") or row.get("url")
            p = urlsplit(url if isinstance(url, str) else "")
            if p.scheme != "https" or p.hostname not in (host, "www."+host):
                continue
            results.append({
                "prospect_ref": entry["prospect_ref"],
                "company":entry["company"],
                "source_url":url,
                "status":"SEARCH_DISCOVERY_ONLY_ORIGINAL_SOURCE_NOT_VERIFIED",
                "posting_date_verified":False,
                "search_source_stale": stale_discovery,
                "buyer_request_verified":False,
                "product_fit_verified":False,
                "outbound_authorized":False,
            })
        if stale_discovery:
            break
    return {
        "schema_version":"empire.acquisition_demand_discovery.v1",
        "mode":"OBSERVE",
        "status": ("SEARCH_PROVIDER_FAILED_REMAINDER_UNSEARCHED"
                   if stopped_for_provider_failure else
                   "STALE_DISCOVERY_ONLY_ORIGINAL_VERIFICATION_REQUIRED"
                   if stale_discovery else "DISCOVERY_RESULTS_NOT_PROOF"),
        "search_queries_attempted":searched,
        "original_source_candidates":results,
        "searched_companies":searched,
        "unsearched_companies":len(tasks)-searched,
        "provider_failed_during_batch":stopped_for_provider_failure,
        "stale_discovery_only":stale_discovery,
        "buyer_requests_verified":0,
        "crm_writes":False,
        "outbound_authorized":False,
        "model_training_authorized":False,
    }


def review_original_company_pages(
    *,
    research_queue: Mapping,
    probe_site,
) -> dict:
    """Reuse existing public-only Search Fabric site probes for demand evidence.

    No scraped contacts, unauthenticated identity promotion, or claim of
    purchasing authority may escape this research-only adapter.
    """
    if (not isinstance(research_queue, Mapping)
        or research_queue.get("schema_version") != "empire.acquisition_demand_first_tasks.v1"
        or research_queue.get("mode") != "OBSERVE"
        or research_queue.get("outbound_authorized") is not False):
        raise ValueError("canonical original YC research task contract required")
    tasks = research_queue.get("next_company_reviews")
    if not isinstance(tasks, list) or len(tasks) > MAX_BATCH:
        raise ValueError("bounded first-party tasks required")
    records=[]
    for item in tasks:
        if (not isinstance(item, Mapping) or
            item.get("status") != "INDEPENDENT_PURCHASING_REQUIREMENT_RESEARCH" or
            item.get("outbound_authorized") is not False):
            raise ValueError("untrusted/promoted source task")
        host=_company_host(item.get("company_website"))
        if not host:
            records.append({"prospect_ref":item.get("prospect_ref"),"company":item.get("company"),
                            "status":"UNVERIFIED_COMPANY_DOMAIN","pages_observed":0,
                            "original_source_candidates":[]})
            continue
        try:
            site=probe_site(item["company_website"],max_pages=3,
                request_timeout=4.0,time_budget_seconds=11.0,
                page_priority="commercial",public_only=True)
        except Exception:
            site={}
        final_host=_company_host(site.get("final_url")) if isinstance(site,Mapping) else ""
        if site.get("ok") is not True or final_host != host:
            records.append({"prospect_ref":item.get("prospect_ref"),
                            "company":item.get("company"),
                            "status":"SITE_UNAVAILABLE_OR_DOMAIN_CUSTODY_UNVERIFIED",
                            "pages_observed":0, "original_source_candidates":[]})
            continue
        pages=site.get("pages_checked")
        if not isinstance(pages,list):
            pages=[]
        candidates=[]
        count=0
        for page in pages[:3]:
            if not isinstance(page,Mapping) or _company_host(page.get("url"))!=host:
                continue
            count+=1
            body=page.get("visible_text")
            if not isinstance(body,str) or len(body)>12000:
                continue
            if HIRING.search(body[:6000]) or SELLER.search(body[:6000]):
                continue
            if not any(pattern.search(body[:6000]) for pattern in REQUEST_TERMS):
                continue
            candidates.append({
                "original_source_url":page.get("url"),
                "original_text_sha256":sha256(body.encode()).hexdigest(),
                "status":"ORIGINAL_PAGE_LANGUAGE_REQUIRES_CONTEXT_AND_DATE_REVIEW",
                "date_published_verified":False,
                "company_domain_authoritatively_verified":False,
                "buyer_request_verified":False,
                "contact_authorized":False,
            })
        records.append({
            "prospect_ref":item.get("prospect_ref"),
            "company":item.get("company"),
            "status":("PUBLIC_SITE_SAMPLE_OBSERVED" if count
                      else "SITE_REACHABLE_WITHOUT_REVIEWED_PAGES"),
            "pages_observed":count,
            "original_source_candidates":candidates,
        })
    return {
        "schema_version":"empire.acquisition_original_source_pages.v1",
        "mode":"OBSERVE",
        "company_pages_attempted":len(records),
        "company_sites_observed":sum(r["status"]=="PUBLIC_SITE_SAMPLE_OBSERVED" for r in records),
        "total_original_pages_observed":sum(r["pages_observed"] for r in records),
        "original_language_candidates_for_owner_review":sum(
            len(r["original_source_candidates"]) for r in records),
        "records":records,
        "date_published_verified":False,
        "buyers_verified":0,
        "crm_writes":False,
        "outbound_authorized":False,
        "model_training_authorized":False,
    }
