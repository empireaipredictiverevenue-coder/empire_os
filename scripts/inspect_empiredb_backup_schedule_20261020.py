"""Production-safe scheduling inventory for the EXISTING Data Cloud owner.

READ-ONLY. Never creates/enables timers, runs a backup, reads secret content,
prints cron lines, or makes a database connection. Only root can inspect
both privileged crontabs and the full systemd/cron scheduling inventory.
A green inventory is not permission to install any unit.
"""
from __future__ import annotations
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path

SCHEMA = "empire.empiredb.physical-backup-scheduler-readiness.v1"
CRON_DIRS = (Path("/etc/cron.d"), Path("/etc/cron.hourly"),
             Path("/etc/cron.daily"), Path("/etc/cron.weekly"),
             Path("/etc/cron.monthly"))
TARGETS = (
    "empire-data-cloud-physical-backup@full.timer",
    "empire-data-cloud-physical-backup@diff.timer",
    "empire-data-cloud-physical-backup@.service",
)
CONFIG = Path("/etc/pgbackrest/empiredb.conf")
# Matching is deliberately conservative; other DB backup producers
# require human reconciliation before installing a second schedule.
BACKUP_PATTERN = re.compile(
    r"pgbackrest|pg_basebackup|empiredb[^\s]*backup|"
    r"empire[^\s]*backup[^\s]*(?:\.sh|\.py|\.service)",
    re.IGNORECASE,
)


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, text=True, capture_output=True, timeout=6, check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
    )


def _script_job(text: str) -> bool:
    return any(
        BACKUP_PATTERN.search(line) is not None
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _cron_user_state(user: str) -> str:
    cmd = _run("/usr/bin/crontab", "-u", user, "-l")
    if cmd.returncode == 0:
        return "MATCHING_JOB" if _script_job(cmd.stdout) else "NO_MATCHING_JOB"
    if cmd.returncode == 1 and re.search(
        r"no crontab for\s+" + re.escape(user) + r"\b",
        cmd.stderr, flags=re.IGNORECASE,
    ):
        return "NO_CRONTAB"
    return "UNAVAILABLE"


def _system_cron_state() -> str:
    files = [Path("/etc/crontab")]
    for folder in CRON_DIRS:
        if not folder.is_dir() or folder.is_symlink():
            return "UNAVAILABLE"
        try:
            files += [p for p in folder.iterdir() if p.is_file() or p.is_symlink()]
        except OSError:
            return "UNAVAILABLE"
    for item in files:
        try:
            st = item.lstat()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0
                or (st.st_mode & 0o022)):
                return "UNAVAILABLE"
            if st.st_size > 65536:
                return "UNAVAILABLE"
            body = item.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return "UNAVAILABLE"
        if _script_job(body):
            return "MATCHING_JOB"
    return "NO_MATCHING_JOB"


def _systemd_state() -> str:
    cmd = _run("/usr/bin/systemctl", "list-timers", "--all", "--no-pager",
               "--plain", "--no-legend")
    if cmd.returncode != 0:
        return "UNAVAILABLE"
    allowed = ("empire-data-cloud-backup-observer.timer",
               "dpkg-db-backup.timer")
    for line in cmd.stdout.splitlines():
        if BACKUP_PATTERN.search(line) and not any(a in line for a in allowed):
            return "MATCHING_TIMER"
    for target in TARGETS:
        if Path("/etc/systemd/system", target).exists():
            return "TARGET_EXISTS"
    return "NO_MATCHING_TIMER"


def _config_state() -> bool:
    try:
        st = CONFIG.lstat()
        return (stat.S_ISREG(st.st_mode) and st.st_uid == pwd.getpwnam('postgres').pw_uid
                and st.st_size > 0 and not (st.st_mode & 0o077))
    except OSError:
        return False


def evaluate(states: dict[str, object]) -> dict:
    cron_ok = all(states.get(k) in ("NO_CRONTAB", "NO_MATCHING_JOB")
                  for k in ("root_cron", "postgres_cron"))
    checks = {
        "complete_privileged_cron_inventory": cron_ok,
        "system_cron_no_backup_collision":
            states.get("system_cron") == "NO_MATCHING_JOB",
        "systemd_no_backup_collision":
            states.get("systemd") == "NO_MATCHING_TIMER",
        "approved_pgbackrest_config_private":
            states.get("config_private") is True,
    }
    return {
        "schema": SCHEMA, "mode": "READ_ONLY_SCHEDULER_INVENTORY",
        "status": ("READY_FOR_EXISTING_DATA_CLOUD_OWNER_REVIEW"
                   if all(checks.values()) else "HELD_SCHEDULER_COLLISION_OR_AUTHORITY"),
        "gates": checks,
        "postgres_cron_state": states.get("postgres_cron", "UNAVAILABLE"),
        "root_cron_state": states.get("root_cron", "UNAVAILABLE"),
        "system_cron_state": states.get("system_cron", "UNAVAILABLE"),
        "systemd_state": states.get("systemd", "UNAVAILABLE"),
        "backup_created": False,
        "timer_installed_or_enabled": False,
        "customer_actions_authorized": False,
        "migration_executed": False,
        "needs_dba_approval": True,
    }


def main(argv: list[str]) -> int:
    if argv != ["--read-only"]:
        print(json.dumps({"status":"HELD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 3
    if os.geteuid() != 0:
        print(json.dumps({
            "schema": SCHEMA, "status":"HELD_ROOT_CRON_INVENTORY_REQUIRED",
            "backup_created":False, "timer_installed_or_enabled":False,
        }))
        return 3
    try:
        result = evaluate({
            "root_cron": _cron_user_state("root"),
            "postgres_cron": _cron_user_state("postgres"),
            "system_cron": _system_cron_state(),
            "systemd": _systemd_state(),
            "config_private": _config_state(),
        })
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result = evaluate({})
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"].startswith("READY_") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
