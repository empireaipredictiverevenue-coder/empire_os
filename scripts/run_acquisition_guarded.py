#!/usr/bin/env python3
"""Guarded acquisition entrypoint for the normal post-soak scheduler.

While the temporary 24-hour acquisition benchmark is still inside its original
expiry window, this worker exits cleanly without crawling. Once the expiry has
passed, it runs one bounded adaptive acquisition cycle.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scripts.run_acquisition_cycle import run_cycle

ROOT = Path("/srv/empire_os")
SOAK_EXPIRY = ROOT / "runtime" / "acquisition" / "soak_24h.expires"


def soak_active(*, now_epoch: int | None = None, expiry_path: Path = SOAK_EXPIRY) -> tuple[bool, int | None]:
    current = int(time.time()) if now_epoch is None else int(now_epoch)
    try:
        expiry = int(expiry_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False, None
    return current < expiry, expiry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-candidates", type=int, default=10)
    args = parser.parse_args()
    if args.max_candidates < 1 or args.max_candidates > 25:
        parser.error("--max-candidates must be between 1 and 25")

    active, expiry = soak_active()
    if active:
        print(json.dumps({
            "schema_version": "empire.acquisition-guard.v1",
            "decision": "SOAK_ACTIVE_SKIP",
            "soak_expires_epoch": expiry,
            "adaptive_acquisition_ran": False,
            "outbound_enabled": False,
            "payment_enabled": False,
        }, indent=2))
        return 0

    result = run_cycle(max_candidates=args.max_candidates)
    print(json.dumps({
        "schema_version": "empire.acquisition-guard.v1",
        "decision": "ACQUISITION_CYCLE",
        "adaptive_acquisition_ran": True,
        "result": result,
    }, indent=2))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
