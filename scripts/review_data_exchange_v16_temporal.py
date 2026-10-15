"""Empire Data Exchange V16: one-shot READ-ONLY historical quality review.

Reuses the existing protected V15 custody DSN and canonical reader. Optional
fresh government GET uses the EXISTING allowlisted fetcher and fixed 3 IDs,
not a new poller or standing service. Never INSERT, send, expose credentials,
relabel a source field as buying intent, or approve commercial redistribution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os

from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from empire_os.data_exchange_temporal_quality import build_temporal_quality, PILOT_IDS
from scripts.operate_data_exchange_observation_custody import capture, DSN_ENV

SCHEMA = "empire.data_exchange.temporal_quality_operator.v16"


def run_review(*, now: datetime, dsn: str | None, recheck: bool,
               fetch_snapshot=capture) -> dict:
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("EXISTING_DEDICATED_CUSTODY_READER_DSN_REQUIRED")
    # All SQL executed by the existing reader is inside READ ONLY transaction.
    # No second read that could mix different custody-head states.
    rows = EmpireDBConstructionCustody(dsn).read_window()
    if not rows:
        raise ValueError("NO_CANONICAL_OBSERVATIONS")
    fresh = fetch_snapshot(now=now) if recheck else None
    return build_temporal_quality(rows, assessed_at=now, recheck=fresh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recheck-official", action="store_true")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        now = datetime.now(timezone.utc)
        if args.source_only:
            if args.recheck_official:
                raise ValueError("SOURCE_ONLY_CANNOT_BE_CUSTODY_RECHECK")
            snapshot = capture(now=now)
            if set(record["record_id"] for record in snapshot["records"]) != PILOT_IDS:
                raise ValueError("PINNED_PILOT_SOURCE_SAMPLE_NOT_COMPLETE")
            report = {
                "schema_version": SCHEMA,
                "mode": "OBSERVE",
                "status": "OFFICIAL_SOURCE_SHAPE_PREVIEW_ONLY",
                "pilot_entity_count": len(PILOT_IDS),
                "pilot_entity_scope": "THREE_NAMED_ENTITIES_NOT_REGIONAL_MARKET_COVERAGE",
                "source_authenticity": "NOT_INDEPENDENTLY_VERIFIED",
                "canonical_history_read": False,
                "canonical_observation_written": False,
                "database_writes": False,
                "customer_delivery_enabled": False,
                "execution_authority": "NONE",
            }
        else:
            report = run_review(
                now=now, dsn=os.environ.get(DSN_ENV),
                recheck=args.recheck_official,
            )
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # Never print SQL/libpq/HTTP exception messages, secrets, or responses.
        print(json.dumps({
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "HOLD_UNVERIFIED_SOURCE_OR_CUSTODY",
            "error_type": type(exc).__name__,
            "database_writes": False,
            "outbound_enabled": False,
            "payment_execution": False,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
