#!/usr/bin/env python3
"""CLI wrapper for the read-only Phase 4 Astra observer."""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.astra_observer import (
    AstraObserverError,
    run_observer_cycle,
)
from empire_os.outcome_role_transport import OutcomeTransportError


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire Phase 4 Astra observer")
    p.add_argument("--limit", type=int, default=_env_int("EMPIRE_ASTRA_FEEDBACK_LIMIT", 100))
    p.add_argument("--min-samples", type=int, default=_env_int("EMPIRE_ASTRA_MIN_OUTCOME_SAMPLES", 20))
    p.add_argument("--min-conversions", type=int, default=_env_int("EMPIRE_ASTRA_MIN_CONVERSIONS", 5))
    p.add_argument(
        "--mode",
        default=os.getenv("EMPIRE_ASTRA_MODE", "OBSERVE"),
    )
    p.add_argument(
        "--output",
        default=os.getenv(
            "EMPIRE_ASTRA_OUTPUT_PATH",
            "/srv/empire_os/runtime/astra/latest.json",
        ),
    )
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    payload = run_observer_cycle(
        dsn=os.getenv("EMPIRE_ASTRA_OBSERVER_DSN", ""),
        mode=args.mode,
        feedback_limit=args.limit,
        min_samples=args.min_samples,
        min_conversions=args.min_conversions,
        operational_snapshot_json=os.getenv(
            "EMPIRE_ASTRA_OPERATIONAL_SNAPSHOT_JSON"
        ),
        output_path=args.output,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AstraObserverError, OutcomeTransportError, ValueError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}),
            file=sys.stderr,
        )
        raise SystemExit(2)
