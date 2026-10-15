"""Read-only historical evidence verification for Construction Signals.

Examples:
    python -m scripts.review_construction_history --snapshots /tmp/a.json /tmp/b.json
    python -m scripts.review_construction_history --snapshots /tmp/a.json /tmp/b.json --expected-chain-sha256 HASH

Prints result to stdout. No DB, recording service, customer export,
payments, contacts, publishing, source fetching or automated execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_history import build_construction_history

MAX_BYTES = 2 * 1024 * 1024


def read_bounded_snapshot(path: Path) -> dict:
    # Symlink rejection prevents reading protected files via an input alias.
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("file absent, symbolic link, or over size limit")
    with path.open("r", encoding="utf-8") as handle:
        result = json.load(handle)
    if not isinstance(result, dict):
        raise ValueError("snapshot must be a JSON object")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", required=True, type=Path, nargs="+")
    parser.add_argument("--expected-chain-sha256", default=None)
    args = parser.parse_args(argv)
    try:
        if not 2 <= len(args.snapshots) <= 16:
            raise ValueError("bounded history requires 2..16 input paths")
        result = build_construction_history(
            [read_bounded_snapshot(path) for path in args.snapshots],
            assessed_at=datetime.now(timezone.utc),
        )
        if args.expected_chain_sha256 is not None and (
            args.expected_chain_sha256 != result["latest_chain_sha256"]
        ):
            raise ValueError("independent expected history hash mismatch")
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            json.JSONDecodeError) as exc:
        print(json.dumps({
            "assessment_status": "HOLD",
            "error_type": type(exc).__name__,
            "execution_authority": "NONE",
            "customer_delivery_enabled": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
