"""Inspect precise Revenue GPS territory evidence for Predictive Economic Twins."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_market_evidence_binding import (
    review_revenue_gps_territory_evidence_runtime,
)


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--read-only",required=True,action="store_true")
    ap.add_argument("--repo-root",default="/srv/empire_os")
    ap.add_argument("--niche",default=None)
    args=ap.parse_args()
    result=review_revenue_gps_territory_evidence_runtime(
        args.repo_root,as_of=datetime.now(timezone.utc),
    )
    if args.niche is not None:
        if not isinstance(args.niche,str) or len(args.niche)>65 or not args.niche.isidentifier():
            raise ValueError("use bounded product niche slug")
        result["territory_research_cards"]=[
            card for card in result["territory_research_cards"]
            if card.get("market_niche_key")==args.niche
        ]
        result["display_filter_only"]=args.niche
        result["filtered_count"]=len(result["territory_research_cards"])
        result["full_source_market_count_unmodified"]=result["market_count"]
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY" else 2


if __name__=="__main__":
    raise SystemExit(main())
