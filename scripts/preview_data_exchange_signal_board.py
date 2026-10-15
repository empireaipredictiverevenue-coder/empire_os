"""One-shot internal verified construction-change board from existing snapshots.

Read-only: no GET, no database, no API server, no mail, no external export.
Original official-source observations must be supplied as bounded local JSON.
A government source record change is NOT a verified project or buyer signal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_signal_board import build_signal_board
from scripts.review_construction_history import read_bounded_snapshot
from scripts.review_data_exchange_agi import _procurement


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots", nargs="+", required=True, type=Path)
    p.add_argument("--procurement", type=Path, default=None)
    p.add_argument("--limit", type=int, default=24)
    args = p.parse_args(argv)
    try:
        if not 2 <= len(args.snapshots) <= 16:
            raise ValueError("BOUNDED_SOURCE_SNAPSHOTS_REQUIRED")
        result = build_signal_board(
            source_snapshots=[
                read_bounded_snapshot(f) for f in args.snapshots
            ],
            procurement=_procurement(args.procurement),
            assessed_at=datetime.now(timezone.utc),
            limit=args.limit,
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "schema_version": "empire.data_exchange.signal_board.v14",
            "feed_status": "HOLD_INVALID_OR_UNVERIFIED_SOURCE",
            "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "data_resale_authorized": False,
            "outbound_enabled": False,
            "payment_execution": False,
            "production_writes": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
