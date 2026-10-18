"""Read-only page-dimension GSC review of legacy 404 URLs.

Consumes the existing first-party Search Console route and the existing
same-origin allowlisted HTTP probe. Never restores pages or suggests a
redirect without proof of an equivalent source and publisher permission.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import math
from typing import Any, Callable, Mapping


class LegacyPageReviewHeld(ValueError):
    pass


def _integer(value: Any) -> int:
    if type(value) is not int or value < 0 or value > 100_000_000:
        raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_METRIC")
    return value


def _number(value: Any, *, max_value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_METRIC")
    value = float(value)
    if not math.isfinite(value) or value < 0 or value > max_value:
        raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_METRIC")
    return value


def _category(path: str) -> tuple[str, str]:
    # Topic similarity gives review priority, not restoration authority.
    if path == "/aeo/accounting/TAM/":
        return ("BUYER_INTENT_EDITORIAL_REVIEW",
                "REVIEW_EXISTING_TAM_BUYER_READINESS_RESEARCH")
    if path.startswith("/aeo/empire/"):
        return ("EMPIRE_PRODUCT_TOPIC_REVIEW",
                "VERIFY_ORIGINAL_EMPIRE_PAGE_AND_EXISTING_PRODUCT_EQUIVALENCE")
    if (path.startswith("/aeo/roofing/")
            or path.startswith("/aeo/roof-repair/")
            or path.startswith("/aeo/roof-inspection/")):
        return ("ROOFING_RESEARCH_REVIEW",
                "VERIFY_INDUSTRY_RELEVANCE_AND_ORIGINAL_PUBLISHER_RIGHTS")
    return ("OFF_CORE_RETAIN_404_PENDING_EVIDENCE",
            "DO_NOT_REDIRECT_WITHOUT_GENUINE_EQUIVALENT_CONTENT")


def review_page_only_legacy_404(
    packet: Mapping[str, Any],
    *,
    start: date,
    end: date,
    today: date,
    safe_path: Callable[[Any], str | None],
    origin_status: Callable[[str], int],
) -> dict[str, Any]:
    """Produce a bounded evidence review; never join query/page totals."""
    if (not isinstance(start, date) or not isinstance(end, date)
            or not isinstance(today, date) or end < start
            or end >= today or (end-start).days > 30):
        raise LegacyPageReviewHeld("UNVERIFIED_GSC_WINDOW")
    if (not isinstance(packet, Mapping)
            or packet.get("source") != "google_search_console"
            or packet.get("site_url") != "sc-domain:empire-ai.co.uk"
            or packet.get("available") is not True
            or packet.get("data_state") != "final"
            or packet.get("dimensions") != ["page"]
            or packet.get("window") != [start.isoformat(), end.isoformat()]):
        raise LegacyPageReviewHeld("UNVERIFIED_PAGE_ONLY_GSC_SOURCE")
    rows = packet.get("items")
    if (not isinstance(rows, list) or len(rows) > 250
            or type(packet.get("count")) is not int
            or packet["count"] != len(rows)):
        raise LegacyPageReviewHeld("UNBOUNDED_GSC_PAGE_ROWS")
    by_path: dict[str, dict[str, Any]] = {}
    originals: set[str] = set()
    normalized_paths: set[str] = set()
    excluded = 0
    reported_page_impressions = 0
    reported_page_clicks = 0
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_ROW")
        keys = raw.get("keys")
        if (not isinstance(keys, list) or len(keys) != 1
                or not isinstance(keys[0], str) or not keys[0]
                or len(keys[0]) > 250 or keys[0] in originals):
            raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_KEY")
        originals.add(keys[0])
        impressions = _integer(raw.get("impressions"))
        clicks = _integer(raw.get("clicks"))
        ctr = _number(raw.get("ctr"), max_value=1)
        _number(raw.get("position"), max_value=100_000)
        if clicks > impressions:
            raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_METRIC")
        if (impressions == 0 and clicks != 0
                or (impressions > 0 and abs(ctr - clicks/impressions) > .02)):
            raise LegacyPageReviewHeld("UNTRUSTED_GSC_PAGE_CTR")
        reported_page_impressions += impressions
        reported_page_clicks += clicks
        path = safe_path(keys[0])
        if path is None:
            excluded += 1
            continue
        normalized_path = path.rstrip("/") or "/"
        if path in by_path or normalized_path in normalized_paths:
            # Trailing slash aliases cannot silently become two URL histories.
            # Do not rewrite their paths before HTTP probing either.
            raise LegacyPageReviewHeld("AMBIGUOUS_PAGE_ALIASES")
        normalized_paths.add(normalized_path)
        by_path[path] = {
            "path": path,
            "page_dimension_impressions": impressions,
            "page_dimension_clicks": clicks,
        }
    found = []
    for path in sorted(by_path):
        entry = by_path[path]
        status = origin_status(path)
        if type(status) is not int or status not in {200,301,302,307,308,404,410}:
            raise LegacyPageReviewHeld("UNVERIFIED_ORIGIN_HTTP_STATUS")
        category, action = _category(path)
        found.append({
            **entry,
            "origin_http_status": status,
            "review_category": category,
            "review_action": action if status in {404,410}
            else "PAGE_NOT_MISSING_INSPECT_LIVE_CONTENT",
            "sitemap_inclusion_checked": False,
            "publisher_rights_verified": False,
            "current_page_equivalence_verified": False,
            "indexed_status_verified": False,
            "qualified_buyer_verified": False,
            "revenue_verified": False,
            "restore_authorized": False,
            "redirect_authorized": False,
        })
    missing = [x for x in found if x["origin_http_status"] in {404, 410}]
    order = {
        "BUYER_INTENT_EDITORIAL_REVIEW": 0,
        "EMPIRE_PRODUCT_TOPIC_REVIEW": 1,
        "ROOFING_RESEARCH_REVIEW": 2,
        "OFF_CORE_RETAIN_404_PENDING_EVIDENCE": 3,
    }
    missing.sort(key=lambda x: (
        order[x["review_category"]], -x["page_dimension_impressions"], x["path"],
    ))
    by_category = Counter(x["review_category"] for x in missing)
    return {
        "schema_version": "empire.organic_search.gsc_page_legacy_404_review.v1",
        "status": "REVIEW_MISSING_LEGACY_URLS" if missing else "NO_MISSING_URLS_IN_PAGE_SAMPLE",
        "mode": "OBSERVE",
        "source": "google_search_console_page_dimension_final",
        "site_url": "sc-domain:empire-ai.co.uk",
        "window": [start.isoformat(), end.isoformat()],
        "returned_page_rows": len(rows),
        "returned_page_impressions": reported_page_impressions,
        "returned_page_clicks": reported_page_clicks,
        "returned_page_totals_are_sitewide": False,
        "query_page_rows_joined_or_added": False,
        "excluded_not_allowlisted_urls": excluded,
        "allowed_paths_probed": len(found),
        "missing_legacy_page_count": len(missing),
        "missing_legacy_page_impressions": sum(x["page_dimension_impressions"] for x in missing),
        "missing_legacy_page_clicks": sum(x["page_dimension_clicks"] for x in missing),
        "missing_review_categories": dict(sorted(by_category.items())),
        "missing_review_queue": missing,
        "redirect_authorized": False,
        "publication_authorized": False,
        "buyer_conversion_verified": False,
        "revenue_verified": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }
