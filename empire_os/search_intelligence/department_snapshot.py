"""On-demand cached, aggregate-only existing SEO department evidence.

Serves the existing Search Command Centre through the existing Search
Intelligence LOOPBACK API. No new daemon, DB, timer, credentials, or exports.
No customer or raw query data. Never serves stale cache after failed refresh.
"""
from __future__ import annotations

from copy import deepcopy
import threading
import time
from typing import Any, Callable

from .department_integration_review import (
    SCHEMA, run,
)

TTL_SECONDS = 900
_LOCK = threading.Lock()
_cached: dict[str, Any] | None = None
_cached_at = -1.0

class DepartmentSnapshotUnavailable(RuntimeError):
    pass


def read_department_snapshot(
    *, reader: Callable[[], dict[str, Any]] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return read-only aggregates with a 15min bounded per-process TTL.

    Fail closed if the reader or source is unavailable; no stale data is
    advertised as current. Threads cannot amplify simultaneous GSC reads.
    """
    global _cached, _cached_at
    tick = clock()
    if not _LOCK.acquire(timeout=1.0):
        raise DepartmentSnapshotUnavailable("DEPARTMENT_REVIEW_ALREADY_IN_PROGRESS")
    try:
        if (_cached is not None and tick >= _cached_at
                and tick - _cached_at < TTL_SECONDS):
            return deepcopy(_cached)
        try:
            report = (reader or run)()
        except Exception:
            _cached = None
            _cached_at = -1.0
            raise DepartmentSnapshotUnavailable("DEPARTMENT_SOURCE_EVIDENCE_UNAVAILABLE") from None
        # Explicit scalar-only allowlist: never pass raw query, customer,
        # secret, full URL or result row from future source implementations.
        if (not isinstance(report, dict)
                or report.get("schema_version") != SCHEMA
                or report.get("status") != "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN"
                or report.get("mode") != "OBSERVE"
                or report.get("database_writes") is not False
                or report.get("outbound_sent") is not False
                or report.get("buyer_enquiries_verified") is not False
                or report.get("realised_revenue_verified") is not False
                or report.get("search_rankings_verified") is not False):
            raise DepartmentSnapshotUnavailable("DEPARTMENT_SOURCE_SHAPE_UNVERIFIED")
        keep = (
            "schema_version", "status", "mode", "gsc_final_page_window",
            "gsc_returned_page_rows", "gsc_returned_page_sample_clicks",
            "gsc_returned_page_sample_impressions",
            "legacy_missing_404_count_in_returned_page_sample",
            "legacy_missing_404_impressions_in_returned_page_sample",
            "legacy_missing_404_clicks_in_returned_page_sample",
            "legacy_404_editorial_category_counts",
            "legacy_404_core_topic_editorial_review_count",
            "legacy_404_off_core_retain_404_count",
            "semantic_live_priority_pages_checked",
            "semantic_editorial_review_candidates",
            "semantic_owned_pages_commercial_route_verified",
            "search_fabric_cache_files_observed",
            "search_fabric_cache_fresh_candidates_24h",
            "search_fabric_cache_stale_candidates",
            "search_fabric_cache_invalid_envelopes",
            "search_rankings_verified",
            "external_ai_answer_citation_verified",
            "external_geo_mentions_verified",
            "buyer_enquiries_verified", "realised_revenue_verified",
            "growth_specialist_desks", "research_campaigns",
            "open_gates",
        )
        safe = {field: deepcopy(report[field]) for field in keep if field in report}
        if (not isinstance(safe.get("open_gates"), list)
                or len(safe["open_gates"]) > 20
                or any(not isinstance(s, str)
                       or len(s) > 96 or not s.isascii()
                       or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in s)
                       for s in safe["open_gates"])):
            raise DepartmentSnapshotUnavailable("DEPARTMENT_GATES_INVALID")
        counts = (
            "gsc_returned_page_rows", "gsc_returned_page_sample_clicks",
            "gsc_returned_page_sample_impressions",
            "legacy_missing_404_count_in_returned_page_sample",
            "legacy_missing_404_impressions_in_returned_page_sample",
            "legacy_missing_404_clicks_in_returned_page_sample",
            "legacy_404_core_topic_editorial_review_count",
            "legacy_404_off_core_retain_404_count",
            "semantic_live_priority_pages_checked",
            "semantic_editorial_review_candidates",
            "search_fabric_cache_files_observed",
            "search_fabric_cache_fresh_candidates_24h",
            "search_fabric_cache_stale_candidates",
            "search_fabric_cache_invalid_envelopes",
            "growth_specialist_desks", "research_campaigns",
        )
        if any(type(safe.get(key)) is not int or not 0 <= safe[key] <= 100_000 for key in counts):
            raise DepartmentSnapshotUnavailable("DEPARTMENT_COUNTS_INVALID")
        groups = safe.get("legacy_404_editorial_category_counts")
        allowed = {
            "BUYER_INTENT_EDITORIAL_REVIEW", "EMPIRE_PRODUCT_TOPIC_REVIEW",
            "ROOFING_RESEARCH_REVIEW", "OFF_CORE_RETAIN_404_PENDING_EVIDENCE",
        }
        if (not isinstance(groups, dict) or set(groups) != allowed
                or any(type(v) is not int or not 0 <= v <= 100_000 for v in groups.values())
                or sum(groups.values()) != safe["legacy_missing_404_count_in_returned_page_sample"]):
            raise DepartmentSnapshotUnavailable("DEPARTMENT_404_GROUPS_INVALID")
        window = safe.get("gsc_final_page_window")
        if (not isinstance(window, list) or len(window) != 2
                or any(not isinstance(s, str) or len(s) != 10 for s in window)):
            raise DepartmentSnapshotUnavailable("DEPARTMENT_WINDOW_INVALID")
        # No freshness inference from cached SERP data.
        safe["independent_google_rank_positions_verified"] = False
        safe["customer_identifiers_disclosed"] = False
        safe["publisher_mutation_authorized"] = False
        safe["execution_authority"] = "NONE"
        _cached = safe
        _cached_at = tick
        return deepcopy(safe)
    finally:
        _LOCK.release()


def _reset_snapshot_for_tests() -> None:
    global _cached, _cached_at
    with _LOCK:
        _cached = None
        _cached_at = -1.0
