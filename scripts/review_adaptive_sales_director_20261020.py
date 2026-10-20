#!/usr/bin/env python3
"""Non-executing adaptive review via the original Sales Director owner reader.

Replays compare a caller-supplied previous privacy-safe report. The existing
orchestrator owns durable state and schedules; this tool creates neither.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from empire_os.commercial_sales_director_adaptive_review import (
    adaptive_original_proof_review,
)
from scripts.review_sales_director_original_proof_20261020 import (
    build_original_proof_runtime,
)


def _read_previous(filename: str):
    if filename == "-":
        source = sys.stdin.buffer.read(40001)
        if len(source) > 40000:
            raise ValueError("prior review exceeds size limit")
        packet = json.loads(source)
    else:
        path = Path(filename)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 40000:
            raise ValueError("bounded private prior review file required")
        packet = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise ValueError("prior review root must be an object")
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Review changed sales proof and suppress repeated holds")
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--previous-review-file")
    parser.add_argument("--owner-source-receipts-file")
    args = parser.parse_args()
    if args.previous_review_file == "-" and args.owner_source_receipts_file == "-":
        parser.error("only one source may use stdin")
    root = Path(args.repo_root).resolve(strict=True)
    previous = _read_previous(args.previous_review_file) if args.previous_review_file else None
    receipts = _read_previous(args.owner_source_receipts_file) if args.owner_source_receipts_file else None
    now = datetime.now(timezone.utc)
    evidence = build_original_proof_runtime(root, now=now)
    review = adaptive_original_proof_review(
        current=evidence, previous=previous,
        source_receipts=receipts, now=now,
    )
    print(json.dumps(review, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
