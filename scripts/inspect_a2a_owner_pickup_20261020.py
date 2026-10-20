#!/usr/bin/env python3
"""Read an existing A2A research pickup for the responsible owner.

Makes research tasks practically inspectable without dispatching anything.
Owner-specific approval and source execution remain in existing owner code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.a2a_owner_research_protocol_v1 import OWNERS
from empire_os.a2a_owner_pickup_change_tracking_v1 import review_pickup_changes

REPORT = (Path(__file__).resolve().parents[1] /
          "runtime/a2a_commercial_signal_mining/owner_research_pickup_v1.json")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read existing owner-specific research pickup")
    p.add_argument("--owner", required=True, choices=tuple(sorted(OWNERS)))
    p.add_argument("--detail", action="store_true",
                   help="Show source identifiers and proposed queries for owner review")
    args = p.parse_args(argv)
    if REPORT.is_symlink() or not REPORT.is_file() or REPORT.stat().st_size > 100_000:
        raise ValueError("MISSING_OR_UNSAFE_OWNER_PICKUP_REPORT")
    source = json.loads(REPORT.read_text(encoding="utf8"))
    review_pickup_changes(source)
    requests = source["pickup_by_owner"][args.owner]
    shown = []
    for item in requests:
        row = {
            "ticket_id": item["ticket_id"],
            "ticket_sha256": item["ticket_sha256"],
            "state": item["execution_state"],
            "owner": args.owner,
            "sector": item["research_request"]["sector"],
            "market": item["research_request"]["market"],
            "product": item["research_request"]["product"],
            "owner_acceptance_required": True,
        }
        if args.detail:
            row.update({
                "source_atlas_ids": item["research_request"]["existing_public_atlas_source_ids"],
                "suggested_queries_not_executed": item["research_request"]["suggested_research_queries_not_executed"],
                "acceptance_criteria": item["research_request"]["acceptance_criteria"],
            })
        shown.append(row)
    print(json.dumps({
        "schema_version": "empire.a2a.owner_pickup_inspection.v1",
        "owner": args.owner, "ticket_count": len(shown),
        "research_tickets": shown,
        "dispatch_performed": False, "commercial_contact_authorized": False,
        "buyer_records_modified": False, "execution_authority": "NONE",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
