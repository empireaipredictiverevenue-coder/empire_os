"""Read-only replay of inbound recovery events. Never connects to external services."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.inbound_revenue_recovery import RecoveryEvent, RecoveryLedger


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline inbound recovery evidence replay")
    parser.add_argument("--events-jsonl", type=Path, required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    ledger = RecoveryLedger()
    for line_no, line in enumerate(args.events_jsonl.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            ledger.append(RecoveryEvent(**payload))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"invalid_event_on_line_{line_no}: {exc}") from exc
    print(json.dumps(ledger.report(args.tenant_id), sort_keys=True))


if __name__ == "__main__":
    main()
