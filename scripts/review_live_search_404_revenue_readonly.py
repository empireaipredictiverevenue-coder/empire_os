#!/usr/bin/env python3
"""Read-only Empire SEO triage of GSC query/page URLs that are now HTTP 404.

Reuses the EXISTING Search Intelligence service. Queries only the local GSC
read endpoints and the first-party loopback gateway, never the public web.
Never publishes, redirects, edits a sitemap, copies search terms, creates
enquiries, provisions infrastructure or starts a recurring monitor.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "empire.organic_search.legacy_404_revenue_triage.v1"
SITE = "sc-domain:empire-ai.co.uk"
SEARCH = "http://127.0.0.1:8771/v1/search"
ORIGIN = "http://127.0.0.1"
HOST = "empire-ai.co.uk"
MAX_GSC_ROWS = 250
MAX_RESPONSE = 300_000
MAX_DAYS = 31
# All remaining paths are omitted from the target audit rather than
# interpolated into HTTP requests. Prevent SSRF, private path guessing,
# arbitrary third-party redirects and untrusted query/PII disclosure.
PATH_PATTERN = re.compile(
    r"^/(?:aeo(?:/[A-Za-z0-9_-]+){1,3}|commercial|buy|predictive-revenue)/?$"
)
TARGET_COMMERCIAL = ("/commercial", "/buy", "/predictive-revenue")
EXACT_KNOWN_REVENUE_TOPIC = {"/aeo/accounting/TAM/": "BUYER_INTENT_TAM_RESEARCH"}
QUERY_PRIVATE = True


class ReviewHeld(RuntimeError):
    pass


class RefuseRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get(path: str, *, search: bool) -> tuple[int, bytes]:
    if search:
        allowed = ("/search-console/status", "/search-console/daily",
                   "/search-console/observations")
        base, suffix = path.split("?", 1) if "?" in path else (path, "")
        if base not in allowed:
            raise ReviewHeld("UNAPPROVED_SEARCH_API")
        if suffix and (len(suffix) > 130 or not re.fullmatch(r"[a-z_0-9=&%\-]+", suffix)):
            raise ReviewHeld("UNSAFE_SEARCH_QUERY_PARAMETERS")
        url = SEARCH + path
        cap = MAX_RESPONSE
    else:
        if (not PATH_PATTERN.fullmatch(path) or "//" in path
                or ".." in path or len(path) > 120):
            raise ReviewHeld("UNAPPROVED_ORIGIN_PATH")
        url = ORIGIN + path
        cap = 2048
    request = Request(
        url, method="GET",
        headers={
            "Host": HOST if not search else "127.0.0.1:8771",
            "User-Agent": "EmpireOS-readonly-organic-404-review/1.0",
        },
    )
    try:
        with build_opener(RefuseRedirect()).open(request, timeout=12) as resp:
            payload = resp.read(cap + 1)
            if len(payload) > cap:
                raise ReviewHeld("UNBOUNDED_READONLY_RESPONSE")
            return resp.status, payload
    except HTTPError as exc:
        # 30x means inspect canonical/host routing separately. Never follow.
        if 300 <= exc.code <= 399:
            return exc.code, b""
        if not search and exc.code in (404, 410):
            return exc.code, b""
        raise ReviewHeld("READ_ONLY_ENDPOINT_FAILURE") from None
    except ReviewHeld:
        raise
    except (URLError, TimeoutError, OSError):
        raise ReviewHeld("READ_ONLY_ENDPOINT_FAILURE") from None


def _json_get(path: str) -> dict[str, Any]:
    http, raw = _get(path, search=True)
    if http != 200:
        raise ReviewHeld("GSC_SOURCE_UNAVAILABLE")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError, UnicodeDecodeError):
        raise ReviewHeld("GSC_SCHEMA_INVALID") from None
    if not isinstance(data, dict):
        raise ReviewHeld("GSC_SCHEMA_INVALID")
    return data


def _metric(value: Any) -> int:
    if type(value) is not int or value < 0 or value > 100_000_000:
        raise ReviewHeld("GSC_METRIC_INVALID")
    return value


def _safe_path(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 250:
        return None
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname != HOST
            or parsed.port is not None or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
        return None
    return parsed.path if PATH_PATTERN.fullmatch(parsed.path) else None


def audit(
    daily: dict[str, Any],
    pages: dict[str, Any],
    *,
    origin_status: Callable[[str], int],
    start: date,
    end: date,
) -> dict[str, Any]:
    if ((end - start).days < 0 or (end - start).days + 1 > MAX_DAYS
            or end >= date.today()):
        raise ReviewHeld("DATE_WINDOW_NOT_HISTORICAL_AND_BOUNDED")
    for envelope in (daily, pages):
        if (envelope.get("available") is not True
                or envelope.get("source") != "google_search_console"
                or envelope.get("site_url") != SITE
                or not isinstance(envelope.get("items"), list)
                or envelope.get("count") != len(envelope["items"])):
            raise ReviewHeld("GSC_ENVELOPE_UNVERIFIED")
    daily_rows = daily["items"]
    page_rows = pages["items"]
    if len(daily_rows) > MAX_DAYS or len(page_rows) > MAX_GSC_ROWS:
        raise ReviewHeld("GSC_SAMPLE_EXCEEDS_ALLOWLIST")
    total_impressions = total_clicks = 0
    observed_dates: set[str] = set()
    for row in daily_rows:
        keys = row.get("keys") if isinstance(row, dict) else None
        if not isinstance(keys, list) or len(keys) != 1:
            raise ReviewHeld("GSC_DAILY_DIMENSION_INVALID")
        try:
            row_date = date.fromisoformat(keys[0])
        except (TypeError, ValueError):
            raise ReviewHeld("GSC_DAILY_DIMENSION_INVALID") from None
        if row_date < start or row_date > end or keys[0] in observed_dates:
            raise ReviewHeld("GSC_DAILY_DIMENSION_INVALID")
        observed_dates.add(keys[0])
        impressions, clicks = _metric(row.get("impressions")), _metric(row.get("clicks"))
        if clicks > impressions:
            raise ReviewHeld("GSC_METRIC_INVALID")
        total_impressions += impressions
        total_clicks += clicks

    by_path: dict[str, dict[str, int]] = defaultdict(lambda: {
        "disclosed_query_page_rows": 0,
        "disclosed_impressions": 0,
        "disclosed_clicks": 0,
    })
    excluded = 0
    disclosed_total = 0
    for row in page_rows:
        keys = row.get("keys") if isinstance(row, dict) else None
        if not isinstance(keys, list) or len(keys) != 2:
            raise ReviewHeld("GSC_QUERY_PAGE_DIMENSION_INVALID")
        impressions, clicks = _metric(row.get("impressions")), _metric(row.get("clicks"))
        if clicks > impressions:
            raise ReviewHeld("GSC_METRIC_INVALID")
        disclosed_total += impressions
        path = _safe_path(keys[1])
        if path is None:
            excluded += 1
            continue
        entry = by_path[path]
        entry["disclosed_query_page_rows"] += 1
        entry["disclosed_impressions"] += impressions
        entry["disclosed_clicks"] += clicks

    found: list[dict[str, Any]] = []
    for path, metrics in by_path.items():
        code = origin_status(path)
        if type(code) is not int or code not in (200, 301, 302, 307, 308, 404, 410):
            raise ReviewHeld("ORIGIN_HTTP_PROBE_UNVERIFIED")
        fit = EXACT_KNOWN_REVENUE_TOPIC.get(path, "PRODUCT_RELEVANCE_UNVERIFIED")
        entry = {
            "path": path, "origin_http_status": code, **metrics,
            "product_relevance": fit,
            "next_action": (
                "REVIEW_FIRST_PARTY_BUYER_INTENT_EVIDENCE_AND_EXACT_PAGE_CONTENT"
                if fit == "BUYER_INTENT_TAM_RESEARCH" and code in (404, 410)
                else "RESEARCH_INTENT_AND_SOURCE_RIGHTS_BEFORE_REPAIR"
                if code in (404, 410) else
                "INSPECT_EXISTING_CANONICAL_AND_CONTENT"
            ),
            "redirect_authorized": False,
            "publishing_authorized": False,
        }
        found.append(entry)

    broken = [r for r in found if r["origin_http_status"] in (404, 410)]
    broken.sort(key=lambda r: (
        r["product_relevance"] != "BUYER_INTENT_TAM_RESEARCH",
        -r["disclosed_impressions"], r["path"]
    ))
    return {
        "schema_version": SCHEMA,
        "status": "OBSERVED_404_REVIEW_QUEUE" if broken else "NO_BROKEN_URLS_IN_DISCLOSED_SAMPLE",
        "mode": "OBSERVE", "read_only": True,
        "source": "live_google_search_console_via_existing_empire_search_intelligence",
        "site": SITE,
        "window_start": start.isoformat(), "window_end_requested": end.isoformat(),
        "latest_returned_date": max(observed_dates, default=None),
        "returned_days": len(observed_dates),
        "sitewide_observed_impressions": total_impressions,
        "sitewide_observed_clicks": total_clicks,
        "disclosed_query_page_rows": len(page_rows),
        "disclosed_query_page_impressions": disclosed_total,
        "excluded_query_page_rows": excluded,
        "allowed_paths_probed": len(found),
        "broken_paths_found": len(broken),
        "broken_disclosed_impressions": sum(x["disclosed_impressions"] for x in broken),
        "broken_review_queue": broken,
        "known_revenue_topic_review_count": sum(
            x["product_relevance"] == "BUYER_INTENT_TAM_RESEARCH" for x in broken
        ),
        "query_page_coverage_complete": False,
        "full_site_indexation_verified": False,
        "organic_conversion_attributed": False,
        "actual_revenue_claimed": False,
        "search_terms_disclosed": False,
        "redirect_authorized": False,
        "publishing_authorized": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def run(*, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    end = today - timedelta(days=2)
    start = end - timedelta(days=12)
    try:
        status = _json_get("/search-console/status")
        if (status.get("available") is not True or status.get("site_url") != SITE):
            raise ReviewHeld("LIVE_GSC_NOT_READY")
        params = urlencode({"start_date": start.isoformat(), "end_date": end.isoformat(),
                            "limit": MAX_GSC_ROWS})
        daily = _json_get("/search-console/daily?" + params)
        pages = _json_get("/search-console/observations?" + params)
        return audit(
            daily, pages, start=start, end=end,
            origin_status=lambda path: _get(path, search=False)[0]
        )
    except ReviewHeld as exc:
        return {
            "schema_version": SCHEMA,
            "status": "HELD",
            "reason_code": str(exc),
            "read_only": True,
            "outbound_sent": False,
            "database_writes": False,
            "publishing_authorized": False,
            "redirect_authorized": False,
            "execution_authority": "none",
        }
    except Exception:
        return {
            "schema_version": SCHEMA, "status": "HELD",
            "reason_code": "UNEXPECTED_GSC_AUDIT_FAILURE",
            "read_only": True, "database_writes": False, "outbound_sent": False,
            "publishing_authorized": False, "redirect_authorized": False,
            "execution_authority": "none",
        }


def main() -> int:
    result = run()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] != "HELD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
