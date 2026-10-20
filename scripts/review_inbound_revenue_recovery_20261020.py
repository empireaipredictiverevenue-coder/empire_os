"""Read-only tenant-scoped inbound recovery replay and operational scorecard.

JSONL mode validates local synthetic/trusted-fixture events; SQLite mode opens
an existing offline store with database-level read-only protections. Neither
accesses voice providers, Supabase, CRM or any payment/booking API.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.inbound_recovery_scorecard import build_inbound_recovery_scorecard
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent, RecoveryLedger


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline inbound recovery evidence review")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--events-jsonl", type=Path)
    source.add_argument("--sqlite-db", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--scorecard", action="store_true")
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()

    if args.events_jsonl is not None:
        ledger = RecoveryLedger()
        for line_no, line in enumerate(
            args.events_jsonl.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                ledger.append(RecoveryEvent(**payload))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise SystemExit(f"invalid_event_on_line_{line_no}: {exc}") from exc
        report = ledger.report(args.tenant_id)
    else:
        with OfflineRecoveryStore(args.sqlite_db, read_only=True) as store:
            report = store.report(args.tenant_id)

    result = build_inbound_recovery_scorecard(report) if args.scorecard else report
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
