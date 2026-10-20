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
from empire_os.buyer_scout_source_verification_queue_20261020 import make_buyer_scout_source_verification_queue
from empire_os.buyer_scout_canonical_dedupe_request_v1 import prepare_canonical_lookup_requests
REPO=Path(__file__).resolve().parents[1]
A2A=Path("/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020/runtime/a2a_commercial_signal_mining")
CANONICAL=Path("/srv/empire_os/runtime/buyer_acquisition")
OUT=REPO/"runtime/buyer_acquisition/a2a_research_owner_intake_latest.json"
QUEUE=REPO/"runtime/buyer_acquisition/a2a_source_verification_queue_latest.json"
CANONICAL_LOOKUPS=REPO/"runtime/buyer_acquisition/a2a_canonical_domain_lookup_requests_latest.json"


def _safe_write(out_path: Path, value: dict) -> None:
    out_path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if out_path.parent.is_symlink() or out_path.is_symlink():
        raise ValueError("UNSAFE_BUYER_SCOUT_OWNER_REVIEW_DESTINATION")
    fd,tmp=tempfile.mkstemp(prefix=".a2a_owner_review_",dir=out_path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w",encoding="utf8") as f:
            json.dump(value,f,indent=2,sort_keys=True)
            f.write("\n")
        os.replace(tmp,out_path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


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
    queue=make_buyer_scout_source_verification_queue(out)
    lookup_requests=prepare_canonical_lookup_requests(queue)
    if args.write_local:
        _safe_write(OUT,out)
        _safe_write(QUEUE,queue)
        _safe_write(CANONICAL_LOOKUPS,lookup_requests)
    print(json.dumps({
        "schema_version":out["schema_version"],
        "buyer_scout_owner_evidence_read":out["source_evidence_read_into_owner_workspace"],
        "a2a_website_source_records":out["website_research_record_count"],
        "a2a_website_overlaps_with_known_records":out["website_records_overlapping_known_search_or_scout"],
        "official_contractor_business_hypotheses":out["official_company_record_count"],
        "company_website_evidence_current_for_review":out["website_source_records_eligible_for_further_owner_review"],
        "individually_source_bound_websites":out["website_receipts_individually_bound_to_source"],
        "ready_site_identity_verification_tasks":queue["ready_first_party_verification_count"],
        "source_policy_held_site_tasks":queue["held_site_count"],
        "historical_permit_name_review_tasks":queue["historical_official_context_count"],
        "owner_verification_tasks_dispatched":queue["tasks_dispatched_to_live_buyer_scout"],
        "canonical_lookup_requests_prepared":lookup_requests["lookup_request_count"],
        "canonical_database_read_performed":lookup_requests["canonical_database_read_performed"],
        "canonical_crm_records_created":0,
        "outreach_sent":0,
        "cryptographically_verified_signed_owner_receipts":0,
        "actual_buyers_verified":0,
        "owner_evidence_intake_saved":args.write_local,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
