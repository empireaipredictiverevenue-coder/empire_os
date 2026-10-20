#!/usr/bin/env python3
"""Manual read-only casebook: original outreach thread evidence, NO sending."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.commercial_conversation_casebook import review_conversion_casebook
from empire_os.commercial_shadow_offer_reconstruction import (
    reconstruct_in_memory_offer_book,
    review_shadow_offer_reconstruction,
)
from empire_os.revenue_distribution_review import REVIEW_SOURCES

MAX_BYTES = 3_000_000


def _read(path: Path):
    p = path.resolve(strict=True)
    if not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError("source must be a bounded JSON file")
    return json.loads(p.read_text(encoding="utf-8"))


def build_casebook_runtime(root: Path, *, now: datetime):
    """Compose owner packet readers in memory, without new jobs or file writes."""
    catalog = _read(root / "runtime/commercial_catalog/latest.json")
    distribution = _read(root / "runtime/revenue_distribution/latest.json")
    previous = _read(root / "runtime/predictive_revenue/commercial_offer_book/latest.json")
    recovery = _read(root / "runtime/conversation_recovery/latest.json")
    sources = {}
    for label, rel in REVIEW_SOURCES.items():
        try:
            sources[label] = _read(root / rel)
        except (OSError, ValueError, json.JSONDecodeError):
            sources[label] = None
    health = review_shadow_offer_reconstruction(
        catalog=catalog, distribution=distribution, review_sources=sources,
        previous_offer_book=previous, now=now,
    )
    book = reconstruct_in_memory_offer_book(
        catalog=catalog, distribution=distribution,
        review_sources=sources, now=now,
    )
    return review_conversion_casebook(
        offer_book=book, conversation_recovery=recovery,
        source_health=health, now=now,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only existing Sales Director conversation conversion review"
    )
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve(strict=True)
    report = build_casebook_runtime(root, now=datetime.now(timezone.utc))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
