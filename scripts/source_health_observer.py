#!/usr/bin/env python3
"""Bounded, no-write source-health observation for Phase 4."""
from __future__ import annotations

import argparse
import json
import os
import signal

from empire_os.lead_sources import overpass
from empire_os.source_health_observer import (
    atomic_write_observation,
    observe_source_health,
)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _timeout(_signum, _frame):
    raise TimeoutError("source health probe exceeded bounded timeout")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="overpass")
    p.add_argument("--metro", default="Austin, TX")
    p.add_argument("--max-candidates", type=int, default=5)
    p.add_argument(
        "--output",
        default="/srv/empire_os/runtime/source_health/latest.json",
    )
    p.add_argument("--timeout-seconds", type=int, default=90)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.source != "overpass":
        raise SystemExit("only the observed Overpass source is enabled")
    if args.timeout_seconds < 1:
        raise SystemExit("timeout must be positive")

    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(args.timeout_seconds)
    try:
        observation = observe_source_health(
            source="overpass",
            metro=args.metro,
            runner=overpass.run,
            max_candidates=args.max_candidates,
            canonical_ingest_authorized=_bool_env(
                "EMPIRE_CANONICAL_ACQUISITION_AUTHORIZED"
            ),
            canonical_ingest_scheduled=_bool_env(
                "EMPIRE_CANONICAL_ACQUISITION_SCHEDULED"
            ),
        )
    finally:
        signal.alarm(0)


    atomic_write_observation(args.output, observation)
    payload = {
        "mode": "OBSERVE",
        "side_effects": "none",
        "canonical_writes": False,
        "observation": observation.as_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if observation.endpoint_healthy else 2


if __name__ == "__main__":
    raise SystemExit(main())
