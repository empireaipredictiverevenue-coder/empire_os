#!/usr/bin/env python3
"""CLI wrapper for the Phase 3E governed closer observer."""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.closer_observer import (
    CloserObserverError,
    run_closer_observer_cycle,
)
from empire_os.closer_role_transport import CloserTransportError


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire governed closer observer")
    p.add_argument(
        "--mode",
        default=os.getenv("EMPIRE_CLOSER_MODE", "OBSERVE"),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=_env_int("EMPIRE_CLOSER_WORK_LIMIT", 50),
    )
    p.add_argument(
        "--output",
        default=os.getenv(
            "EMPIRE_CLOSER_OUTPUT_PATH",
            "/srv/empire_os/runtime/closer/latest.json",
        ),
    )
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    payload = run_closer_observer_cycle(
        dsn=os.getenv("EMPIRE_CLOSER_OBSERVER_DSN", ""),
        mode=args.mode,
        limit=args.limit,
        output_path=args.output,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloserObserverError, CloserTransportError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
