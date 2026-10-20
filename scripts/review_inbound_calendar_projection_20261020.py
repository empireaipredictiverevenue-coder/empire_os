"""Supervised local-only calendar evidence projection or read-only backlog review.

NO Google access, token issuance, booking, calling or payment operations.
Write mode is only an explicit local SQLite evidence replay from already
verified registry records. Never run against production copies.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from dataclasses import asdict

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_calendar_projection import project_calendar_evidence_offline
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_recovery_store import OfflineRecoveryStore


def _validated_existing_database(raw: Path) -> Path:
    if not raw.is_absolute() or raw.is_symlink() or not raw.is_file():
        raise ValueError("existing_absolute_private_sqlite_file_required")
    return raw.resolve(strict=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explicit offline calendar evidence replay (NEVER live calendar integration)"
    )
    parser.add_argument("--calendar-db", type=Path, required=True)
    parser.add_argument("--recovery-db", type=Path)
    parser.add_argument("--workflow-db", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--limit", type=int, default=100)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--read-only", action="store_true")
    mode.add_argument("--apply-local-evidence-replay", action="store_true")
    args = parser.parse_args()

    if args.apply_local_evidence_replay and (
        args.recovery_db is None or args.workflow_db is None or not args.as_of
    ):
        parser.error("write mode requires three separate existing databases and --as-of")
    try:
        calendar = _validated_existing_database(args.calendar_db)
        if args.read_only:
            with OfflineCalendarRegistry(calendar, read_only=True) as registry:
                counts = registry.projection_counts(args.tenant_id)
                result = {
                    "tenant_id": args.tenant_id,
                    "mode": "calendar_projection_backlog_read_only",
                    **counts,
                    "live_actions_authorized": False,
                }
        else:
            recovery = _validated_existing_database(args.recovery_db)
            workflow = _validated_existing_database(args.workflow_db)
            if len({calendar, recovery, workflow}) != 3:
                raise ValueError("distinct_local_evidence_databases_required")
            clock = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            with OfflineCalendarRegistry(calendar) as registry, \
                OfflineRecoveryStore(recovery) as recovered, \
                OfflineBookingWorkflowStore(workflow) as workflow_store:
                result = asdict(project_calendar_evidence_offline(
                    registry=registry, recovery=recovered, workflow=workflow_store,
                    tenant_id=args.tenant_id, as_of=clock, limit=args.limit,
                ))
    except (ValueError, OSError, TypeError) as exc:
        parser.error(f"offline projection rejected: {exc}")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
