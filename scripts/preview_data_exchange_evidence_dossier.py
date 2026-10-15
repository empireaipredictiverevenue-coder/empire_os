"""Build a strictly internal source-linked construction buyer-validation sample.

Use previously obtained public source snapshots; no source HTTP requests.
Outputs JSON to stdout only. Never serve the preview to customers or export
it commercially without independent rights review and explicit approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_evidence_dossier import (
    build_internal_construction_dossier,
)
from scripts.review_construction_history import read_bounded_snapshot
from scripts.review_data_exchange_agi import _procurement


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", nargs="+", type=Path, required=True)
    parser.add_argument("--procurement", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        if not 2 <= len(args.snapshots) <= 16:
            raise ValueError("bounded source history requires 2..16 snapshots")
        result = build_internal_construction_dossier(
            snapshots=[read_bounded_snapshot(p) for p in args.snapshots],
            procurement=_procurement(args.procurement),
            reviewed_at=datetime.now(timezone.utc),
            max_sample=args.limit,
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "HOLD", "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
