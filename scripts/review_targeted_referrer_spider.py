#!/usr/bin/env python3
"""Founder review CLI for a one-shot, guarded source-page crawler.

No live crawl unless --crawl-once, --approve-bounded-public-reads and explicit
source hosts all match the immutable historical graph review queue.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time
from hashlib import sha256

from empire_os.search_intelligence.targeted_referrer_spider import (
    SpiderHeld, plan_from_review, crawl_pilot,
)
from empire_os.search_intelligence.historical_spider_seeds import add_wat_page_seeds

MAX_INPUT = 2_000_000


def main():
    p = argparse.ArgumentParser()
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--review-only", action="store_true")
    modes.add_argument("--crawl-once", action="store_true")
    p.add_argument("--historical-review", type=Path, required=True)
    p.add_argument("--wat-evidence", type=Path,
                   help="Optional existing local WAT receipt for exact historical page seeds")
    p.add_argument("--source-host", action="append", default=[])
    p.add_argument("--approve-bounded-public-reads", action="store_true")
    p.add_argument("--private-receipt", type=Path)
    args = p.parse_args()
    try:
        f = args.historical_review
        if f.is_symlink() or not f.is_file() or not 0 < f.stat().st_size <= MAX_INPUT:
            raise SpiderHeld("bounded_graph_review_file_required")
        raw = f.read_bytes()
        review = json.loads(raw)
        plan = plan_from_review(review, tuple(args.source_host))
        if args.wat_evidence is not None:
            w = args.wat_evidence
            if w.is_symlink() or not w.is_file() or not 0 < w.stat().st_size <= MAX_INPUT:
                raise SpiderHeld("bounded_wat_evidence_file_required")
            plan = add_wat_page_seeds(plan, json.loads(w.read_bytes()))
        if args.review_only:
            visible = {k: v for k, v in plan.items() if k != "historical_page_seeds"}
            print(json.dumps({**visible, "historical_review_sha256": sha256(raw).hexdigest()}, sort_keys=True))
            return 0
        if (not args.approve_bounded_public_reads or not args.source_host
                or args.private_receipt is None):
            raise SpiderHeld("explicit_one_shot_public_read_and_receipt_required")
        dest = args.private_receipt
        if (dest.exists() or dest.is_symlink() or not dest.parent.is_dir()
                or dest.parent.stat().st_mode & 0o077):
            raise SpiderHeld("exclusive_private_evidence_destination_required")
        from empire_os.search_intelligence.backlink_live_verifier import PublicHttpsFetcher
        result = crawl_pilot(plan, fetch=PublicHttpsFetcher(timeout=5), wait=time.sleep)
        result["historical_review_sha256"] = sha256(raw).hexdigest()
        result["source_plan"] = plan
        result_bytes = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
        fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(result_bytes)
            output.flush()
            os.fsync(output.fileno())
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("evidence", "source_plan")}, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "TARGETED_SPIDER_HELD",
            "reason": str(exc) if isinstance(exc, SpiderHeld) else type(exc).__name__,
            "success_not_claimed": True,
            "empiredb_writes": False,
            "paid_api_calls": 0,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
