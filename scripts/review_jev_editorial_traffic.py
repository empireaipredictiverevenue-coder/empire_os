"""Operator-triggered official-news-to-live-Empire-page research preview.

No article publication, scheduler, site mutation, outbound, or payment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.jev_newsjack_official_sources import (
    federal_register_signals, govuk_primary_signal,
)
from empire_os.jev_newsjack_traffic_briefs import prepare_editorial_traffic_reviews
from empire_os.jev_newsjack_marketing_handoff import prepare_marketing_director_handoff


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify official source and owned destination for an editorial review."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--govuk-url")
    source.add_argument("--federal-register-term")
    source.add_argument("--source-packet")
    parser.add_argument("--sector", required=True,
                        choices=("solar", "roofing", "ai", "hvac", "dental"))
    parser.add_argument("--market", required=True, choices=("GB", "US"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--include-items", action="store_true")
    parser.add_argument("--local-jev-shadow", action="store_true",
                        help="Use existing local Laya classifier in shadow mode")
    parser.add_argument("--marketing-handoff", action="store_true",
                        help="Add Media OS and existing Marketing Agency draft + UTM plan")
    args = parser.parse_args()

    if args.govuk_url:
        if args.market != "GB":
            parser.error("GOV.UK can only represent GB sources")
        packet = govuk_primary_signal(
            public_url=args.govuk_url, sector=args.sector, as_of=args.as_of)
    elif args.federal_register_term:
        if args.market != "US":
            parser.error("Federal Register can only represent US sources")
        packet = federal_register_signals(
            term=args.federal_register_term, sector=args.sector,
            as_of=args.as_of, max_results=args.limit)
    else:
        path = Path(args.source_packet)
        if not path.is_file() or path.stat().st_size > 150_000:
            parser.error("bounded existing source packet file required")
        packet = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(packet, dict) or not isinstance(packet.get("signals"), list):
            parser.error("source packet must contain bounded signals")
    provider = None
    if args.local_jev_shadow:
        from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
        provider = LayaHttpTypedDecisionProvider(timeout_s=7)
    result = prepare_editorial_traffic_reviews(
        packet["signals"], as_of=args.as_of, provider=provider)
    result["local_jev_shadow_requested"] = args.local_jev_shadow
    if args.marketing_handoff:
        handoff = prepare_marketing_director_handoff(result, generated_at=args.as_of)
        if not args.include_items:
            handoff["campaign_previews"] = []
        result["marketing_director_handoff"] = handoff
    if not args.include_items:
        result["review_queue"] = []
        result["observed_owned_pages"] = {
            page: {
                "live_verified": row["live_verified"],
                "status": row["status"],
            }
            for page, row in result["observed_owned_pages"].items()
        }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
