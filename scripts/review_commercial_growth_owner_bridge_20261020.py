#!/usr/bin/env python3
"""Manually compose EXISTING owner evidence with commercial growth, read-only.

If --buyer-development-review-file - is supplied, consume JSON on stdin
from the independently owned BD desk CLI. No subprocesses or jobs are launched.
No filesystem writes, DB reads, network calls, CRM access or outbound.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from empire_os.commercial_growth_existing_owner_review import (
    review_existing_owner_handoff,
)
from empire_os.video_commercial_growth_framework import (
    build_commercial_growth_review,
)

MAX_PACKET_BYTES = 3_000_000


def _load_json(*, filename: str) -> Mapping:
    if filename == "-":
        content = sys.stdin.buffer.read(MAX_PACKET_BYTES + 1)
        if len(content) > MAX_PACKET_BYTES:
            raise ValueError("BD stdin exceeds packet size limit")
        document = json.loads(content)
    else:
        path = Path(filename).resolve(strict=True)
        if not path.is_file() or path.stat().st_size > MAX_PACKET_BYTES:
            raise ValueError("input must be a bounded JSON file")
        document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("input JSON root must be an object")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only cross-team revenue framework diagnosis"
    )
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--observations-file", required=True)
    parser.add_argument("--offer-book-file", required=True)
    parser.add_argument("--funnel-file", required=True)
    parser.add_argument("--buyer-development-review-file", required=True)
    args = parser.parse_args()
    if args.buyer_development_review_file == "-" and "-" in (
        args.observations_file,
        args.offer_book_file,
        args.funnel_file,
    ):
        parser.error("only BD review may be piped from stdin")

    growth = build_commercial_growth_review(
        observations=_load_json(filename=args.observations_file),
        offer_book=_load_json(filename=args.offer_book_file),
        funnel=_load_json(filename=args.funnel_file),
    )
    combined = review_existing_owner_handoff(
        commercial=growth,
        buyer_development=_load_json(filename=args.buyer_development_review_file),
    )
    print(json.dumps(combined, indent=2, sort_keys=True, ensure_ascii=False))
    return 0  # A source hold is a valid, safely reported review outcome.


if __name__ == "__main__":
    raise SystemExit(main())
