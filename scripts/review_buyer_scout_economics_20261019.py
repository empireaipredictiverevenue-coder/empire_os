"""Economics-first read-only gap board over existing Scout and CRM receipts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from empire_os.buyer_scout_commercial_awareness import review_buyer_scout_awareness
from empire_os.buyer_scout_economic_intelligence import build_buyer_economic_gap_review
from scripts.review_buyer_scout_commercial_awareness_20261019 import (
    SCOUT, ACTIONS, RELATIONSHIPS, _load, ROOT,
)

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        now = datetime.now(timezone.utc)
        scout = _load(args.runtime_root, SCOUT)
        actions = _load(args.runtime_root, ACTIONS)
        registry = _load(args.runtime_root, RELATIONSHIPS)
        awareness = review_buyer_scout_awareness(
            scout, actions, registry, as_of=now)
        report = build_buyer_economic_gap_review(
            awareness, registry, as_of=now)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        print(json.dumps({
            "schema_version": "empire.buyer_scout_economic_gap_review.v1",
            "state": "HOLD_UNVERIFIED_SNAPSHOT_OR_ECONOMICS",
            "verified_paying_buyer_capacity": 0,
            "outbound_authorized": False, "canonical_empiredb_writes": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
