#!/usr/bin/env python3
"""Page-only Google Search Console report for four existing commercial URLs.

Feature branch only until Search Intelligence API integration. On production
without the /pages endpoint, fail closed; do not substitute query/page rows.
GET localhost only, bounded data, no credential handling or database writes.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from typing import Any, Callable, Mapping

import requests

from empire_os.search_intelligence.first_party_gsc_page_review import (
    PROPERTY, GscPageEvidenceError, review_gsc_priority_pages,
)


BASE = "http://127.0.0.1:8771/v1/search"


def local_gsc_get(path: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if path not in {"/search-console/status", "/search-console/pages"}:
        raise GscPageEvidenceError("unexpected GSC page report route")
    response = requests.get(BASE + path, params=dict(params or {}),
                            allow_redirects=False, timeout=15)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, Mapping):
        raise GscPageEvidenceError("malformed GSC API payload")
    return body


def build_live_priority_page_report(
    *,
    start_date: str,
    end_date: str,
    get_json: Callable[..., Mapping[str, Any]] = local_gsc_get,
) -> dict[str, Any]:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError) as exc:
        raise GscPageEvidenceError("valid ISO date window required") from exc
    if end < start or (end - start).days > 31:
        raise GscPageEvidenceError("page-only GSC review window must be 0..31 days")
    status = get_json("/search-console/status")
    if status.get("available") is not True or status.get("site_url") != PROPERTY:
        raise GscPageEvidenceError("GSC adapter or domain property unverified")
    payload = get_json("/search-console/pages", params={
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "limit": 1000,
    })
    return review_gsc_priority_pages(
        payload, start_date=start.isoformat(), end_date=end.isoformat(),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--format", choices=("summary", "json"), default="summary")
    args = p.parse_args(argv)
    try:
        report = build_live_priority_page_report(
            start_date=args.start_date, end_date=args.end_date,
        )
    except (requests.RequestException, ValueError, GscPageEvidenceError):
        print(json.dumps({
            "status": "GSC_PAGE_DIMENSION_NOT_YET_VERIFIED",
            "paid_api_calls": 0,
            "production_changed": False,
            "indexation_verified": False,
            "execution_authority": "none",
        }, sort_keys=True), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(json.dumps({
            "status": "FIRST_PARTY_PAGE_ONLY_GSC_REVIEW_COMPLETE",
            "window": report["date_window"],
            "returned_page_rows": report["returned_page_rows"],
            "priority_pages": [
                {
                    "url": item["canonical_url"],
                    "status": item["status"],
                    "observed_alias_count": item["observed_alias_count"],
                    "reported_rows": [{
                        "impressions": row["impressions"],
                        "clicks": row["clicks"],
                        "observed_page_url": row["observed_page_url"],
                    } for row in item["observed_url_aliases"]],
                    "google_indexing_verified": False,
                }
                for item in report["priority_page_findings"]
            ],
            "commercial_conversion_verified": False,
            "production_changed": False,
            "execution_authority": "none",
        }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
