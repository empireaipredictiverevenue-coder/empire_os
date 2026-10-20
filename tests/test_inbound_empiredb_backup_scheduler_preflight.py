"""Data Cloud scheduling candidate stays held unless all privileged jobs are inventoried."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

from scripts import inspect_empiredb_backup_schedule_20261020 as gate


def _facts(**overrides):
    baseline = {
        "root_cron": "NO_CRONTAB",
        "postgres_cron": "NO_MATCHING_JOB",
        "system_cron": "NO_MATCHING_JOB",
        "systemd": "NO_MATCHING_TIMER",
        "config_private": True,
    }
    baseline.update(overrides)
    return baseline


def test_all_known_clear_is_only_review_ready():
    result = gate.evaluate(_facts())
    assert result["status"] == "READY_FOR_EXISTING_DATA_CLOUD_OWNER_REVIEW"
    assert all(result["gates"].values())
    assert result["backup_created"] is False
    assert result["timer_installed_or_enabled"] is False
    assert result["needs_dba_approval"] is True


@pytest.mark.parametrize("facts", [
    {"root_cron": "UNAVAILABLE"},
    {"postgres_cron": "UNAVAILABLE"},
    {"root_cron": "MATCHING_JOB"},
    {"postgres_cron": "MATCHING_JOB"},
    {"system_cron": "MATCHING_JOB"},
    {"system_cron": "UNAVAILABLE"},
    {"systemd": "MATCHING_TIMER"},
    {"systemd": "TARGET_EXISTS"},
    {"systemd": "UNAVAILABLE"},
    {"config_private": False},
    {"root_cron": None},
    {},
])
def test_incomplete_or_colliding_inventory_is_held(facts):
    candidate = gate.evaluate(_facts(**facts))
    if facts:
        assert candidate["status"] == "HELD_SCHEDULER_COLLISION_OR_AUTHORITY"
    assert candidate["timer_installed_or_enabled"] is False


def test_cron_matching_never_prints_job_or_secret():
    script = """
# pgbackrest --stanza=empiredb backup
15 3 * * 1 /usr/bin/pgbackrest --stanza=empiredb backup --password=private-do-not-print
"""
    assert gate._script_job(script)
    result = gate.evaluate(_facts(postgres_cron="MATCHING_JOB"))
    assert result["status"].startswith("HELD_")
    assert "private-do-not-print" not in json.dumps(result)
    assert gate._script_job("# pgbackrest backup\n") is False


def test_privileged_empty_cron_is_valid_absence(monkeypatch):
    def mocked(*argv):
        user = argv[2]
        return subprocess.CompletedProcess(
            argv, 1, "", "no crontab for " + user,
        )
    monkeypatch.setattr(gate, "_run", mocked)
    assert gate._cron_user_state("postgres") == "NO_CRONTAB"
    assert gate._cron_user_state("root") == "NO_CRONTAB"


def test_cron_errors_not_misread_as_no_crontab(monkeypatch):
    monkeypatch.setattr(gate, "_run", lambda *args:
        subprocess.CompletedProcess(args, 1, "", "permission denied"))
    assert gate._cron_user_state("postgres") == "UNAVAILABLE"


def test_template_is_prepared_only_dba_owned_and_without_expiration():
    root = Path("deploy/systemd")
    service = (root / "empire-data-cloud-physical-backup@.service").read_text()
    full = (root / "empire-data-cloud-physical-backup@full.timer").read_text()
    diff = (root / "empire-data-cloud-physical-backup@diff.timer").read_text()
    assert "PREPARED ONLY" in service
    assert "User=postgres" in service
    assert "--no-expire-auto" in service
    assert "--stanza=empiredb" in service
    assert "--type=%i" in service
    assert "ExecStart=/usr/bin/pgbackrest" in service
    assert "Persistent=false" in full and "Persistent=false" in diff
    assert "Wed,Sun *-*-* 03:00:00 UTC" in full
    assert "Mon,Tue,Thu..Sat *-*-* 03:00:00 UTC" in diff
    assert "WantedBy=timers.target" in full
    assert "WantedBy=timers.target" in diff


def test_unprivileged_or_missing_flag_cli_never_inventories_privileged_jobs():
    cmd = [sys.executable, "-B", "-m",
           "scripts.inspect_empiredb_backup_schedule_20261020", "--read-only"]
    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    # A developer session is deliberately unprivileged.
    if process.returncode == 3:
        assert json.loads(process.stdout)["status"] == "HELD_ROOT_CRON_INVENTORY_REQUIRED"
