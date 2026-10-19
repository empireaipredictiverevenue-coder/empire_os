"""Read-only USB market archives preflight: never sends source data anywhere."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.legacy_market_archive_review_20261019 import (
    review_expected_value_csv, review_metro_json,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--metro-json", type=Path)
    parser.add_argument("--expected-value-csv", type=Path)
    args = parser.parse_args(argv)
    if not args.metro_json and not args.expected_value_csv:
        parser.error("one historical offline archive path is required")
    data = {}
    try:
        if args.metro_json:
            data["metro"] = review_metro_json(args.metro_json)
        if args.expected_value_csv:
            data["expected_value"] = review_expected_value_csv(args.expected_value_csv)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print(json.dumps({
            "schema_version": "empire.legacy_market_archive_cli.v1",
            "state": "HOLD_UNTRUSTED_OR_UNAVAILABLE_ARCHIVE",
            "raw_source_exported": False, "database_writes": False,
            "outbound_authorized": False, "execution_authority": "none",
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema_version": "empire.legacy_market_archive_cli.v1",
        "state": "OFFLINE_HISTORICAL_RESEARCH_CENSUS",
        "reviews": data,
        "raw_source_exported": False,
        "canonical_empiredb_writes": False,
        "buyer_or_subscriber_status_promoted": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
