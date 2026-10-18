"""Minimal, self-contained first-party page-only Search Console review.

Production-safe measurement adapter: no semantic-search branch dependency, no
new credentials, no sales assertion and no background work.
"""
from __future__ import annotations

from hashlib import sha256
import math
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

PROPERTY = "sc-domain:empire-ai.co.uk"
DOMAIN = "empire-ai.co.uk"
PRIORITY_PAGE_ROUTES: tuple[tuple[str, str], ...] = (
    ("/industries/roofing", "roofing"),
    ("/industries/solar", "solar"),
    ("/industries/hvac", "hvac"),
    ("/predictive-revenue", "predictive-revenue-os"),
)


class GscPageEvidenceError(ValueError):
    """Page-only Search Console packet failed bounded provenance checks."""


def _owned_gsc_url(value: str) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme not in {"https", "http"}
        or host not in {DOMAIN, "www." + DOMAIN}
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or (port is not None and port != (443 if parsed.scheme == "https" else 80))
    ):
        return ""
    return "https://" + DOMAIN + (parsed.path.rstrip("/") or "/")


def _measure(value: Any, *, integer: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    if not math.isfinite(f) or f < 0 or (integer and not f.is_integer()):
        return None
    return f


def review_gsc_priority_pages(
    response: Mapping[str, Any], *, start_date: str, end_date: str,
) -> dict[str, Any]:
    if (
        not isinstance(response, Mapping)
        or response.get("source") != "google_search_console"
        or response.get("site_url") != PROPERTY
        or response.get("available") is not True
        or response.get("dimensions") != ["page"]
        or response.get("data_state") != "final"
    ):
        raise GscPageEvidenceError("verified final page-only GSC source required")
    if (
        not isinstance(start_date, str) or not isinstance(end_date, str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_date)
        or end_date < start_date
        or response.get("window") != [start_date, end_date]
    ):
        raise GscPageEvidenceError("GSC date window provenance mismatch")
    rows = response.get("items")
    if (
        not isinstance(rows, list) or len(rows) > 10_000
        or type(response.get("count")) is not int
        or response["count"] != len(rows)
    ):
        raise GscPageEvidenceError("bounded GSC page rows required")

    allowed = {"https://" + DOMAIN + p: (p, product) for p, product in PRIORITY_PAGE_ROUTES}
    priority = {url: [] for url in allowed}
    original_urls = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise GscPageEvidenceError("untrusted GSC page row")
        keys = row.get("keys")
        if (
            not isinstance(keys, (list, tuple)) or len(keys) != 1
            or not isinstance(keys[0], str)
        ):
            raise GscPageEvidenceError("exact page-only dimension required")
        original = keys[0]
        canonical = _owned_gsc_url(original)
        if not canonical or original in original_urls:
            raise GscPageEvidenceError("non-owned or duplicate page observation")
        original_urls.add(original)
        clicks = _measure(row.get("clicks"), integer=True)
        impressions = _measure(row.get("impressions"), integer=True)
        ctr = _measure(row.get("ctr"))
        position = _measure(row.get("position"))
        if (
            clicks is None or impressions is None or clicks > impressions
            or ctr is None or ctr > 1 or position is None
        ):
            raise GscPageEvidenceError("invalid GSC page measurements")
        if canonical not in priority:
            continue
        digest = sha256(
            f"{PROPERTY}|page|final|{start_date}|{end_date}|{original}|"
            f"{int(clicks)}|{int(impressions)}|{ctr}|{position}".encode()
        ).hexdigest()
        priority[canonical].append({
            "observed_page_url": original, "clicks": int(clicks),
            "impressions": int(impressions), "ctr": ctr,
            "reported_average_position": position,
            "evidence_ref": "gsc-page-row-sha256:" + digest,
            "source": "google_search_console_page_dimension",
        })
    findings = []
    for url, (_, product) in allowed.items():
        observed = priority[url]
        findings.append({
            "canonical_url": url,
            "product_key": product,
            "status": (
                "GSC_PAGE_PERFORMANCE_OBSERVED" if observed
                else "NO_PAGE_IN_RETURNED_GSC_ROWS"
            ),
            "observed_url_aliases": observed,
            "observed_alias_count": len(observed),
            "reported_impressions_total_across_aliases": None,
            "google_indexing_verified": False,
            "search_keyword_volume_verified": False,
            "qualified_buyer_verified": False,
            "realized_revenue_verified": False,
        })
    return {
        "schema_version": "empire.search.first_party_gsc_page_review.v1",
        "mode": "OBSERVE",
        "date_window": [start_date, end_date],
        "source": "google_search_console_page_dimension",
        "page_only_aggregation_not_query_page": True,
        "returned_page_rows": len(rows),
        "total_returned_property_traffic_claimed": None,
        "priority_page_findings": findings,
        "page_rows_may_exclude_unreported_data": True,
        "reported_search_rank_is_not_live_serp_position": True,
        "indexation_verified": False,
        "commercial_conversion_verified": False,
        "outbound_authorized": False,
        "publishing_authorized": False,
        "execution_authority": "none",
    }
