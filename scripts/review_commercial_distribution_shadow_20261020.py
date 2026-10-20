#!/usr/bin/env python3
"""Manual, aggregate-only dry-run of owner Revenue Distribution from source JSON."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_distribution_shadow_refresh import (
    shadow_distribution_refresh_review,
)
from empire_os.revenue_distribution import SOURCES

MAX_SOURCE_BYTES = 3_000_000


def _read(path: Path):
    target = path.resolve(strict=True)
    if not target.is_file() or target.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("source file must be bounded JSON")
    return json.loads(target.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline read-only Revenue Distribution source freshness review"
    )
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve(strict=True)
    prior = _read(root / "runtime/revenue_distribution/latest.json")
    data = {}
    for name, relative in SOURCES.items():
        try:
            data[name] = _read(root / relative)
        except (OSError, ValueError, json.JSONDecodeError):
            data[name] = None
    report = shadow_distribution_refresh_review(
        source_snapshots=data,
        previous_distribution=prior,
        now=datetime.now(timezone.utc),
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
