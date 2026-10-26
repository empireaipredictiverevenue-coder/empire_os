#!/usr/bin/env python3
"""Run one bounded canonical Lead Scoring v2 qualification cycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.parse
from datetime import datetime, timezone

from empire_os.qualification_worker_v2 import (
    run_cycle,
    run_identity_catchup,
    run_evidence_recovery,
    run_historical_backfill_batch,
)
from empire_os.qualification_historical_backfill_cursor import (
    load_cursor, save_cursor,
)
from empire_os.sb import request_json
from empire_os.omega_worker import run_omega_cycle
from empire_os.signal_resolver import run_signal_resolution
from empire_os.omega_buyer_readiness import (
    run_omega_buyer_readiness_cycle,
)
from empire_os.commercial_loop_observer import (
    assess_commercial_loop,
    fetch_canonical_commercial_observations,
    observations_from_cycle,
    read_latest_acquisition_accepted,
    write_commercial_loop_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--identity-catchup-limit",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--signal-resolution-limit",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--evidence-recovery-limit",
        type=int,
        default=10,
    )
    parser.add_argument("--historical-backfill-limit", type=int, default=0)
    parser.add_argument("--historical-identity-backfill-limit", type=int, default=0)
    parser.add_argument("--approved-historical-backfill", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 25:
        parser.error("--limit must be between 1 and 25")
    if args.identity_catchup_limit < 0 or args.identity_catchup_limit > 25:
        parser.error("--identity-catchup-limit must be between 0 and 25")
    if args.signal_resolution_limit < 0 or args.signal_resolution_limit > 25:
        parser.error("--signal-resolution-limit must be between 0 and 25")

    if args.evidence_recovery_limit < 0 or args.evidence_recovery_limit > 25:
        parser.error("--evidence-recovery-limit must be between 0 and 25")
    if not 0 <= args.historical_backfill_limit <= 25:
        parser.error("--historical-backfill-limit must be between 0 and 25")
    if not 0 <= args.historical_identity_backfill_limit <= 25:
        parser.error("--historical-identity-backfill-limit must be between 0 and 25")
    if args.historical_backfill_limit + args.historical_identity_backfill_limit > 25:
        parser.error("combined historical backfill limit must not exceed 25")
    if (args.historical_backfill_limit or args.historical_identity_backfill_limit) and not args.approved_historical_backfill:
        parser.error("historical backfill requires --approved-historical-backfill")

    signal_resolution = (
        run_signal_resolution(args.signal_resolution_limit)
        if args.signal_resolution_limit
        else {
            "schema_version": "empire.signal-resolution.v1",
            "ok": True,
            "attempted": 0,
            "resolved": 0,
            "failed": 0,
            "results": [],
        }
    )
    qualification = run_cycle(args.limit)
    historical_backfill = {
        "enabled": False, "attempted": 0, "scanned_rows": 0,
        "qualified": 0, "ok": True, "outbound_authorized": False,
    }
    if args.historical_backfill_limit:
        current_offset = load_cursor()
        historical_backfill = run_historical_backfill_batch(
            offset=current_offset, limit=args.historical_backfill_limit,
        )
        historical_backfill["enabled"] = True
        if historical_backfill["cursor_may_advance"]:
            next_offset = (
                0 if historical_backfill["archive_exhausted"]
                else historical_backfill["proposed_next_offset"]
            )
            save_cursor(next_offset)
            historical_backfill["cursor_committed"] = True
            historical_backfill["next_offset"] = next_offset
        else:
            historical_backfill["cursor_committed"] = False
            historical_backfill["next_offset"] = current_offset
    identity_linked_backfill = {
        "enabled": False, "attempted": 0, "scanned_rows": 0,
        "qualified": 0, "identity_resolved": 0,
        "ok": True, "outbound_authorized": False,
    }
    if args.historical_identity_backfill_limit:
        identity_cursor = Path(
            "/srv/empire_os/runtime/qualification/"
            "historical_identity_linked_cursor.json"
        )
        identity_offset = load_cursor(identity_cursor)
        identity_linked_backfill = run_historical_backfill_batch(
            offset=identity_offset,
            limit=args.historical_identity_backfill_limit,
            identity_linked=True,
        )
        identity_linked_backfill["enabled"] = True
        if identity_linked_backfill["cursor_may_advance"]:
            identity_next = (
                0 if identity_linked_backfill["archive_exhausted"]
                else identity_linked_backfill["proposed_next_offset"]
            )
            save_cursor(identity_next, path=identity_cursor)
            identity_linked_backfill["cursor_committed"] = True
            identity_linked_backfill["next_offset"] = identity_next
        else:
            identity_linked_backfill["cursor_committed"] = False
            identity_linked_backfill["next_offset"] = identity_offset
    evidence_recovery = (
        run_evidence_recovery(args.evidence_recovery_limit)
        if args.evidence_recovery_limit
        else {
            "schema_version": "qualification_evidence_recovery.v1",
            "ok": True,
            "attempted": 0,
            "requalified": 0,
            "skipped_unchanged": 0,
            "deferred": 0,
            "failed": 0,
            "results": [],
            "errors": [],
        }
    )
    catchup = (
        run_identity_catchup(args.identity_catchup_limit)
        if args.identity_catchup_limit
        else {
            "schema_version": "qualification_identity_catchup.v1",
            "ok": True,
            "attempted": 0,
            "qualified": 0,
            "failed": 0,
            "identity_resolved": 0,
            "results": [],
            "errors": [],
        }
    )
    omega = run_omega_cycle(args.limit)
    buyer_readiness = run_omega_buyer_readiness_cycle(args.limit)

    def canonical_reader(path: str, params: dict[str, str]):
        query = urllib.parse.urlencode(params)
        return request_json("GET", f"{path}?{query}")

    canonical_observations = fetch_canonical_commercial_observations(
        canonical_reader,
        now=datetime.now(timezone.utc),
    )
    commercial_loop = assess_commercial_loop(
        observations_from_cycle(
            acquisition_accepted=read_latest_acquisition_accepted(),
            qualification=qualification,
            omega=omega,
            buyer_readiness=buyer_readiness,
            canonical_observations=canonical_observations,
        )
    )
    write_commercial_loop_snapshot(commercial_loop)
    result = {
        "schema_version": "qualification_service_cycle.v4",
        "signal_resolution": signal_resolution,
        "qualification": qualification,
        "historical_backfill": historical_backfill,
        "historical_identity_linked_backfill": identity_linked_backfill,
        "evidence_recovery": evidence_recovery,
        "identity_catchup": catchup,
        "omega_projection": omega,
        "buyer_readiness": buyer_readiness,
        "commercial_loop": commercial_loop.as_dict(),
        "ok": bool(
            signal_resolution["ok"]
            and qualification["ok"]
            and historical_backfill["ok"]
            and identity_linked_backfill["ok"]
            and evidence_recovery["ok"]
            and catchup["ok"]
            and omega["ok"]
            and buyer_readiness["ok"]
        ),
    }
    # Preserve business/pipeline truth independently of process health.
    result["business_ok"] = bool(result["ok"])
    result["service_health"] = "completed"

    print(json.dumps(result, indent=2, default=str))

    # A handled business-state blocker must not make the systemd
    # heartbeat itself unhealthy. Real execution defects still raise.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
