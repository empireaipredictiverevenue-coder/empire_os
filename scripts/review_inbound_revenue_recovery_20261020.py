"""Read-only tenant-scoped inbound revenue intelligence review.

Accepts explicitly marked local events / signed-offline SQLite, optional
reviewed intent signals and verified call-tracking source claims.
Never dispatches contact or mutates a production database.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import TypeVar

from empire_os.inbound_opportunity_intelligence import (
    OpportunityPolicy, OpportunitySignal, build_opportunity_queue,
)
from empire_os.inbound_recovery_scorecard import build_inbound_recovery_scorecard
from empire_os.inbound_recovery_patterns import PatternPolicy, analyse_inbound_patterns
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent, RecoveryLedger
from empire_os.inbound_source_attribution import SourceTouch, attribute_recovered_sources

T = TypeVar("T")


def _read_jsonl(path: Path, kind: type[T]) -> list[T]:
    result: list[T] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("json_object_required")
            result.append(kind(**payload))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"invalid_{kind.__name__}_line_{line_no}: {exc}") from exc
    return result


def _as_of(value: str | None) -> datetime:
    if not value:
        raise SystemExit("--as-of required for opportunity or attribution review")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("timezone_required")
        return dt
    except ValueError as exc:
        raise SystemExit(f"invalid_as_of: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline inbound commercial intelligence review")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--events-jsonl", type=Path)
    source.add_argument("--sqlite-db", type=Path)
    parser.add_argument("--tenant-id", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scorecard", action="store_true")
    mode.add_argument("--opportunities", action="store_true")
    mode.add_argument("--source-attribution", action="store_true")
    mode.add_argument("--patterns", action="store_true")
    parser.add_argument("--signals-jsonl", type=Path)
    parser.add_argument("--source-touches-jsonl", type=Path)
    parser.add_argument("--as-of")
    parser.add_argument("--timezone")  # Required only for observed local demand patterns.
    parser.add_argument("--max-tickets", type=int, default=500)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()

    if args.signals_jsonl and not args.opportunities:
        parser.error("--signals-jsonl requires --opportunities")
    if args.source_touches_jsonl and not args.source_attribution:
        parser.error("--source-touches-jsonl requires --source-attribution")
    if args.patterns and not args.timezone:
        parser.error("--timezone required for --patterns")
    if args.events_jsonl is not None:
        events = _read_jsonl(args.events_jsonl, RecoveryEvent)
    else:
        with OfflineRecoveryStore(args.sqlite_db, read_only=True) as store:
            events = list(store.events_for_tenant(args.tenant_id))

    if args.opportunities:
        result = build_opportunity_queue(
            events,
            policy=OpportunityPolicy(args.tenant_id, max_tickets=args.max_tickets),
            as_of=_as_of(args.as_of),
            signals=(
                _read_jsonl(args.signals_jsonl, OpportunitySignal)
                if args.signals_jsonl else []
            ),
        )
    elif args.patterns:
        result = analyse_inbound_patterns(
            events, as_of=_as_of(args.as_of),
            policy=PatternPolicy(args.tenant_id, args.timezone),
        )
    elif args.source_attribution:
        result = attribute_recovered_sources(
            events,
            (
                _read_jsonl(args.source_touches_jsonl, SourceTouch)
                if args.source_touches_jsonl else []
            ),
            tenant_id=args.tenant_id,
            as_of=_as_of(args.as_of),
        )
    else:
        ledger = RecoveryLedger()
        for event in events:
            if event.tenant_id == args.tenant_id:
                ledger.append(event)
        report = ledger.report(args.tenant_id)
        if args.sqlite_db is not None:
            report["store"] = "offline_sqlite_persisted"
        result = build_inbound_recovery_scorecard(report) if args.scorecard else report

    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
