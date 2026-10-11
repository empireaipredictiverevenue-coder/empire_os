#!/usr/bin/env python3
"""Refresh the commercial-loop read model from canonical evidence only."""
from __future__ import annotations

import argparse
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from empire_os.commercial_loop_observer import (
    CommercialLoopObservation,
    assess_commercial_loop,
    fetch_canonical_commercial_observations,
    write_commercial_loop_snapshot,
)
from empire_os.sb import request_json
from empire_os.canonical_data_gateway import DataGatewayUnavailable, DataGatewayOperationUnsupported
from empire_os.commercial_loop_reader import read_commercial_loop, CommercialLoopReadError
from empire_os.commercial_loop_refresh_contract import preserve_cycle_local_observations
from empire_os.commercial_evidence_inventory import fetch_qualification_omega_inventory
SNAPSHOT = Path("/srv/empire_os/runtime/commercial_loop/latest.json")


def _existing() -> dict[str, CommercialLoopObservation]:
    try:
        payload = read_commercial_loop(SNAPSHOT)
    except CommercialLoopReadError:
        return {}

    observations: dict[str, CommercialLoopObservation] = {}
    for row in payload.get("stages") or []:
        if not isinstance(row, dict):
            continue
        stage = str(row.get("stage") or "").strip()
        if not stage:
            continue
        observations[stage] = CommercialLoopObservation(
            stage=stage,
            observed=row.get("observed"),
            evidence_ref=row.get("evidence_ref"),
            detail=row.get("detail"),
        )
    return observations


def _reader(path: str, params: dict[str, str]):
    query = urllib.parse.urlencode(params)
    return request_json("GET", f"{path}?{query}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Refresh or preview OBSERVE commercial loop')
    parser.add_argument('--dry-run', action='store_true', help='read-only preview; never write runtime snapshot')
    args = parser.parse_args(argv)
    existing = _existing()
    try:
        canonical = fetch_canonical_commercial_observations(
            _reader,
            now=datetime.now(timezone.utc),
        )
    except (DataGatewayUnavailable, DataGatewayOperationUnsupported) as exc:
        if not args.dry_run:
            raise
        print(json.dumps({
            'mode': 'OBSERVE', 'dry_run': True,
            'snapshot_written': False, 'verified': False,
            'reason': 'canonical_reader_unavailable',
            'error_type': type(exc).__name__,
        }, sort_keys=True))
        return 2
    observations = preserve_cycle_local_observations(existing, canonical)
    # Inventory is authoritative for durable local stages, not cycle activity.
    observations.update(fetch_qualification_omega_inventory(_reader))
    status = assess_commercial_loop(observations)
    if not args.dry_run:
        write_commercial_loop_snapshot(status)
    print(json.dumps(status.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
