#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.lead_smart_coverage_observer import (
    observe,
    write_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-root",
        default=(
            "runtime/revenue/lead_smart/"
            "coverage"
        ),
    )

    args = parser.parse_args()

    root = Path(args.output_root)
    latest = root / "latest.json"

    previous = None

    if latest.exists():
        previous = json.loads(
            latest.read_text()
        )

    snapshot = observe(
        previous=previous,
    )

    snapshot_path, latest_path = write_snapshot(
        snapshot,
        output_root=root,
    )

    summary = {
        "schema_version":
            snapshot["schema_version"],
        "mode":
            snapshot["mode"],
        "observed_at":
            snapshot["observed_at"],
        "offer_key":
            snapshot["canonical_vertical"]["offer_key"],
        "vertical_slug":
            snapshot["canonical_vertical"]["slug"],
        "vertical_enabled":
            snapshot["canonical_vertical"]["enabled"],
        "row_count":
            snapshot["coverage"]["row_count"],
        "unique_zip_count":
            snapshot["coverage"]["unique_zip_count"],
        "duration_payout":
            snapshot["coverage"]["duration_payout"],
        "cpl_payout":
            snapshot["coverage"]["cpl_payout"],
        "top_payout":
            snapshot["coverage"]["top_payout"],
        "oldest_age_seconds":
            snapshot["coverage"]["oldest_age_seconds"],
        "newest_age_seconds":
            snapshot["coverage"]["newest_age_seconds"],
        "source_hash":
            snapshot["source_hash"],
        "delta":
            snapshot["delta"],
        "authority":
            snapshot["authority"],
        "snapshot_path":
            str(snapshot_path),
        "latest_path":
            str(latest_path),
    }

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
