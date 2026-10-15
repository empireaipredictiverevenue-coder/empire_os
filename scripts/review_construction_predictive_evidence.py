"""Manual read-only construction forecast/outcome readiness review.

Usage: python -m scripts.review_construction_predictive_evidence
  --snapshots /tmp/observation1.json /tmp/observation2.json
  --tenant-id example-internal-tenant

Without --pairs there is NEVER a claim of verified forecasts or sales.
If provided, --pairs JSON must be an array of canonical verified
prediction/feedback objects. Do not use this CLI as data export.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_predictive_review import (
    review_construction_prediction_cohort,
)
from scripts.review_construction_history import read_bounded_snapshot

MAX_PAIR_BYTES = 512_000


def read_pairs(path: Path | None) -> list:
    if path is None:
        return []
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PAIR_BYTES:
        raise ValueError("canonical pairs file absent, link or oversized")
    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, list):
        raise ValueError("canonical pairs must be a JSON list")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, required=True, nargs="+")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--pairs", type=Path)
    args = parser.parse_args(argv)
    try:
        if not 2 <= len(args.snapshots) <= 16:
            raise ValueError("requires 2..16 source snapshots")
        review = review_construction_prediction_cohort(
            source_snapshots=[read_bounded_snapshot(f) for f in args.snapshots],
            pairs=read_pairs(args.pairs),
            tenant_id=args.tenant_id,
            assessed_at=datetime.now(timezone.utc),
        )
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            json.JSONDecodeError) as exc:
        # No raw source, private feedback, paths, passwords or contact data.
        print(json.dumps({
            "review_status": "HOLD", "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(review, sort_keys=True))
    return 0 if review["review_status"] != "HOLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
