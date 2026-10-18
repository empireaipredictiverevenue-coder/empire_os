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
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UK public OCDS single-page incremental source review",
    )
    parser.add_argument(
        "--stage-private-checkpoint", action="store_true",
        help="Explicitly stage one private feature-worktree cursor checkpoint",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
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
