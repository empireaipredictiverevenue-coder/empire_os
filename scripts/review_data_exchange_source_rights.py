"""OBSERVE-only source rights preflight: no networking, sends or DB writes.

Reads already generated official-source snapshots and optional procurement
projection. Emits a JSON field-lineage and rights checklist for independent
review, not a rights approval or commercial distribution grant.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_rights_preflight import build_rights_preflight
from scripts.review_construction_history import read_bounded_snapshot
from scripts.review_data_exchange_agi import _procurement


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", required=True, nargs="+", type=Path)
    parser.add_argument("--procurement", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if not 2 <= len(args.snapshots) <= 16:
            raise ValueError("source-rights review requires bounded observations")
        packet = build_rights_preflight(
            source_snapshots=[read_bounded_snapshot(p) for p in args.snapshots],
            procurement=_procurement(args.procurement),
            assessed_at=datetime.now(timezone.utc),
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "HOLD",
            "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "data_resale_authorized": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(packet, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
