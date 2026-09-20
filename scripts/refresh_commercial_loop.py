#!/usr/bin/env python3
"""Refresh the commercial-loop read model from canonical evidence only."""
from __future__ import annotations

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
from empire_os.qualification_worker_v2 import request_json

SNAPSHOT = Path("/srv/empire_os/runtime/commercial_loop/latest.json")


def _existing() -> dict[str, CommercialLoopObservation]:
    try:
        payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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


def main() -> int:
    observations = _existing()
    observations.update(
        fetch_canonical_commercial_observations(
            _reader,
            now=datetime.now(timezone.utc),
        )
    )
    status = assess_commercial_loop(observations)
    write_commercial_loop_snapshot(status)
    print(json.dumps(status.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
