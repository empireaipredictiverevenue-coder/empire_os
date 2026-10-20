"""Physical backup job preflight cannot mutate repository or run outside custody."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.inspect_empiredb_backup_job_preflight_20261020 import (
    MAX_RETAINED_BACKUPS, MIN_REPO_FREE_BYTES, inspect_metadata,
)

NOW = datetime(2026, 10, 20, 20, tzinfo=timezone.utc)


def record(kind, age_hours):
    stop = int((NOW - timedelta(hours=age_hours)).timestamp())
    return {"type": kind, "timestamp": {"start": stop - 120, "stop": stop}}


def sample(*, extra=(), full_age=48):
    return [{
        "name": "empiredb", "status": {"code": 0},
        "backup": [record("full", full_age), record("diff", 1), *extra],
    }]


def report(data=None, *, kind="diff", free=MIN_REPO_FREE_BYTES + 1):
    return inspect_metadata(
        sample() if data is None else data, backup_type=kind,
        free_bytes=free, now_utc=NOW,
    )


def test_approved_metadata_only_entitles_supervised_job():
    result = report()
    assert result["status"] == "READY_FOR_ONE_SUPERVISED_BACKUP"
    assert all(result["gates"].values())
    assert result["backup_created"] is False
    assert result["expiry_executed"] is False
    assert result["timer_activated"] is False


def test_missing_stale_base_blocks_diff_but_full_can_repair():
    assert report(sample(full_age=170))["status"].startswith("HELD_")
    assert report(sample(full_age=170), kind="full")["status"] == (
        "READY_FOR_ONE_SUPERVISED_BACKUP"
    )


def test_low_space_or_unsafe_input_blocks():
    assert report(free=MIN_REPO_FREE_BYTES - 1)["status"].startswith("HELD_")
    assert report(free=True)["status"].startswith("HELD_")
    assert report(kind="incr")["status"].startswith("HELD_")
    assert report(data=[])["status"].startswith("HELD_")
    assert report(data=[{"name":"other"}])["status"].startswith("HELD_")


def test_oversized_backup_sets_fail_closed_instead_of_filling_repository():
    data = sample(extra=[record("diff", 2)] * (MAX_RETAINED_BACKUPS - 2))
    blocked = report(data)
    assert blocked["observed_backup_count"] == MAX_RETAINED_BACKUPS
    assert blocked["status"].startswith("HELD_")


@pytest.mark.parametrize("edited", [
    lambda d: d[0].update(status={"code": 1}),
    lambda d: d[0].update(repo=[{"key": 1, "status": {"code": 2}}]),
    lambda d: d[0].update(backup=[]),
    lambda d: d[0]["backup"][0].update(timestamp={"start": 1, "stop": 2}),
    lambda d: d[0]["backup"][0].update(timestamp={"start": "x", "stop": "y"}),
    lambda d: d[0]["backup"][0].update(type="unverified"),
])
def test_bad_catalog_never_runs_backup(edited):
    data = sample()
    edited(data)
    assert report(data)["status"].startswith("HELD_")


def test_result_contains_no_provider_labels_or_credentials():
    data = sample()
    data[0]["backup"][0]["label"] = "private-snapshot-identifier"
    data[0]["repo_path"] = "/sensitive/location"
    output = json.dumps(report(data))
    assert "private-snapshot-identifier" not in output
    assert "/sensitive/location" not in output
    assert '"backup_created": false' in output


def test_unit_requires_pinned_preflight_before_pgbackrest():
    unit = Path("deploy/systemd/empire-data-cloud-physical-backup@.service").read_text()
    guard = "ExecStartPre=/usr/bin/python3 -I -B /opt/empire-ai/backup-operators/releases/20261020-empiredb-physical-guard-v1/inspect_empiredb_backup_job_preflight_20261020.py --preflight %i"
    cmd = "ExecStart=/usr/bin/pgbackrest"
    assert guard in unit
    assert unit.index(guard) < unit.index(cmd)
    assert "--no-expire-auto" in unit


def test_unapproved_local_source_cannot_execute_privileged_preflight():
    proc = subprocess.run([
        sys.executable, "-B", "-m",
        "scripts.inspect_empiredb_backup_job_preflight_20261020",
        "--preflight", "diff",
    ], capture_output=True, text=True)
    assert proc.returncode == 2
    output = json.loads(proc.stdout)
    assert output["status"] == "HELD_BACKUP_JOB_OPERATOR_CUSTODY"
    assert output["backup_created"] is False
