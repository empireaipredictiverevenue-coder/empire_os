"""Read-only offline callback/booking lifecycle review; no provider connectivity."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_booking_workflow import WorkflowPolicy


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline booking/callback evidence review")
    parser.add_argument("--workflow-db", required=True, type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--max-calls", type=int, default=500)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    try:
        clock = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        with OfflineBookingWorkflowStore(args.workflow_db, read_only=True) as store:
            report = store.summary(
                WorkflowPolicy(args.tenant_id, max_calls=args.max_calls), as_of=clock,
            )
    except (ValueError, OSError, TypeError) as exc:
        parser.error(f"workflow review failed: {exc}")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
