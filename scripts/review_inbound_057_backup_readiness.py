"""EmpireDB 057: read-only pgBackRest metadata release preflight.

Pipe the existing postgres OS user's pgBackRest JSON into this command as
Ubuntu. No backup paths, labels, credentials, database rows or provider
secrets appear in output; this process never connects to PostgreSQL.
An observed backup is not evidence of successful restore/PITR.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys

from empire_os.rev051_pgbackrest_readiness import review_pgbackrest_info

MAX_CURRENT_BACKUP_HOURS = 48
MAX_RECENT_FULL_BACKUP_HOURS = 168
MAX_INPUT_BYTES = 1_000_000


def _age_hours(timestamp: object, now: datetime) -> float | None:
    if type(timestamp) is not int or timestamp <= 0:
        return None
    age = (now.timestamp() - timestamp) / 3600
    return age if age >= 0 else None


def inspect_backup_metadata(data: object, *, now_utc: datetime | None = None) -> dict:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_aware_now_required")
    base = review_pgbackrest_info(data, now_utc=now)
    newest_full_age = None
    newest_completed_age = None
    try:
        stanza = data[0] if type(data) is list and len(data) == 1 else None
        if isinstance(stanza, dict) and stanza.get("name") == "empiredb":
            full_ages = []
            completed_ages = []
            for item in stanza.get("backup", []):
                if not isinstance(item, dict) or item.get("type") not in ("full", "diff", "incr"):
                    continue
                timestamps = item.get("timestamp")
                if not isinstance(timestamps, dict):
                    continue
                start = _age_hours(timestamps.get("start"), now)
                stop = _age_hours(timestamps.get("stop"), now)
                if start is None or stop is None or start < stop:
                    # Ages are reversed: start is older than stop.
                    continue
                completed_ages.append(stop)
                if item.get("type") == "full":
                    full_ages.append(stop)
            if full_ages:
                newest_full_age = min(full_ages)
            if completed_ages:
                newest_completed_age = min(completed_ages)
    except (TypeError, ValueError):
        newest_full_age = None

    healthy = (
        base.get("status") == "PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"
        and base.get("healthy_stanza_count") == 1
    )
    recent = (
        healthy
        and newest_completed_age is not None
        and newest_completed_age <= MAX_CURRENT_BACKUP_HOURS
    )
    full = (
        healthy and newest_full_age is not None
        and newest_full_age <= MAX_RECENT_FULL_BACKUP_HOURS
    )
    # Metadata does not attest PITR or real restore. Never infer approval.
    return {
        "schema": "empire.inbound.empiredb057.backup_preflight.v1",
        "mode": "READ_ONLY_PGBACKREST_METADATA",
        "status": ("READY_FOR_INDEPENDENT_BACKUP_RESTORE_REVIEW"
                   if healthy and recent and full else
                   "HELD_BACKUP_RECENCY_OR_REPOSITORY"),
        "gates": {
            "correct_healthy_empiredb_stanza": healthy,
            "recent_completed_backup_within_48h": bool(recent),
            "completed_full_backup_within_168h": bool(full),
            "restore_or_pitr_drill_independently_verified": False,
            "migration_approval_granted": False,
        },
        "newest_backup_age_hours": (
            base.get("newest_backup_age_hours") if healthy else None
        ),
        "newest_full_backup_age_hours": (
            round(newest_full_age, 1) if full else None
        ),
        "stanza_count": base.get("stanza_count", 0),
        "contains_backup_paths_or_labels": False,
        "production_database_changed": False,
        "backup_or_restore_performed": False,
        "revenue_verified": False,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin", action="store_true", required=True)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not (args.stdin and args.read_only):
        print(json.dumps({"status": "HELD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 3
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if not 1 <= len(raw) <= MAX_INPUT_BYTES:
            raise ValueError("oversized_or_missing_backup_json")
        data = json.loads(raw)
        report = inspect_backup_metadata(data)
    except (ValueError, TypeError, UnicodeError):
        report = {
            "status": "HELD_BACKUP_METADATA_UNAVAILABLE",
            "mode": "READ_ONLY_PGBACKREST_METADATA",
            "production_database_changed": False,
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "READY_FOR_INDEPENDENT_BACKUP_RESTORE_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
