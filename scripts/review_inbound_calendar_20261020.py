"""Read-only tenant-scoped calendar status review (existing local DB only)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.inbound_calendar_registry import OfflineCalendarRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Google Calendar readback summary")
    parser.add_argument("--calendar-db", required=True, type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--read-only", required=True, action="store_true")
    args = parser.parse_args()
    try:
        with OfflineCalendarRegistry(args.calendar_db, read_only=True) as registry:
            result = registry.tenant_summary(args.tenant_id)
    except (ValueError, OSError) as exc:
        parser.error(f"calendar review failed: {exc}")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
