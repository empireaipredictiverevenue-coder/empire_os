"""Original Search Intelligence: compare REAL Google indexed version to owned crawl.

Pure read-only evidence join; Google Search Console URL Inspection isn't a
generic Google indexing submitter and doesn't assert all-website coverage.
The module consumes the existing five-URL Search Console API and the existing
owned-site technical audit. No second crawler, external source or DB.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .owned_url_inspection import URLS, SITE

class IndexedTruthHeld(ValueError):
    pass

def review_owned_google_index_evidence(
    indexed_version: Mapping[str, Any],
    live_site_audit: Mapping[str, Any],
) -> dict[str, Any]:
    if (not isinstance(indexed_version, Mapping)
        or indexed_version.get("schema_version") != "empire.search.owned_gsc_index_inspection.v1"
        or indexed_version.get("status") != "INDEXED_VERSION_INSPECTION_RECORDED"
        or indexed_version.get("site") != SITE
        or indexed_version.get("mode") != "OBSERVE"
        or indexed_version.get("google_live_test_performed") is not False
        or indexed_version.get("google_indexing_request_sent") is not False
        or indexed_version.get("full_site_indexation_verified") is not False
        or indexed_version.get("production_database_writes") is not False
        or indexed_version.get("execution_authority") != "none"
        or type(indexed_version.get("count")) is not int
        or indexed_version["count"] != len(URLS)):
        raise IndexedTruthHeld("ORIGINAL_INDEXED_VERSION_RECEIPT_REQUIRED")
    try:
        timestamp = datetime.fromisoformat(indexed_version["observed_at"])
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timezone")
        now = datetime.now(timezone.utc)
        age_seconds = (now-timestamp.astimezone(timezone.utc)).total_seconds()
        if age_seconds < -300 or age_seconds > 7*86400:
            raise ValueError("stale_or_future")
    except (TypeError, KeyError, ValueError) as exc:
        raise IndexedTruthHeld("TIMELY_PROVIDER_RECEIPT_REQUIRED") from exc

    items=indexed_version.get("items")
    if (not isinstance(items,list)
        or len(items)!=len(URLS)
        or any(not isinstance(x,Mapping) for x in items)
        or [x.get("url") for x in items]!=list(URLS)
        or any(x.get("google_indexed_version_only") is not True
               or x.get("live_url_test_performed") is not False
               or x.get("index_status_reported") is not True
               for x in items)):
        raise IndexedTruthHeld("FIVE_EXACT_GOOGLE_RECEIPTS_REQUIRED")
    if (not isinstance(live_site_audit, Mapping)
        or live_site_audit.get("schema_version") != "empire.seo.index_health.v1"
        or live_site_audit.get("mode") != "OBSERVE"
        or live_site_audit.get("status") not in ("HEALTHY_SIGNALS","REVIEW","ACTION_REQUIRED")
        or live_site_audit.get("origin") != "https://empire-ai.co.uk"
        or live_site_audit.get("website_changed") is not False
        or live_site_audit.get("google_indexed_pages_verified") is not False):
        raise IndexedTruthHeld("ORIGINAL_LIVE_SITE_HEALTH_REQUIRED")
    links=live_site_audit.get("sitemap_incoming_anchor_counts")
    if not isinstance(links,Mapping):
        raise IndexedTruthHeld("REAL_SITEMAP_LINK_EVIDENCE_REQUIRED")

    findings=[]
    for entry in items:
        url=entry["url"]
        verdict=entry.get("verdict")
        coverage=entry.get("coverageState")
        robots=entry.get("robotsTxtState")
        fetch=entry.get("pageFetchState")
        index=entry.get("indexingState")
        google_canonical=entry.get("googleCanonical")
        in_sitemap = url in links
        link_count = links.get(url) if in_sitemap else None
        if in_sitemap and (type(link_count) is not int or link_count < 0):
            raise IndexedTruthHeld("INCONSISTENT_SITE_LINK_GRAPH")
        if (verdict == "PASS" and coverage == "Submitted and indexed"
            and google_canonical == url and robots == "ALLOWED"
            and fetch == "SUCCESSFUL" and index == "INDEXING_ALLOWED"):
            state="GOOGLE_INDEXED_VERSION_VERIFIED"
            priority="P3_GSC_OBSERVE"
            action="MONITOR_SEARCH_PERFORMANCE_AND_FUTURE_CRAWLS"
        elif (verdict == "NEUTRAL" and coverage == "URL is unknown to Google"):
            state="GOOGLE_HAS_NO_URL_RECORD"
            priority="P1_DISCOVERY_REVIEW"
            action=("REVIEW_ORIGINAL_PAGE_VALUE_AND_INDEX_INSPECTION_MANUAL_REQUEST_IF_WARRANTED"
                    if in_sitemap and link_count > 0 else
                    "REPAIR_OWNED_SITEMAP_AND_CONTEXTUAL_LINK_DISCOVERY_FIRST")
        else:
            state="GOOGLE_INDEX_STATUS_NEEDS_REVIEW"
            priority="P1_INDEXING_EVIDENCE_REVIEW"
            action="REVIEW_EXACT_GOOGLE_CRAWL_INDEX_AND_CANONICAL_EVIDENCE"
        findings.append({
            "url":url,"state":state,"priority":priority,
            "next_owner_action":action,
            "sitemap_listed_by_live_audit":in_sitemap,
            "incoming_sitemap_page_links":link_count,
            "google_coverageState":coverage,
            "google_verdict":verdict,
            "google_lastCrawlTime":entry.get("lastCrawlTime"),
            "google_canonical_matches_exact_url":google_canonical==url if google_canonical is not None else None,
            "external_search_rank_attested":False,
            "ai_answer_citation_attested":False,
            "lead_or_sale_attested":False,
        })

    return {
        "schema_version":"empire.search.google_indexed_truth_review.v1",
        "source":"ORIGINAL_FIVE_URL_GSC_INSPECTION_PLUS_LIVE_CRAWL",
        "mode":"OBSERVE",
        "provider_receipt_observed_at":indexed_version["observed_at"],
        "provider_receipt_age_seconds":int(age_seconds),
        "site_audit_status":live_site_audit.get("status"),
        "site_audit_critical_issue_count":live_site_audit.get("critical_issue_count"),
        "scope_google_urls_checked":len(findings),
        "indexed_version_exact_verified":sum(r["state"]=="GOOGLE_INDEXED_VERSION_VERIFIED" for r in findings),
        "google_url_unknown_count":sum(r["state"]=="GOOGLE_HAS_NO_URL_RECORD" for r in findings),
        "other_indexing_review_count":sum(r["state"]=="GOOGLE_INDEX_STATUS_NEEDS_REVIEW" for r in findings),
        "findings":findings,
        "full_site_indexation_verified":False,
        "ranking_uplift_verified":False,
        "site_crawl_equals_google_indexation":False,
        "automatic_index_submissions_authorized":False,
        "external_outbound_sent":False,
        "database_writes":False,
        "website_changed":False,
        "execution_authority":"none",
    }
