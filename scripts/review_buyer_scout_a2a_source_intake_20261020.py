#!/usr/bin/env python3
"""Read the existing A2A research packets in Buyer Scout's isolated owner workspace.

No remote requests, credentials, DB connections, outreach or owner promotion.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
from empire_os.buyer_scout_a2a_research_intake_20261020 import (
    stage_a2a_owner_research,read_bounded_json,
)
REPO=Path(__file__).resolve().parents[1]
A2A=Path("/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020/runtime/a2a_commercial_signal_mining")
CANONICAL=Path("/srv/empire_os/runtime/buyer_acquisition")
OUT=REPO/"runtime/buyer_acquisition/a2a_research_owner_intake_latest.json"


def main() -> int:
    p=argparse.ArgumentParser(description="Read-only canonical Buyer Scout research owner source intake")
    p.add_argument("--read-only-owner-review",action="store_true",required=True)
    p.add_argument("--write-local",action="store_true")
    args=p.parse_args()
    docs=[
        read_bounded_json(A2A/"first_party_buyer_scout_handoff_v1.json"),
        read_bounded_json(A2A/"official_permit_buyer_scout_review_v1.json"),
        read_bounded_json(CANONICAL/"scout_latest.json",ceiling=2_000_000),
        read_bounded_json(CANONICAL/"public_research_seeds.json",ceiling=2_000_000),
        read_bounded_json(A2A/"first_party_source_readback_v1.json"),
    ]
    out=stage_a2a_owner_research(*docs)
    if args.write_local:
        OUT.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if OUT.parent.is_symlink() or OUT.is_symlink():
            raise ValueError("UNSAFE_BUYER_SCOUT_OWNER_REVIEW_DESTINATION")
        fd,tmp=tempfile.mkstemp(prefix=".a2a_owner_review_",dir=OUT.parent)
        try:
            os.fchmod(fd,0o600)
            with os.fdopen(fd,"w",encoding="utf8") as f:
                json.dump(out,f,indent=2,sort_keys=True)
                f.write("\n")
            os.replace(tmp,OUT)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    print(json.dumps({
        "schema_version":out["schema_version"],
        "buyer_scout_owner_evidence_read":out["source_evidence_read_into_owner_workspace"],
        "a2a_website_source_records":out["website_research_record_count"],
        "a2a_website_overlaps_with_known_records":out["website_records_overlapping_known_search_or_scout"],
        "official_contractor_business_hypotheses":out["official_company_record_count"],
        "company_website_evidence_current_for_review":out["website_source_records_eligible_for_further_owner_review"],
        "canonical_crm_records_created":0,
        "outreach_sent":0,
        "cryptographically_verified_signed_owner_receipts":0,
        "actual_buyers_verified":0,
        "owner_evidence_intake_saved":args.write_local,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
