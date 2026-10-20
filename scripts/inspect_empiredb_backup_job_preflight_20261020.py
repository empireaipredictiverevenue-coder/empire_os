"""Non-destructive, fail-closed preflight for the DBA-owned physical backup job.

Candidate, NOT installed on production. Installed only after founder/DBA
approval; no cron, backup, retention, logins or service writes from here.
Runs under postgres, reads approved pgBackRest *metadata*, statvfs and file
ownership only. Emits codes/booleans, never labels/paths/tokens.
"""
from __future__ import annotations

import json
import os
import pwd
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "empire.empiredb.physical-backup-job.preflight.v1"
RELEASE = Path("/opt/empire-ai/backup-operators/releases/20261020-empiredb-physical-guard-v1")
PINNED_SCRIPT = RELEASE / "inspect_empiredb_backup_job_preflight_20261020.py"
CONFIG = Path("/etc/pgbackrest/empiredb.conf")
REPO = Path("/var/backups/empiredb/pgbackrest")
MAX_RETAINED_BACKUPS = 28
MIN_REPO_FREE_BYTES = 100 * 1024 ** 3
MAX_FULL_AGE_HOURS = 168


def inspect_metadata(document: object, *, backup_type: str,
                     free_bytes: int, now_utc: datetime) -> dict:
    """Independent of privileged OS/file I/O for deterministic tests."""
    valid_now = (
        isinstance(now_utc, datetime) and now_utc.tzinfo is not None
        and now_utc.utcoffset() is not None
    )
    stanza = document[0] if type(document) is list and len(document) == 1 else None
    healthy = (
        isinstance(stanza, dict)
        and stanza.get("name") == "empiredb"
        and isinstance(stanza.get("status"), dict)
        and type(stanza["status"].get("code")) is int
        and stanza["status"]["code"] == 0
    )
    repo_status = stanza.get("repo") if healthy else None
    if repo_status is not None:
        healthy = (type(repo_status) is list and any(
            isinstance(item, dict) and item.get("key") == 1
            and isinstance(item.get("status"), dict)
            and type(item["status"].get("code")) is int
            and item["status"]["code"] == 0 for item in repo_status
        ))
    raw_backups = stanza.get("backup") if healthy else None
    backups = raw_backups if type(raw_backups) is list else []
    backed_up_full = []
    backups_valid = bool(
        healthy and isinstance(raw_backups, list)
        and len(raw_backups) >= 1 and len(raw_backups) < MAX_RETAINED_BACKUPS
    )
    for item in backups[:MAX_RETAINED_BACKUPS + 1]:
        if not isinstance(item, dict) or item.get("type") not in ("full", "diff", "incr"):
            backups_valid = False
            continue
        timestamps = item.get("timestamp")
        if not isinstance(timestamps, dict):
            backups_valid = False
            continue
        start = timestamps.get("start")
        stop = timestamps.get("stop")
        if (type(start) is not int or type(stop) is not int or start <= 0
            or stop < start or not valid_now or stop > now_utc.timestamp()):
            backups_valid = False
            continue
        if item.get("type") == "full":
            backed_up_full.append((now_utc.timestamp() - stop) / 3600)
    type_ok = backup_type in ("full", "diff")
    full_base_ok = bool(backed_up_full) if backup_type == "full" else any(
        0 <= age <= MAX_FULL_AGE_HOURS for age in backed_up_full
    )
    capacity_ok = (
        type(free_bytes) is int and free_bytes >= MIN_REPO_FREE_BYTES
    )
    checks = {
        "healthy_existing_stanza_and_repository": bool(healthy),
        "existing_full_base": bool(full_base_ok),
        "backup_records_within_bounded_cap": bool(backups_valid),
        "at_least_100gib_repo_free": capacity_ok,
        "approved_job_type_full_or_diff": type_ok,
    }
    return {
        "schema": SCHEMA, "mode": "READ_ONLY_BACKUP_JOB_PREFLIGHT",
        "status": ("READY_FOR_ONE_SUPERVISED_BACKUP" if all(checks.values())
                   else "HELD_BACKUP_JOB_SAFETY_GATES"),
        "gates": checks, "observed_backup_count": len(backups)
        if type(raw_backups) is list else None,
        "backup_created": False, "expiry_executed": False,
        "database_changed": False, "timer_activated": False,
    }


def _trusted_installed_script() -> bool:
    script = Path(__file__).absolute()
    if script != PINNED_SCRIPT:
        return False
    for item in (RELEASE, PINNED_SCRIPT):
        try:
            st = item.lstat()
            if (st.st_uid != 0 or st.st_mode & 0o022
                or stat.S_ISLNK(st.st_mode)):
                return False
            if item == PINNED_SCRIPT and not stat.S_ISREG(st.st_mode):
                return False
            if item == RELEASE and not stat.S_ISDIR(st.st_mode):
                return False
        except OSError:
            return False
    return True


def _trusted_private_config_and_repo() -> bool:
    try:
        config = CONFIG.lstat()
        repo = REPO.lstat()
        uid = pwd.getpwnam("postgres").pw_uid
        return (
            stat.S_ISREG(config.st_mode) and config.st_uid == uid
            and not config.st_mode & 0o077 and config.st_size > 0
            and stat.S_ISDIR(repo.st_mode) and repo.st_uid == uid
            and not repo.st_mode & 0o007
        )
    except (OSError, KeyError):
        return False


def run_candidate(backup_type: str) -> dict:
    if (os.geteuid() != pwd.getpwnam("postgres").pw_uid
        or not _trusted_installed_script()
        or not _trusted_private_config_and_repo()):
        return {"schema": SCHEMA, "status": "HELD_BACKUP_JOB_OPERATOR_CUSTODY",
                "backup_created": False, "timer_activated": False}
    try:
        result = subprocess.run(
            ["/usr/bin/pgbackrest", "--config=/etc/pgbackrest/empiredb.conf",
             "--stanza=empiredb", "--output=json", "--log-level-console=off",
             "info"], check=False, capture_output=True, timeout=20,
            env={"PATH": "/usr/bin:/bin", "HOME": "/var/lib/postgresql", "LANG": "C"},
        )
        if result.returncode or not 0 < len(result.stdout) <= 512000:
            raise ValueError("backup_catalog_unavailable")
        document = json.loads(result.stdout)
        volume = os.statvfs(REPO)
        free_bytes = volume.f_bavail * volume.f_frsize
        return inspect_metadata(
            document, backup_type=backup_type, free_bytes=free_bytes,
            now_utc=datetime.now(timezone.utc),
        )
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {"schema": SCHEMA, "status": "HELD_BACKUP_JOB_PROBE_ERROR",
                "backup_created": False, "timer_activated": False}


def main(argv: list[str]) -> int:
    if (len(argv) != 2 or argv[0] != "--preflight"
        or argv[1] not in ("full", "diff")):
        print(json.dumps({"schema": SCHEMA, "status": "HELD_EXACT_FLAGS_REQUIRED"}))
        return 3
    report = run_candidate(argv[1])
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("status") == "READY_FOR_ONE_SUPERVISED_BACKUP" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
