#!/usr/bin/env python3
"""Review existing buyer-network and DFW storm snapshots, without any mutation.

Only reads explicit local JSON files. Makes no outbound requests or sales actions.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

from empire_os.claims_exchange.adapters import buyer_queue_candidates, dfw_storm_candidates, official_network_research_candidates
from empire_os.claims_exchange.controls import parse_date, reject_sensitive_input
from empire_os.claims_exchange.pipeline import build_snapshot


# Fixed private OBSERVE-only runtime path; never accept a user-selected path.
OUTPUT_PATH = Path("/srv/empire_os/runtime/claims_exchange/research_latest.json")


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("source_missing_or_over_limit")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("source_must_be_object")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buyer-queue", required=True, type=Path)
    parser.add_argument("--dfw-cohort", required=True, type=Path)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument(
        "--write-private-observe-snapshot", action="store_true",
        help="Save only the reviewed, no-personal-data OBSERVE summary to the existing runtime directory.",
    )
    args = parser.parse_args(argv)
    try:
        as_of = parse_date(args.as_of)
        if as_of is None or not 0 <= args.top <= 25:
            raise ValueError("invalid_view_parameters")
        # Fail closed on sensitive policyholder/claim fields BEFORE projection.
        # Sanitising them out of the output is not sufficient for this lane.
        raw_buyers = _load(args.buyer_queue)
        raw_dfw = _load(args.dfw_cohort)
        reject_sensitive_input(raw_buyers)
        reject_sensitive_input(raw_dfw)
        buyer, buyer_report = buyer_queue_candidates(raw_buyers)
        dfw, dfw_report = dfw_storm_candidates(raw_dfw)
        official_programs = official_network_research_candidates()
        snapshot = build_snapshot({"candidates": buyer + dfw + official_programs}, as_of=as_of)
        # The output excludes the raw source records, which can include
        # internal identity aliases, investigative evidence and contacts.
        result = {
            "schema": "empire.claims_exchange.existing_sources_preview_v2",
            "mode": "OBSERVE",
            "as_of": as_of.isoformat(),
            "source_reports": {"buyer_network": buyer_report, "dfw_cohort": dfw_report,
                               "official_network_programs": {"research_rows": len(official_programs), "demand_or_capacity_inferred": False}},
            "summary": snapshot["summary"],
            "research_preview": [{
                "company_name": r["company_name"],
                "kind": r["kind"],
                "jurisdiction": r["jurisdiction"],
                "research_priority": r["research_priority"],
                "triage_priority": r["triage_priority"],
                "research_source": r["research_source"],
                "review_state": r["review_state"],
                "missing_evidence": r["missing_evidence"],
            } for r in snapshot["research_queue"][:args.top]],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "actual_revenue": 0, "outbound_sent": 0,
            "outbound_authorized": False, "execution_authority": "none",
        }
        if args.write_private_observe_snapshot:
            # No user-supplied output path, no secrets, no outbound, no DB.
            dest = OUTPUT_PATH
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_symlink():
                raise ValueError("unsafe_observe_snapshot_destination")
            tmp = dest.with_suffix(".json.tmp")
            if tmp.is_symlink():
                raise ValueError("unsafe_temporary_destination")
            tmp.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.chmod(tmp, 0o600)
            tmp.replace(dest)
            os.chmod(dest, 0o600)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError):
        print(json.dumps({"schema": "empire.claims_exchange.error_v2",
                          "status": "SOURCE_REJECTED", "mode": "OBSERVE",
                          "outbound_authorized": False, "execution_authority": "none"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
