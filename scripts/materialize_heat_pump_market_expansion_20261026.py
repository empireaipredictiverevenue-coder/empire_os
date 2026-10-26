#!/usr/bin/env python3
"""One-shot public-market research admission into original Buyer Network receipts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.heat_pump_market_expansion import run

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    result=run(Path("/srv/empire_os"),write=args.write)
    print(json.dumps({
        "status":result["status"],"candidate_count":result["candidate_count"],
        "lane_counts":result["lane_counts"],
        "existing_registry_or_scout_exact_matches":result["existing_registry_or_scout_exact_matches"],
        "prior_contact_or_identity_collision_reviews":result["prior_contact_or_identity_collision_reviews"],
        "fresh_research_only_without_exact_match":result["fresh_research_only_without_exact_match"],
        "buyers_verified":result["eligible_payable_agreements"],
        "automatic_outbound":result["outbound_authorized"],
        "database_writes":result["database_writes"],
        "private_snapshot_written":bool(args.write),
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
