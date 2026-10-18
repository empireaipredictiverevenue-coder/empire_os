#!/usr/bin/env python3
"""Page-only GSC legacy 404 review using existing SEO observer transport.

Reuses the Search Intelligence loopback endpoint and the exact existing
Host-pinned same-origin HTTP GET. No new crawler, auth, timer, database,
website mutation or third-party network traffic. Output includes no queries.
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta
import json
from typing import Any

from scripts import review_live_search_404_revenue_readonly as existing
from empire_os.search_intelligence.legacy_404_page_review import (
    LegacyPageReviewHeld, review_page_only_legacy_404,
)


def run(*, start: date | None = None, end: date | None = None,
        today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    end = end or today - timedelta(days=2)
    start = start or end - timedelta(days=12)
    try:
        if not (start <= end < today) or (end - start).days > 30:
            raise LegacyPageReviewHeld("UNVERIFIED_GSC_WINDOW")
        status = existing._json_get("/search-console/status")
        if (status.get("available") is not True
                or status.get("site_url") != existing.SITE):
            raise LegacyPageReviewHeld("LIVE_GSC_SOURCE_UNAVAILABLE")
        page_packet = existing._json_get(
            "/search-console/pages?"
            f"start_date={start.isoformat()}&end_date={end.isoformat()}"
            "&limit=250"
        )
        return review_page_only_legacy_404(
            page_packet, start=start, end=end, today=today,
            safe_path=existing._safe_path,
            origin_status=lambda path: existing._get(path, search=False)[0],
        )
    except (existing.ReviewHeld, LegacyPageReviewHeld) as exc:
        return {
            "schema_version": "empire.organic_search.gsc_page_legacy_404_review.v1",
            "status": "HELD",
            "reason_code": str(exc),
            "mode": "OBSERVE",
            "sitewide_traffic_verified": False,
            "redirect_authorized": False,
            "publication_authorized": False,
            "outbound_sent": False,
            "database_writes": False,
            "execution_authority": "none",
        }
    except Exception:
        return {
            "schema_version": "empire.organic_search.gsc_page_legacy_404_review.v1",
            "status": "HELD",
            "reason_code": "UNEXPECTED_READONLY_PAGE_REVIEW_FAILURE",
            "mode": "OBSERVE",
            "sitewide_traffic_verified": False,
            "redirect_authorized": False,
            "publication_authorized": False,
            "outbound_sent": False,
            "database_writes": False,
            "execution_authority": "none",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat,
                        help="Historical first date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=date.fromisoformat,
                        help="Historical final date (YYYY-MM-DD)")
    parser.add_argument("--summary-only", action="store_true",
                        help="Omit path-level detail; count by review category")
    args = parser.parse_args(argv)
    if bool(args.start_date) != bool(args.end_date):
        parser.error("start-date and end-date must be specified together")
    report = run(start=args.start_date, end=args.end_date)
    if args.summary_only:
        report.pop("missing_review_queue", None)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] != "HELD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
