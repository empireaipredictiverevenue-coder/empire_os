"""Compare two local, non-commercial OBSERVE snapshot JSON files.

This manual forensic utility performs NO fetches, writes, email, DB work,
payment operations or publication. Generated report goes to stdout only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_change_intelligence import (
    assess_construction_changes,
)

MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024


def read_snapshot(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot missing or too large")
    with path.open("r", encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError("snapshot is not an object")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = assess_construction_changes(
            read_snapshot(args.before),
            read_snapshot(args.after),
            assessed_at=datetime.now(timezone.utc),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "assessment_status": "HOLD", "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["assessment_status"] != "HOLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
