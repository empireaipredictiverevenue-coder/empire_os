#!/usr/bin/env python3
"""Run isolated commercial shadow check. Never invoke the production producer."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_shadow_offer_reconstruction import (
    review_shadow_offer_reconstruction,
)
from empire_os.revenue_distribution_review import REVIEW_SOURCES

MAX_BYTES = 3_000_000


def _read(path: Path):
    target = path.resolve(strict=True)
    if not target.is_file() or target.stat().st_size > MAX_BYTES:
        raise ValueError("source must be a bounded JSON file")
    return json.loads(target.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Memory-only commercial offer-book reconstruction and provenance gate"
    )
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve(strict=True)
    inputs = {
        "catalog": _read(root / "runtime/commercial_catalog/latest.json"),
        "distribution": _read(root / "runtime/revenue_distribution/latest.json"),
        "previous_offer_book": _read(
            root / "runtime/predictive_revenue/commercial_offer_book/latest.json"
        ),
    }
    review = {}
    for name, rel in REVIEW_SOURCES.items():
        try:
            review[name] = _read(root / rel)
        except (OSError, ValueError, json.JSONDecodeError):
            review[name] = None  # Explicitly gates readiness: no silent source success.

    packet = review_shadow_offer_reconstruction(
        **inputs, review_sources=review, now=datetime.now(timezone.utc)
    )
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
