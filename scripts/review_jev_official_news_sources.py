"""Manual official-source discovery → first-party JEV traffic review. No scheduling."""
from __future__ import annotations

import argparse
import json

from empire_os.jev_newsjack_official_sources import (
    federal_register_signals, govuk_primary_signal,
)
from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic


def main() -> int:
    parser = argparse.ArgumentParser(description="£0 government source review; never publishes")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--federal-register-term")
    sources.add_argument("--govuk-url")
    parser.add_argument("--sector", required=True,
                        choices=["solar", "roofing", "hvac", "dental", "ai"])
    parser.add_argument("--as-of", required=True,
                        help="Observed UTC/current time as timezone-aware ISO-8601")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--local-jev-shadow", action="store_true",
                        help="Use existing localhost Laya shadow classifier; no paid API")
    parser.add_argument("--include-items", action="store_true")
    args = parser.parse_args()

    if args.federal_register_term:
        packet = federal_register_signals(
            term=args.federal_register_term, as_of=args.as_of,
            sector=args.sector, max_results=args.limit,
        )
        market = "US"
    else:
        packet = govuk_primary_signal(
            public_url=args.govuk_url, sector=args.sector, as_of=args.as_of,
        )
        market = "GB"
    provider = None
    if args.local_jev_shadow:
        from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
        provider = LayaHttpTypedDecisionProvider(timeout_s=7)
    review = review_newsjack_jev_traffic(
        packet["signals"],
        as_of=args.as_of,
        approved_sectors=[args.sector],
        approved_markets=[market],
        provider=provider,
    )
    report = {
        "schema_version": "empire.organic.official_news_review.v1",
        "mode": "OBSERVE", "source": packet["source"],
        "source_url": packet["source_url"],
        "source_candidates": packet["candidate_count"],
        "status_counts": review["status_counts"],
        "jev_shadow_requested": args.local_jev_shadow,
        "source_claims_fully_verified": False,
        "search_console_queried": False,
        "publications_made": 0,
        "outbound_sent": False,
        "execution_authority": "none",
    }
    if args.include_items:
        report["candidates"] = review["candidates"]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
