"""Read the existing Buyer Acquisition Scout snapshot and rank B2B research.

This is a one-shot OFFLINE sniper review on already captured public B2B data.
Does not start the legacy Lead Sniper daemon, scanner HTTP fetch, mail, DB,
money transfer, or systemd service. Does not alter scout JSON in place.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from empire_os.revenue_sniper_scanner_review import review_existing_scout_snapshot

MAX_FILE_BYTES = 2_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument(
        "--scout-snapshot", type=Path, required=True,
        help="Existing local runtime/buyer_acquisition/scout_latest.json",
    )
    args = parser.parse_args(argv)
    try:
        p = args.scout_snapshot
        if not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("missing_or_unbounded_snapshot")
        snapshot = json.loads(p.read_text(encoding="utf-8"))
        report = review_existing_scout_snapshot(snapshot)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["source_snapshot_fresh_under_24h"] else 2
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({
            "schema_version": "empire.revenue_scanner_sniper_review.v1",
            "mode": "READ_ONLY_EXISTING_SCANNER_SNAPSHOT",
            "state": "HOLD", "error_class": type(exc).__name__,
            "execution_authority": "none", "outbound_authorized": False,
            "canonical_database_writes": False,
        }))
        return 2


if __name__ == "__main__":
    sys.exit(main())
