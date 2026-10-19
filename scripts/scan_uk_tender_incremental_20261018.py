#!/usr/bin/env python3
"""Single-page public procurement change miner; review-only by default.

--stage-private-checkpoint persists only into THIS FEATURE WORKTREE's private
runtime directory. It never uses the production source/DB or performs sending,
contact extraction, autonomous polling, bidding or provider payments.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.uk_tender_incremental import (
    TenderIncrementalHold, advance_private_checkpoint,
    deliver_one_pending_sector_review, review_incremental_checkpoint,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UK public OCDS single-page incremental source review",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--stage-private-checkpoint", action="store_true",
        help="Explicitly stage one private feature-worktree cursor checkpoint",
    )
    action.add_argument(
        "--enqueue-one-sector-review", action="store_true",
        help="Route one existing staged source proof to ASTRA for internal review",
    )
    action.add_argument(
        "--checkpoint-health", action="store_true",
        help="Read private source progress without network or queue activity",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.checkpoint_health:
        print(json.dumps(review_incremental_checkpoint(
            root, as_of=datetime.now(timezone.utc)), indent=2, sort_keys=True))
        return 0
    if args.enqueue_one_sector_review:
        result = deliver_one_pending_sector_review(
            root, as_of=datetime.now(timezone.utc), apply=True,
            department_repo_root=Path("/srv/empire_os"),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    try:
        result = advance_private_checkpoint(
            root, as_of=datetime.now(timezone.utc),
            apply=args.stage_private_checkpoint,
        )
    except (TenderIncrementalHold, ValueError) as exc:
        # Avoid surfacing untrusted raw provider content.
        print(json.dumps({
            "status": "SOURCE_REVIEW_HELD",
            "reason_type": type(exc).__name__,
            "reason": str(exc)[:180],
            "source_high_watermark_advanced": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
