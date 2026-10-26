"""Review original Keyword Universe → GSC query evidence → research triage.

One allowlisted Search Intelligence loopback GET with explicit GSC date flags.
No credentials, DB writes, outbound, paid provider, SEO publish or forecast.
"""
from __future__ import annotations
import argparse
from datetime import date
import json

from empire_os.public_intent_offer_method_bridge import (
    IntentOfferSpec, prepare_public_intent_offer_review,
)
from empire_os.public_intent_gsc_evidence_bridge import read_original_loopback_gsc
from empire_os.public_intent_evidence_triage import build_intent_evidence_review_queue


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--market",required=True)
    parser.add_argument("--seed",required=True)
    parser.add_argument("--icp",required=True)
    parser.add_argument("--buyer-problem",required=True)
    parser.add_argument("--glossary",default="")
    parser.add_argument("--product",default="search_opportunity_map")
    parser.add_argument("--full",action="store_true")
    parser.add_argument("--gsc-start",help="Existing first-party GSC start YYYY-MM-DD")
    parser.add_argument("--gsc-end",help="Existing first-party GSC end YYYY-MM-DD")
    args=parser.parse_args()
    if bool(args.gsc_start)!=bool(args.gsc_end):
        parser.error("--gsc-start and --gsc-end are required together")
    terms=tuple(x.strip() for x in args.glossary.split(",") if x.strip())
    result=prepare_public_intent_offer_review(IntentOfferSpec(
        market_key=args.market,seed_keyword=args.seed,
        icp_key=args.icp,buyer_problem=args.buyer_problem,
        product_key=args.product,glossary_terms=terms,
    ))
    gsc=None
    if args.gsc_start:
        try:
            start=date.fromisoformat(args.gsc_start)
            end=date.fromisoformat(args.gsc_end)
        except ValueError:
            parser.error("GSC dates must be YYYY-MM-DD")
        gsc=read_original_loopback_gsc(result,start=start,end=end)
        result["first_party_gsc"]=gsc
    observed=(gsc if gsc and "ideas" in gsc else None)
    result["research_review_order"]=build_intent_evidence_review_queue(result,observed)
    if not args.full:
        result.pop("universe",None)
        result.pop("existing_asset_backlog",None)
        # Full evidence rows remain available with --full. Show priority
        # wording and counts without leaking unnecessary route inventory.
        result["research_review_order"]["priority_ordered_candidates"]= [
            {k:v for k,v in row.items() if k!="observed_query_page_rows"}
            for row in result["research_review_order"]["priority_ordered_candidates"]
        ]
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
