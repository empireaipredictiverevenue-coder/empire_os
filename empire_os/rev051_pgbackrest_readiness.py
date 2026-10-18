"""Strict pgBackRest repository metadata preflight for approved REV051.

Do not claim a restore is tested: a completed backup recorded by a healthy
stanza is a prerequisite, not evidence of independently successful restore.
The pgBackRest JSON 'repo' array can be absent on a healthy single-repo
stanza. Absence of a per-repo array is NOT the same as backup absence.

No connections, backup operations, customer records or secrets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "empire.rev051.pgbackrest_backup_readiness.v1"
MAX_AGE_HOURS = 168


def _timestamp(value: Any) -> int | None:
    # Backups must have a plain integer Unix stop time.
    if type(value) is not int or value <= 0:
        return None
    return value


def review_pgbackrest_info(
    info: Any, *, now_utc: datetime | None = None
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone aware review time required")
    epoch = now.timestamp()
    summary = {
        "schema_version": SCHEMA,
        "status": "HOLD_RECENT_COMPLETED_BACKUP_NOT_PROVEN",
        "healthy_stanza_count": 0,
        "recent_completed_backup_count": 0,
        "newest_backup_age_hours": None,
        "stanza_count": 0,
        "max_backup_age_hours": MAX_AGE_HOURS,
        "explicit_repo_status_array_required": False,
        "single_repo_stanza_status_sufficient_when_repo_array_absent": True,
        "backup_info_is_independent_restore_drill": False,
        "money_moved": False,
        "database_mutation": False,
        "execution_authority": "none",
    }
    # The caller explicitly requests the live 'empiredb' stanza. Never
    # accept an unrelated healthy backup to permit EmpireDB DDL.
    if type(info) is not list or len(info) != 1:
        summary["reason"] = "EXPECTED_SINGLE_EMPIREDB_STANZA_NOT_RETURNED"
        return summary
    summary["stanza_count"] = len(info)
    verified_ages: list[float] = []
    reason = "NO_HEALTHY_BACKUP_STANZA"
    for stanza in info:
        if not isinstance(stanza, dict) or stanza.get("name") != "empiredb":
            reason = "UNEXPECTED_STANZA_IDENTITY"
            continue
        status = stanza.get("status")
        if not isinstance(status, dict) or type(status.get("code")) is not int:
            reason = "UNKNOWN_STANZA_STATUS"
            continue
        if status["code"] != 0:
            reason = "STANZA_UNHEALTHY"
            continue
        repos = stanza.get("repo")
        if repos is not None:
            if type(repos) is not list or not repos:
                # Explicit empty repo list does not prove repository health.
                reason = "INVALID_REPOSITORY_STATUS_LIST"
                continue
            if not any(
                isinstance(repo, dict)
                and repo.get("key") == 1
                and isinstance(repo.get("status"), dict)
                and type(repo["status"].get("code")) is int
                and repo["status"]["code"] == 0
                for repo in repos
            ):
                reason = "NO_HEALTHY_REPOSITORY"
                continue
        # On a single-repository stanza pgBackRest need not supply repo[].
        summary["healthy_stanza_count"] += 1
        backups = stanza.get("backup")
        if type(backups) is not list:
            reason = "BACKUP_LIST_NOT_AVAILABLE"
            continue
        if not any(
            isinstance(backup, dict) and backup.get("type") == "full"
            for backup in backups
        ):
            reason = "NO_FULL_BACKUP_IN_STANZA"
            continue
        for backup in backups:
            if not isinstance(backup, dict):
                continue
            if backup.get("type") not in ("full", "diff", "incr"):
                continue
            stamp_info = backup.get("timestamp")
            if not isinstance(stamp_info, dict):
                continue
            start = _timestamp(stamp_info.get("start"))
            stop = _timestamp(stamp_info.get("stop"))
            if start is None or stop is None or start > stop:
                continue
            age = (epoch - stop) / 3600
            if 0 <= age <= MAX_AGE_HOURS:
                verified_ages.append(age)
    if verified_ages:
        summary.update(
            {
                "status": "PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED",
                "recent_completed_backup_count": len(verified_ages),
                "newest_backup_age_hours": round(min(verified_ages), 1),
                "reason": "RECENT_COMPLETED_BACKUP_RECORDED",
            }
        )
    else:
        summary["reason"] = (
            "NO_RECENT_COMPLETED_BACKUP"
            if reason == "NO_HEALTHY_BACKUP_STANZA" and summary["healthy_stanza_count"]
            else reason
        )
    return summary
