#!/usr/bin/env python3
"""Read currently prepared first-party buyer-research evidence for owner review."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.a2a_first_party_buyer_scout_handoff_v1 import SCHEMA

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"runtime/a2a_commercial_signal_mining/first_party_buyer_scout_handoff_v1.json"


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Read bounded public first-party Buyer Scout review packets")
    parser.add_argument("--market",choices=("tampa, fl","little rock, ar","nyc"),required=True)
    parser.add_argument("--only-reviewable",action="store_true")
    args=parser.parse_args(argv)
    if REPORT.is_symlink() or not REPORT.is_file() or REPORT.stat().st_size>100000:
        raise ValueError("UNSAFE_OR_MISSING_BUYER_SCOUT_RESEARCH_PACKET")
    data=json.loads(REPORT.read_text(encoding="utf-8"))
    if (not isinstance(data,dict) or data.get("schema_version")!=SCHEMA
            or data.get("mode")!="OBSERVE" or data.get("execution_authority")!="NONE"
            or data.get("verified_buyers")!=0 or data.get("messages_sent")!=0
            or data.get("buyer_scout_owner_tasks_dispatched")!=0
            or data.get("canonical_buyer_records_created")!=0):
        raise ValueError("UNTRUSTED_OWNER_PACKET")
    entries=data.get("scoped_review_packets")
    if not isinstance(entries,list) or len(entries)>9:
        raise ValueError("INVALID_OWNER_EVIDENCE_ENTRIES")
    scoped=[row for row in entries if isinstance(row,dict) and row.get("target_market")==args.market]
    if args.only_reviewable:
        scoped=[row for row in scoped if row.get("ready_for_buyer_scout_owner_research_review") is True]
    print(json.dumps({
        "schema_version":"empire.a2a.first_party_owner_review_inspection.v1",
        "market":args.market,
        "company_website_research_packet_count":len(scoped),
        "source_packets":scoped,
        "research_only":True,
        "owner_acceptance_required":True,
        "verified_purchasers":0,
        "buyer_scout_tasks_dispatched":0,
        "messages_sent":0,
        "crm_changes":False,
        "execution_authority":"NONE",
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
