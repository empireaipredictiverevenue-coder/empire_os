#!/usr/bin/env python3
"""One read-only commercial decision review across EXISTING source owners.

Reuses pure owner modules. This does not create another agent, scheduler,
revenue projection, buyer list, model learner or activation workflow.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_adaptive_intelligence_control import (
    review_adaptive_commercial_intelligence,
)
from empire_os.commercial_sales_director_adaptive_review import (
    adaptive_original_proof_review,
)
from empire_os.commercial_shadow_offer_reconstruction import (
    review_shadow_offer_reconstruction,
)
from empire_os.commercial_distribution_shadow_refresh import (
    shadow_distribution_refresh_review,
)
from empire_os.revenue_distribution import SOURCES
from empire_os.revenue_distribution_review import REVIEW_SOURCES
from scripts.review_sales_director_original_proof_20261020 import (
    build_original_proof_runtime,
)

MAX_FILE_SIZE = 3_000_000
MAX_PREVIOUS_SIZE = 80_000


def _bounded_json(path: Path, *, max_bytes: int = MAX_FILE_SIZE):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("source is not a bounded original JSON file")
    return json.loads(path.read_text(encoding="utf-8"))


def _previous(filename: str | None):
    if filename is None:
        return None
    return _bounded_json(Path(filename), max_bytes=MAX_PREVIOUS_SIZE)


def build_adaptive_commercial_runtime(
    root: Path, *,
    now: datetime,
    previous_sales: dict | None,
    previous_control: dict | None,
):
    """Pure read-only owner composition, no database, mailbox API or writes."""
    original_sales = build_original_proof_runtime(root, now=now)
    sales = adaptive_original_proof_review(
        current=original_sales, previous=previous_sales,
        source_receipts=None, now=now,
    )
    catalog = _bounded_json(root / "runtime/commercial_catalog/latest.json")
    distribution_file = _bounded_json(root / "runtime/revenue_distribution/latest.json")
    previous_book = _bounded_json(
        root / "runtime/predictive_revenue/commercial_offer_book/latest.json"
    )
    owner_reviews = {}
    for name, rel in REVIEW_SOURCES.items():
        try:
            owner_reviews[name] = _bounded_json(root / rel)
        except (OSError, ValueError, json.JSONDecodeError):
            owner_reviews[name] = None
    offers = review_shadow_offer_reconstruction(
        catalog=catalog, distribution=distribution_file,
        review_sources=owner_reviews, previous_offer_book=previous_book,
        now=now,
    )
    original_distribution_sources = {}
    for name, rel in SOURCES.items():
        try:
            original_distribution_sources[name] = _bounded_json(root / rel)
        except (OSError, ValueError, json.JSONDecodeError):
            original_distribution_sources[name] = None
    distribution = shadow_distribution_refresh_review(
        source_snapshots=original_distribution_sources,
        previous_distribution=distribution_file, now=now,
    )
    return review_adaptive_commercial_intelligence(
        sales=sales, offers=offers, distribution=distribution,
        previous=previous_control, now=now,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manual read-only commercial adaptive dependency graph"
    )
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--previous-sales-review-file")
    parser.add_argument("--previous-commercial-review-file")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve(strict=True)
    report = build_adaptive_commercial_runtime(
        root, now=datetime.now(timezone.utc),
        previous_sales=_previous(args.previous_sales_review_file),
        previous_control=_previous(args.previous_commercial_review_file),
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
