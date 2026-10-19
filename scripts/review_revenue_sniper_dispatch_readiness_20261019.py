"""Cross-check existing scanner, buyer review and EmpireDB Exchange snapshots.

Read-only. Expects locally existing bounded files; NEVER launches agents,
queries EmpireDB, changes timers, writes tasks or sends any external traffic.

Usage:
 python -m scripts.review_revenue_sniper_dispatch_readiness_20261019 \
   --read-only \
   --scout runtime/buyer_acquisition/scout_latest.json \
   --review runtime/buyer_acquisition/review_readiness_latest.json \
   --exchange runtime/commercial_exchange/latest.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.revenue_sniper_dispatch_readiness import build_sniper_dispatch_readiness

LIMIT_BYTES = 2_000_000


def _read_snapshot(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > LIMIT_BYTES:
        raise ValueError("snapshot_missing_or_unbounded")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("snapshot_not_a_mapping")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--scout", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--exchange", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_sniper_dispatch_readiness(
            scout_snapshot=_read_snapshot(args.scout),
            buyer_review_snapshot=_read_snapshot(args.review),
            commercial_exchange_snapshot=_read_snapshot(args.exchange),
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["state"] == "INTERNAL_RESEARCH_READY" else 2
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({
            "mode": "READ_ONLY_CROSS_SNAPSHOT_REVIEW",
            "state": "HOLD_EVIDENCE",
            "error_class": type(exc).__name__,
            "canonical_empiredb_writes": False,
            "outreach_authorized": False,
            "execution_authority": "none",
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
