#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_review_materializer import run_buyer_review_materializer
from empire_os.gtm_standing_bridge import run_standing_bridge
from empire_os.solar_opportunity_map_automation import (
    materialize_solar_maps_for_review_outcomes,
)

STATE = Path("/srv/empire_os/runtime/buyer_review_materializer/state.json")
LATEST = Path("/srv/empire_os/runtime/buyer_review_materializer/latest.json")


def _state() -> dict:
    try:
        value = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-limit", type=int, default=40)
    parser.add_argument("--proposal-limit", type=int, default=10)
    parser.add_argument("--max-offset", type=int, default=500)
    parser.add_argument("--probe-workers", type=int, default=8)
    args = parser.parse_args()

    state = _state()
    scan_fresh = bool(state.get("scan_fresh_next", True))
    backlog_offset = max(
        int(args.scan_limit),
        int(
            state.get("backlog_offset")
            or state.get("next_offset")
            or args.scan_limit
        ),
    )
    offset = 0 if scan_fresh else backlog_offset
    deferred_queue = BuyerDeferredEnrichmentQueue()
    result = run_buyer_review_materializer(
        defer=deferred_queue.enqueue,
        scan_limit=args.scan_limit,
        proposal_limit=args.proposal_limit,
        scan_offset=offset,
        probe_workers=args.probe_workers,
    )
    payload = result.as_dict()
    payload["scan_offset"] = offset
    payload["mode"] = "INTERNAL_MATERIALIZE"
    payload["owner"] = "astra"

    payload["artifact_materialization"] = (
        materialize_solar_maps_for_review_outcomes(
            result.outcomes,
        )
    )

    bridge = run_standing_bridge(
        review_limit=min(50, max(10, int(args.proposal_limit) * 2)),
        outbound_limit=min(50, max(10, int(args.proposal_limit) * 2)),
        daily_cap=10,
    )
    payload["standing_bridge"] = bridge.as_dict()
    payload["ok"] = (
        not payload["errors"]
        and not payload["standing_bridge"]["outbound_errors"]
    )
    _write(LATEST, payload)

    next_scan_fresh = not scan_fresh
    next_backlog = backlog_offset
    if not scan_fresh:
        next_backlog += max(1, int(args.scan_limit))
        if next_backlog > max(0, int(args.max_offset)):
            next_backlog = max(1, int(args.scan_limit))
    next_offset = 0 if next_scan_fresh else next_backlog
    _write(
        STATE,
        {
            "next_offset": next_offset,
            "backlog_offset": next_backlog,
            "scan_fresh_next": next_scan_fresh,
            "last_offset": offset,
            "last_ok": payload["ok"],
            "last_proposed": payload["proposed"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
