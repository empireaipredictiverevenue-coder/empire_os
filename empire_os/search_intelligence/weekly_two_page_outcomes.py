"""Read-only weekly GSC comparison for two approved Empire AI SEO pages.

Distinguishes a not-yet-final window, no returned page row, an observed zero,
and observed nonzero metrics. A missing page row is NEVER a measured zero.
Neither clicks, forecasts nor Jev recommendations constitute proven revenue.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Any, Callable, Mapping

from .first_party_gsc_page_review import (
    DOMAIN, PROPERTY, GscPageEvidenceError,
    _owned_gsc_url, review_gsc_priority_pages,
)

PUBLISHED_DATE = date(2026, 10, 22)
SITE_PAGES = (
    "https://empire-ai.co.uk/predictive-revenue",
    "https://empire-ai.co.uk/industries/roofing",
)
DAYS_PER_WINDOW = 7
FINALITY_LAG_DAYS = 4
SOURCE_ROUTE = "/search-console/pages"


class WeeklyGscHeld(ValueError):
    pass


def _window(start: date, end: date, *, state: str,
            returned_rows: int | None = None, items: list[Mapping[str, Any]] | None = None
            ) -> dict[str, Any]:
    by_page = []
    for url in SITE_PAGES:
        if state == "NOT_YET_FINAL":
            row = {"url": url, "status": "NOT_YET_REPORTED", "clicks": None,
                   "impressions": None, "ctr": None, "evidence_refs": []}
        elif state != "FINAL_PAGE_ROWS":
            row = {"url": url, "status": "SOURCE_UNAVAILABLE", "clicks": None,
                   "impressions": None, "ctr": None, "evidence_refs": []}
        else:
            assert items is not None
            matched = [r for r in items if _owned_gsc_url(r["keys"][0]) == url]
            if not matched:
                row = {"url": url, "status": "NO_PAGE_IN_RETURNED_GSC_ROWS",
                       "clicks": None, "impressions": None, "ctr": None,
                       "evidence_refs": []}
            else:
                clicks = sum(int(r["clicks"]) for r in matched)
                impressions = sum(int(r["impressions"]) for r in matched)
                if clicks > impressions:
                    raise WeeklyGscHeld("AGGREGATED_PAGE_CLICK_IMPRESSION_MISMATCH")
                status = "MEASURED_ZERO" if clicks == 0 and impressions == 0 else "MEASURED_PAGE_METRICS"
                refs = []
                for r in matched:
                    # Evidence refs represent actual original source-row content,
                    # rather than repeating a possibly stale aggregate.
                    import hashlib
                    data = f'{PROPERTY}|page|final|{start}|{end}|{r["keys"][0]}|{r["clicks"]}|{r["impressions"]}|{r["ctr"]}|{r["position"]}'
                    refs.append("gsc-page-row-sha256:" + hashlib.sha256(data.encode()).hexdigest())
                row = {
                    "url": url, "status": status,
                    "clicks": clicks, "impressions": impressions,
                    "ctr": round(clicks / impressions, 6) if impressions > 0 else None,
                    "evidence_refs": refs,
                }
        by_page.append(row)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "source_status": state,
        "returned_page_rows": returned_rows,
        "pages": by_page,
        "fully_after_publication": start > PUBLISHED_DATE,
        "includes_publication_day": start <= PUBLISHED_DATE <= end,
    }


def weekly_window_bounds(as_of: date) -> tuple[tuple[date, date], tuple[date, date]]:
    if not isinstance(as_of, date):
        raise WeeklyGscHeld("DATE_REQUIRED")
    last_day = as_of - timedelta(days=FINALITY_LAG_DAYS)
    current = (last_day - timedelta(days=6), last_day)
    previous = (current[0] - timedelta(days=7), current[0] - timedelta(days=1))
    return previous, current


def _validated_rows(payload: Mapping[str, Any], start: date, end: date
                    ) -> list[Mapping[str, Any]]:
    try:
        checked = review_gsc_priority_pages(
            payload, start_date=start.isoformat(), end_date=end.isoformat(),
        )
    except (GscPageEvidenceError, TypeError, KeyError, ValueError) as exc:
        raise WeeklyGscHeld("GSC_FINAL_PAGE_ROW_PROVENANCE_REJECTED") from exc
    if checked["page_only_aggregation_not_query_page"] is not True:
        raise WeeklyGscHeld("WRONG_SEARCH_DIMENSION")
    return payload["items"]


def build_weekly_report(
    *,
    as_of: date,
    get_json: Callable[..., Mapping[str, Any]],
    lag_days: int = FINALITY_LAG_DAYS,
) -> dict[str, Any]:
    if type(lag_days) is not int or lag_days < 3 or lag_days > 7:
        raise WeeklyGscHeld("FINALITY_LAG_OUTSIDE_SAFE_RANGE")
    if not isinstance(as_of, date):
        raise WeeklyGscHeld("DATE_REQUIRED")
    if as_of < PUBLISHED_DATE:
        raise WeeklyGscHeld("BEFORE_RELEASE_DATE")
    end = as_of - timedelta(days=lag_days)
    current = (end - timedelta(days=6), end)
    previous = (current[0] - timedelta(days=7), current[0] - timedelta(days=1))
    windows = []
    errors = []
    try:
        status = get_json("/search-console/status")
        status_ok = (
            status.get("available") is True
            and status.get("site_url") == PROPERTY
        )
    except (OSError, ValueError, TypeError, KeyError):
        status_ok = False
    for start, finish in (previous, current):
        # Even though normally lag-safe, explicitly distinguish a requested
        # nonfinal period so reports never display "0" for unfinalised data.
        if finish > as_of - timedelta(days=3):
            windows.append(_window(start, finish, state="NOT_YET_FINAL"))
            continue
        if not status_ok:
            windows.append(_window(start, finish, state="SOURCE_UNAVAILABLE"))
            errors.append("GSC_PROPERTY_NOT_VERIFIED_OR_ADAPTER_UNAVAILABLE")
            continue
        try:
            packet = get_json(
                SOURCE_ROUTE, params={
                    "start_date": start.isoformat(),
                    "end_date": finish.isoformat(), "limit": 1000,
                },
            )
            items = _validated_rows(packet, start, finish)
        except (WeeklyGscHeld, OSError, ValueError, TypeError, KeyError):
            windows.append(_window(start, finish, state="SOURCE_UNAVAILABLE"))
            errors.append("BOUNDED_FINAL_PAGE_REPORT_UNAVAILABLE_OR_INVALID")
            continue
        windows.append(_window(
            start, finish, state="FINAL_PAGE_ROWS",
            returned_rows=len(items), items=items,
        ))
    previous_window, current_window = windows
    comparable = (
        previous_window["fully_after_publication"]
        and current_window["fully_after_publication"]
        and previous_window["source_status"] == current_window["source_status"] == "FINAL_PAGE_ROWS"
    )
    comparisons = []
    for older, newer in zip(previous_window["pages"], current_window["pages"]):
        if older["url"] != newer["url"]:
            raise WeeklyGscHeld("COMPARISON_PAGE_ORDER_MISMATCH")
        observed_both = (
            comparable
            and older["status"] in {"MEASURED_ZERO", "MEASURED_PAGE_METRICS"}
            and newer["status"] in {"MEASURED_ZERO", "MEASURED_PAGE_METRICS"}
        )
        comparisons.append({
            "url": newer["url"],
            "comparison_status": "COMPARABLE_POST_PUBLICATION_ROWS" if observed_both
                else "NOT_COMPARABLE_OR_PAGE_ROW_MISSING",
            "click_change": newer["clicks"] - older["clicks"] if observed_both else None,
            "impression_change": newer["impressions"] - older["impressions"] if observed_both else None,
            "ctr_change_points": round((newer["ctr"] - older["ctr"]) * 100, 4)
                if observed_both and newer["ctr"] is not None and older["ctr"] is not None
                else None,
            "measured_traffic_lift_proven": False,
        })
    first_full_postrelease_end = PUBLISHED_DATE + timedelta(days=DAYS_PER_WINDOW)
    first_full_postrelease_final_from = first_full_postrelease_end + timedelta(days=FINALITY_LAG_DAYS)
    return {
        "schema_version": "empire.search.weekly_two_page_outcome_observer.v1",
        "first_complete_postrelease_window": [
            (PUBLISHED_DATE + timedelta(days=1)).isoformat(),
            first_full_postrelease_end.isoformat(),
        ],
        "first_postrelease_final_check_from": first_full_postrelease_final_from.isoformat(),
        "new_postrelease_page_data_status": (
            "POSTRELEASE_SEVEN_DAY_WINDOW_NOT_YET_FINAL"
            if as_of < first_full_postrelease_final_from
            else "POSTRELEASE_WINDOW_ELIGIBLE_FOR_GSC_REPORT"
        ),
        "status": "READ_ONLY_WEEKLY_REPORT",
        "as_of": as_of.isoformat(),
        "source_property": PROPERTY,
        "dimensions": ["page"],
        "data_state": "final_when_available",
        "reporting_lag_days": lag_days,
        "publication_date": PUBLISHED_DATE.isoformat(),
        "comparison_valid_after_release": comparable,
        "previous_window": previous_window,
        "current_window": current_window,
        "comparisons": comparisons,
        "source_errors": sorted(set(errors)),
        "google_indexing_verified": False,
        "qualified_buyer_enquiries_verified": False,
        "commercial_acceptance_verified": False,
        "realised_revenue_verified": False,
        "buyer_and_revenue_status": "NOT_CONNECTED_TO_VERIFIED_OUTCOME_RECEIPTS",
        "automatic_jev_model_calls": 0,
        "outbound_sent": False,
        "database_writes": False,
        "website_mutations": False,
        "execution_authority": "NONE",
    }
