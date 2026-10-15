"""Evidence-bound organic SEO baseline and recovery decisions for one owned site.

Only accepts first-party GSC query/page observations. This is measurement
research, not publication, commercial attribution or live site mutation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import math
from typing import Any, Mapping
from urllib.parse import urlsplit

MAX_OBSERVATIONS = 1000
MAX_EXCERPTS = 15


def _window(start: str, end: str) -> tuple[date, date]:
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError("invalid_gsc_observation_window") from None
    if a > b or (b - a).days >= 91 or b > date.today():
        raise ValueError("invalid_gsc_observation_window")
    return a, b


def _domain(site_url: Any) -> str:
    if not isinstance(site_url, str) or not site_url.startswith("sc-domain:"):
        raise ValueError("gsc_domain_property_required")
    domain = site_url.removeprefix("sc-domain:").strip().lower().rstrip(".")
    if domain != "empire-ai.co.uk":
        # This release is tied explicitly to our own verified property; no
        # free-text multi-tenant claims or user-provided customer domain control.
        raise ValueError("empire_property_binding_required")
    return domain


def _page(url: Any, domain: str) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url):
        raise ValueError("invalid_gsc_page_url")
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower().rstrip(".")
        if (
            p.scheme not in {"http", "https"}
            or host not in {domain, "www." + domain}
            or p.username is not None or p.password is not None
            or p.port is not None or p.fragment
        ):
            raise ValueError()
    except ValueError:
        raise ValueError("nonowned_or_invalid_gsc_page_url") from None
    return host, p.path or "/"


def _positive(value: Any, label: str, *, min_value: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid_gsc_{label}")
    result = float(value)
    if not math.isfinite(result) or result < min_value:
        raise ValueError(f"invalid_gsc_{label}")
    return result


def _read_batch(packet: Mapping[str, Any], *, domain: str) -> dict[str, Any]:
    if (
        not isinstance(packet, Mapping)
        or packet.get("available") is not True
        or packet.get("source") != "google_search_console"
        or packet.get("site_url") != "sc-domain:" + domain
    ):
        raise ValueError("unverified_or_cross_property_gsc_batch")
    rows = packet.get("items")
    if not isinstance(rows, list) or len(rows) > MAX_OBSERVATIONS:
        raise ValueError("gsc_observation_limit_exceeded")
    if packet.get("count") != len(rows):
        raise ValueError("gsc_observation_count_mismatch")
    if rows and len(rows) >= MAX_OBSERVATIONS:
        raise ValueError("truncated_gsc_data_requires_pagination")
    impressions = clicks = 0
    brand_impressions = legacy_aeo_impressions = other_impressions = 0
    unique_query = set()
    unique_urls = set()
    seen_pairs = set()
    top_pages = defaultdict(lambda: {"impressions": 0, "clicks": 0, "weighted_position": 0.0})
    brand_home_variants = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("malformed_gsc_observation")
        keys = row.get("keys")
        if not isinstance(keys, list) or len(keys) != 2:
            raise ValueError("gsc_query_page_dimensions_required")
        query, url = keys
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("invalid_gsc_query")
        host, path = _page(url, domain)
        pair = (query.casefold(), url)
        if pair in seen_pairs:
            raise ValueError("duplicate_gsc_query_page_row")
        seen_pairs.add(pair)
        imp = _positive(row.get("impressions"), "impressions")
        clk = _positive(row.get("clicks"), "clicks")
        pos = _positive(row.get("position"), "position", min_value=1.0)
        ctr = _positive(row.get("ctr"), "ctr")
        if (not imp.is_integer() or not clk.is_integer() or clk > imp or ctr > 1):
            raise ValueError("inconsistent_gsc_metrics")
        if (imp and abs(ctr - clk/imp) > 0.015) or (not imp and (clk or ctr)):
            raise ValueError("inconsistent_gsc_metrics")
        imp, clk = int(imp), int(clk)
        impressions += imp
        clicks += clk
        unique_query.add(query.casefold())
        unique_urls.add(url)
        top_pages[url]["impressions"] += imp
        top_pages[url]["clicks"] += clk
        top_pages[url]["weighted_position"] += pos * imp
        if "empire ai" in query.casefold() or "empire-ai" in query.casefold():
            brand_impressions += imp
        elif path.startswith("/aeo/"):
            legacy_aeo_impressions += imp
        else:
            other_impressions += imp
        if path == "/":
            brand_home_variants.add((urlsplit(url).scheme, host))
    pages = sorted(top_pages.items(), key=lambda r: (-r[1]["impressions"], r[0]))
    return {
        "returned_rows": len(rows),
        "impressions": impressions, "clicks": clicks,
        "ctr_percent": round(clicks / impressions * 100, 2) if impressions else None,
        "distinct_queries": len(unique_query), "distinct_page_urls": len(unique_urls),
        "brand_query_impressions": brand_impressions,
        "legacy_aeo_page_impressions": legacy_aeo_impressions,
        "other_query_impressions": other_impressions,
        "homepage_scheme_or_host_variations_observed": len(brand_home_variants) > 1,
        "top_pages": [
            {
                "url": url,
                "impressions": vals["impressions"],
                "clicks": vals["clicks"],
                "average_position": round(vals["weighted_position"]/vals["impressions"], 1)
                    if vals["impressions"] else None,
                "gsc_source_ref": "gsc:page:" +
                    hashlib.sha256((domain+"|"+url).encode()).hexdigest()[:18],
                "current_live_page_verified": False,
            } for url, vals in pages[:MAX_EXCERPTS]
        ],
    }



def _read_daily_sitewide(packet: Mapping[str, Any], *, domain: str,
                         start: date, end: date, detailed: Mapping[str, Any]) -> dict[str, Any]:
    """Date dimension is site-wide, unlike anonymised query/page rows."""
    if (
        not isinstance(packet, Mapping)
        or packet.get("available") is not True
        or packet.get("source") != "google_search_console"
        or packet.get("site_url") != "sc-domain:" + domain
        or packet.get("dimensions") != ["date"]
    ):
        raise ValueError("unverified_or_cross_property_gsc_daily_batch")
    rows = packet.get("items")
    if not isinstance(rows, list) or len(rows) > 92:
        raise ValueError("gsc_daily_observation_limit_exceeded")
    if packet.get("count") != len(rows):
        raise ValueError("gsc_daily_count_mismatch")
    total_imp = total_clk = 0
    dates = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_gsc_daily_row")
        keys = row.get("keys")
        if not isinstance(keys, list) or len(keys) != 1:
            raise ValueError("gsc_daily_date_dimension_required")
        try:
            day = date.fromisoformat(keys[0])
        except (TypeError, ValueError):
            raise ValueError("invalid_gsc_daily_date") from None
        if not start <= day <= end or day in dates:
            raise ValueError("gsc_daily_dates_out_of_window_or_duplicate")
        dates.add(day)
        impressions = _positive(row.get("impressions"), "daily_impressions")
        clicks = _positive(row.get("clicks"), "daily_clicks")
        ctr = _positive(row.get("ctr"), "daily_ctr")
        position = _positive(row.get("position"), "daily_position", min_value=0)
        if impressions > 0 and position < 1:
            raise ValueError("inconsistent_gsc_daily_position")
        if not impressions.is_integer() or not clicks.is_integer() or clicks > impressions or ctr > 1:
            raise ValueError("inconsistent_gsc_daily_metrics")
        if (impressions and abs(ctr-clicks/impressions) > 0.015) or (not impressions and (clicks or ctr)):
            raise ValueError("inconsistent_gsc_daily_metrics")
        total_imp += int(impressions)
        total_clk += int(clicks)
    if detailed["impressions"] > total_imp or detailed["clicks"] > total_clk:
        raise ValueError("gsc_query_rows_exceed_daily_sitewide_total")
    return {
        "impressions": total_imp,
        "clicks": total_clk,
        "ctr_percent": round(total_clk/total_imp*100, 2) if total_imp else None,
        "days_with_observations": len(dates),
        "last_observed_date": max(dates).isoformat() if dates else None,
        "report_window_complete_to_end_date": end in dates,
        "visible_query_page_impressions": detailed["impressions"],
        "visible_query_page_clicks": detailed["clicks"],
        "query_page_impression_coverage_percent": round(detailed["impressions"]/total_imp*100, 2) if total_imp else None,
        "visibility_gap_unattributed_impressions": total_imp-detailed["impressions"],
        "visibility_gap_unattributed_clicks": total_clk-detailed["clicks"],
        "hidden_queries_identified": False,
        "commercial_source_attribution_verified": False,
    }

def review_owned_organic_baseline(
    *, site_url: str, tenant_id: str, site_id: str,
    current: Mapping[str, Any], previous: Mapping[str, Any],
    current_daily: Mapping[str, Any] | None = None,
    previous_daily: Mapping[str, Any] | None = None,
    current_start: str = "", current_end: str = "",
    previous_start: str = "", previous_end: str = "",
) -> dict[str, Any]:
    """Return site-scoped review. Caller must authenticate actual owner separately."""
    domain = _domain(site_url)
    if tenant_id != "empire-ai" or site_id != "empire-ai.co.uk":
        raise ValueError("owned_tenant_site_binding_required")
    start, end = _window(current_start, current_end)
    before, until = _window(previous_start, previous_end)
    if (end-start).days != (until-before).days or until >= start:
        raise ValueError("not_comparable_disjoint_gsc_windows")
    now = _read_batch(current, domain=domain)
    prior = _read_batch(previous, domain=domain)
    if (current_daily is None) != (previous_daily is None):
        raise ValueError("both_sitewide_gsc_windows_required")
    sitewide_current = sitewide_previous = None
    if current_daily is not None and previous_daily is not None:
        sitewide_current = _read_daily_sitewide(current_daily, domain=domain,
                                               start=start, end=end, detailed=now)
        sitewide_previous = _read_daily_sitewide(previous_daily, domain=domain,
                                                start=before, end=until, detailed=prior)
    legacy = now["legacy_aeo_page_impressions"]
    tasks = [
        {
            "kind": "OWNED_GSC_MEASUREMENT_TRUTH",
            "status": "REVIEW_READY" if sitewide_current is not None else "EVIDENCE_HOLD",
            "source_attested_by_existing_gsc_api": True,
            "sitewide_traffic_truth_available": sitewide_current is not None,
            "independently_rechecked_raw_google_api": False,
            "observed_organic_clicks": now["clicks"],
            "verified_buyer_enquiries": None,
            "verified_sales": None,
            "revenue": None,
            "next_action": "confirm_gsc_source_scope_and_measure_canonical_commercial_events",
        },
        {
            "kind": "FIRST_PARTY_BUYER_PROBLEM_RESEARCH",
            "status": "EVIDENCE_HOLD",
            "blockers": ["no_verified_buying_queries_or_offer_fit_in_this_review"],
            "next_action": "research_one_actual_b2b_buyer_question_then_validate_canonical_offer_and_build_one_useful_asset",
        },
    ]
    if legacy:
        tasks.append({
            "kind": "LEGACY_AEO_PAGE_QUALITY_REVIEW",
            "status": "EVIDENCE_HOLD",
            "observed_impressions": legacy,
            "next_action": "inspect_aeo_page_value_sources_ownership_canonical_robots_and_policy_before_any_indexing_change",
            "automatic_noindex_or_deletion_allowed": False,
        })
    if now["homepage_scheme_or_host_variations_observed"]:
        tasks.append({
            "kind": "HOMEPAGE_CANONICAL_PARITY_REVIEW",
            "status": "EVIDENCE_HOLD",
            "next_action": "verify_www_http_https_redirects_with_GET_and_canonical_headers_before_modifying",
            "automatic_redirect_or_site_change_allowed": False,
        })
    return {
        "schema_version": "empire.search.owned_gsc_organic_review.v1",
        "tenant_id": tenant_id, "site_id": site_id, "gsc_property": site_url,
        "mode": "OBSERVE",
        "window": {"start": current_start, "end": current_end},
        "comparison_window": {"start": previous_start, "end": previous_end},
        "current": now, "previous": prior,
        "sitewide_current": sitewide_current,
        "sitewide_previous": sitewide_previous,
        "measurement_status": "GSC_DAILY_SITEWIDE_PLUS_QUERY_PAGE" if sitewide_current is not None
                              else "QUERY_PAGE_ONLY_SITEWIDE_UNKNOWN",
        "tasks": tasks,
        "confidence": "OBSERVED_GSC_QUERY_PAGE_ROWS_ONLY",
        "completeness_warning": (
            "GSC daily report metrics and query/page breakdown have different "
            "privacy and aggregation coverage; query/page rows may omit anonymised "
            "queries. No commercial attribution, source-to-customer or causal claim."
        ),
        "gsc_currently_available": True,
        "offer_eligibility_verified": False,
        "direct_publishing_allowed": False,
        "external_model_calls": 0,
        "payment_action": False,
        "outbound_allowed": False,
        "production_mutation": False,
    }
