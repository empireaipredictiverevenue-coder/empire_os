"""First-party, chart-ready GSC daily observations; never simulated traffic.

Uses the EXISTING loopback Search Intelligence GSC date-dimension reader.
No Google credential here, no new search provider, DB, paid API, user PII,
synthetic daily zeros, or ranking claims. Unavailable is explicitly HELD.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA = "empire.search.gsc_daily_chart_evidence.v1"
SOURCE = "google_search_console_date_dimension"
SITE = "sc-domain:empire-ai.co.uk"
BASE = "http://127.0.0.1:8771/v1/search/search-console/daily"
MAX_DAYS = 31
MAX_BODY_BYTES = 65536


class GscDailyEvidenceHeld(ValueError):
    pass


def _strict_int(value: Any, upper: int = 1_000_000) -> int:
    if type(value) is not int or not 0 <= value <= upper:
        raise GscDailyEvidenceHeld("GSC_DAILY_COUNT_INVALID")
    return value


def validate_daily(raw: Mapping[str, Any], *, start: date, end: date) -> dict:
    """Strict source envelope -> additive safe day series. No zero fills."""
    if (not isinstance(raw, Mapping) or raw.get("available") is not True
            or raw.get("source") != "google_search_console"
            or raw.get("site_url") != SITE
            or raw.get("dimensions") != ["date"]):
        raise GscDailyEvidenceHeld("GSC_DAILY_SOURCE_UNVERIFIED")
    if (start > end or (end-start).days >= MAX_DAYS
            or end >= date.today()):
        raise GscDailyEvidenceHeld("GSC_DAILY_WINDOW_UNSAFE")
    rows = raw.get("items")
    count = raw.get("count")
    limit = raw.get("limit")
    if (not isinstance(rows, list) or type(count) is not int or count != len(rows)
            or type(limit) is not int or not 1 <= limit <= MAX_DAYS
            or count > limit):
        raise GscDailyEvidenceHeld("GSC_DAILY_ROW_LIMIT_UNVERIFIED")
    seen: set[date] = set()
    series = []
    for item in rows:
        if not isinstance(item, Mapping):
            raise GscDailyEvidenceHeld("GSC_DAILY_ROW_INVALID")
        keys = item.get("keys")
        if (not isinstance(keys,list) or len(keys)!=1
                or not isinstance(keys[0],str) or len(keys[0])!=10):
            raise GscDailyEvidenceHeld("GSC_DAILY_DATE_KEY_INVALID")
        try:
            day = date.fromisoformat(keys[0])
        except ValueError:
            raise GscDailyEvidenceHeld("GSC_DAILY_DATE_KEY_INVALID") from None
        if day in seen or day < start or day > end:
            raise GscDailyEvidenceHeld("GSC_DAILY_DATE_OUT_OF_RANGE_OR_DUPLICATE")
        seen.add(day)
        clicks = _strict_int(item.get("clicks"))
        impressions = _strict_int(item.get("impressions"))
        if clicks > impressions:
            raise GscDailyEvidenceHeld("GSC_DAILY_CLICKS_EXCEED_IMPRESSIONS")
        ctr = item.get("ctr")
        average_position = item.get("position")
        if (type(ctr) not in (float, int) or not math.isfinite(ctr)
                or ctr < 0 or ctr > 1 or (impressions and abs(ctr - clicks/impressions) > 0.02)
                or type(average_position) not in (float,int)
                or not math.isfinite(average_position)
                or average_position < 0 or average_position > 1000):
            raise GscDailyEvidenceHeld("GSC_DAILY_METRIC_INVALID")
        series.append({
            "date": day.isoformat(),
            "clicks": clicks,
            "impressions": impressions,
            "gsc_reported_ctr": round(ctr, 6),
            "gsc_reported_average_position": round(average_position, 3),
        })
    series.sort(key=lambda item: item["date"])
    missing = []
    current = start
    while current <= end:
        if current not in seen:
            missing.append(current.isoformat())
        current += timedelta(days=1)
    total_clicks = sum(x["clicks"] for x in series)
    total_impressions = sum(x["impressions"] for x in series)
    return {
        "schema_version": SCHEMA,
        "status": "DATE_DIMENSION_ROWS_OBSERVED",
        "source": SOURCE,
        "site_url": SITE,
        "mode": "READ_ONLY",
        "date_window": [start.isoformat(),end.isoformat()],
        "days_observed": len(series),
        "days_missing_unreported": missing,
        "rows": series,
        "reported_date_dimension_clicks": total_clicks,
        "reported_date_dimension_impressions": total_impressions,
        "query_page_or_page_only_totals_added": False,
        "missing_days_treated_as_zero": False,
        "gsc_average_position_is_independent_serp_rank": False,
        "independent_google_rank_positions_verified": False,
        "property_traffic_or_indexation_exhaustiveness_verified": False,
        "buyer_enquiries_verified": False,
        "realised_revenue_verified": False,
        "paid_api_calls": 0,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }


def held(*, start: date, end: date) -> dict:
    return {
        "schema_version": SCHEMA,
        "status": "HELD_GSC_DAILY_SOURCE_UNAVAILABLE",
        "source": SOURCE,
        "mode": "READ_ONLY",
        "date_window": [start.isoformat(),end.isoformat()],
        "days_observed": None,
        "days_missing_unreported": None,
        "rows": [],
        "reported_date_dimension_clicks": None,
        "reported_date_dimension_impressions": None,
        "missing_days_treated_as_zero": False,
        "gsc_average_position_is_independent_serp_rank": False,
        "independent_google_rank_positions_verified": False,
        "buyer_enquiries_verified": False,
        "realised_revenue_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }


def read_daily(*, start: date, end: date, transport=None) -> dict:
    """One allowlisted loopback GET, in the requested 31-day maximum window."""
    if start > end or (end-start).days >= MAX_DAYS or end >= date.today():
        raise GscDailyEvidenceHeld("GSC_DAILY_WINDOW_UNSAFE")
    params = urlencode({
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "limit": (end-start).days+1,
    })
    url = BASE + "?" + params
    if transport is None:
        def transport(target: str) -> bytes:
            req = Request(target,headers={"Accept":"application/json"},method="GET")
            with urlopen(req,timeout=16) as response:
                if response.status != 200:
                    raise GscDailyEvidenceHeld("GSC_DAILY_LOOPBACK_HTTP_UNAVAILABLE")
                data=response.read(MAX_BODY_BYTES+1)
                if len(data)>MAX_BODY_BYTES:
                    raise GscDailyEvidenceHeld("GSC_DAILY_LOOPBACK_BODY_TOO_LARGE")
                return data
    try:
        import json
        data = transport(url)
        if not isinstance(data, bytes) or len(data)>MAX_BODY_BYTES:
            raise GscDailyEvidenceHeld("GSC_DAILY_SOURCE_SIZE_INVALID")
        source = json.loads(data)
        return validate_daily(source,start=start,end=end)
    except (OSError, ValueError, TypeError, UnicodeError, TimeoutError):
        return held(start=start,end=end)


def validate_chart_contract(chart: Mapping[str, Any], *, window: list[str]) -> dict:
    """Validate even an injected chart envelope before founder API exposure."""
    if (not isinstance(chart, Mapping) or chart.get("schema_version") != SCHEMA
            or chart.get("source") != SOURCE
            or chart.get("mode") != "READ_ONLY"
            or chart.get("date_window") != window
            or chart.get("missing_days_treated_as_zero") is not False
            or chart.get("gsc_average_position_is_independent_serp_rank") is not False
            or chart.get("independent_google_rank_positions_verified") is not False
            or chart.get("buyer_enquiries_verified") is not False
            or chart.get("realised_revenue_verified") is not False
            or chart.get("database_writes") is not False
            or chart.get("outbound_sent") is not False
            or chart.get("execution_authority") != "NONE"):
        raise GscDailyEvidenceHeld("GSC_CHART_PROVENANCE_INVALID")
    try:
        start, end = [date.fromisoformat(day) for day in window]
    except (TypeError, ValueError):
        raise GscDailyEvidenceHeld("GSC_CHART_WINDOW_INVALID") from None
    if (end < start or (end-start).days >= MAX_DAYS
            or len(window) != 2):
        raise GscDailyEvidenceHeld("GSC_CHART_WINDOW_INVALID")
    status = chart.get("status")
    if status == "HELD_GSC_DAILY_SOURCE_UNAVAILABLE":
        if (chart.get("rows") != []
                or chart.get("days_observed") is not None
                or chart.get("reported_date_dimension_clicks") is not None
                or chart.get("reported_date_dimension_impressions") is not None):
            raise GscDailyEvidenceHeld("GSC_CHART_HELD_DATA_CONTRADICTION")
        return held(start=start,end=end)
    if status != "DATE_DIMENSION_ROWS_OBSERVED" or chart.get("site_url") != SITE:
        raise GscDailyEvidenceHeld("GSC_CHART_SOURCE_INVALID")
    rows = chart.get("rows")
    missing = chart.get("days_missing_unreported")
    if (not isinstance(rows,list) or len(rows) > MAX_DAYS
            or not isinstance(missing,list) or len(missing) > MAX_DAYS
            or _strict_int(chart.get("days_observed"),MAX_DAYS) != len(rows)):
        raise GscDailyEvidenceHeld("GSC_CHART_DAYS_INVALID")
    all_days = [(start+timedelta(days=i)).isoformat()
                for i in range((end-start).days+1)]
    if (len(rows)+len(missing) != len(all_days)
            or len(set(missing))!=len(missing)
            or any(type(day) is not str or day not in all_days for day in missing)):
        raise GscDailyEvidenceHeld("GSC_CHART_MISSING_DAYS_INVALID")
    safe_rows = []
    for row in rows:
        if not isinstance(row,Mapping) or set(row) != {
                "date", "clicks", "impressions",
                "gsc_reported_ctr", "gsc_reported_average_position"}:
            raise GscDailyEvidenceHeld("GSC_CHART_ROW_SHAPE_INVALID")
        day = row["date"]
        clicks = _strict_int(row["clicks"])
        impr = _strict_int(row["impressions"])
        ctr, pos = row["gsc_reported_ctr"], row["gsc_reported_average_position"]
        if (day not in all_days or day in missing or clicks>impr
                or type(ctr) not in (int,float) or not math.isfinite(ctr)
                or not 0 <= ctr <= 1
                or (impr and abs(ctr-clicks/impr)>0.021)
                or type(pos) not in (int,float) or not math.isfinite(pos)
                or not 0 <= pos <= 1000):
            raise GscDailyEvidenceHeld("GSC_CHART_ROW_CONTENT_INVALID")
        safe_rows.append(dict(row))
    observed_days = [r["date"] for r in safe_rows]
    if (observed_days != sorted(set(observed_days))
            or sorted(observed_days+missing) != all_days
            or _strict_int(chart.get("reported_date_dimension_clicks")) != sum(r["clicks"] for r in safe_rows)
            or _strict_int(chart.get("reported_date_dimension_impressions")) != sum(r["impressions"] for r in safe_rows)):
        raise GscDailyEvidenceHeld("GSC_CHART_AGGREGATE_INVALID")
    return {
        "schema_version": SCHEMA,
        "status": status,
        "source": SOURCE,
        "site_url": SITE,
        "mode": "READ_ONLY",
        "date_window": list(window),
        "days_observed": len(safe_rows),
        "days_missing_unreported": list(missing),
        "rows": safe_rows,
        "reported_date_dimension_clicks": sum(r["clicks"] for r in safe_rows),
        "reported_date_dimension_impressions": sum(r["impressions"] for r in safe_rows),
        "query_page_or_page_only_totals_added": False,
        "missing_days_treated_as_zero": False,
        "gsc_average_position_is_independent_serp_rank": False,
        "independent_google_rank_positions_verified": False,
        "property_traffic_or_indexation_exhaustiveness_verified": False,
        "buyer_enquiries_verified": False,
        "realised_revenue_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }
