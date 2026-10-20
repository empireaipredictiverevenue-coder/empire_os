"""Backup metadata is a necessary but insufficient condition for EmpireDB 057."""
from datetime import datetime, timedelta, timezone
import copy
import json
import subprocess
import sys

import pytest

from scripts.review_inbound_057_backup_readiness import inspect_backup_metadata

NOW = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)


def ts(hours_ago):
    return int((NOW - timedelta(hours=hours_ago)).timestamp())


def payload(*, latest_hours=3, full_hours=30, stanza="empiredb", status=0):
    def backup(kind, hours):
        return {
            "type": kind,
            "timestamp": {
                "start": ts(hours + 0.25),
                "stop": ts(hours),
            },
        }
    return [{
        "name": stanza,
        "status": {"code": status},
        "repo": [{"key": 1, "status": {"code": status}}],
        "backup": [
            backup("full", full_hours),
            backup("diff", latest_hours),
        ],
    }]


def test_recent_healthy_full_and_diff_only_ready_for_review():
    report = inspect_backup_metadata(payload(), now_utc=NOW)
    assert report["status"] == "READY_FOR_INDEPENDENT_BACKUP_RESTORE_REVIEW"
    assert report["gates"]["correct_healthy_empiredb_stanza"] is True
    assert report["gates"]["recent_completed_backup_within_48h"] is True
    assert report["gates"]["completed_full_backup_within_168h"] is True
    assert report["gates"]["restore_or_pitr_drill_independently_verified"] is False
    assert report["gates"]["migration_approval_granted"] is False
    assert report["production_database_changed"] is False


@pytest.mark.parametrize("modified", [
    payload(latest_hours=49, full_hours=100),
    payload(full_hours=169),
    payload(stanza="unrelated"),
    payload(status=2),
    [{"name": "empiredb", "status": {"code": 0}, "backup": []}],
    [],
    {},
])
def test_backup_missing_stale_or_wrong_stanza_is_held(modified):
    result = inspect_backup_metadata(modified, now_utc=NOW)
    assert result["status"] == "HELD_BACKUP_RECENCY_OR_REPOSITORY"
    assert result["backup_or_restore_performed"] is False


def test_48h_boundary_not_rounded_into_false_success():
    # Existing REV051 reviewer rounds display ages to one decimal;
    # the stricter 057 gate uses original unrounded Unix timestamps.
    info = payload(latest_hours=48 + 0.02, full_hours=100)
    result = inspect_backup_metadata(info, now_utc=NOW)
    assert not result["gates"]["recent_completed_backup_within_48h"]
    assert result["status"].startswith("HELD_")


def test_future_invalid_and_malformed_full_backups_never_count():
    info = payload()
    info[0]["backup"][0]["timestamp"]["stop"] = ts(-1)
    assert not inspect_backup_metadata(info, now_utc=NOW)["gates"][
        "completed_full_backup_within_168h"
    ]
    info[0]["backup"][0]["timestamp"]["stop"] = "unknown"
    assert not inspect_backup_metadata(info, now_utc=NOW)["gates"][
        "completed_full_backup_within_168h"
    ]


def test_output_does_not_reveal_backup_names_or_paths():
    info = payload()
    info[0]["backup"][0]["label"] = "sensitive-internal-backup-label"
    info[0]["repo"][0]["cipher-pass"] = "must-not-appear"
    report = inspect_backup_metadata(info, now_utc=NOW)
    text = json.dumps(report)
    assert "sensitive-internal" not in text
    assert "must-not-appear" not in text
    assert "repo" not in report


def test_cli_bogus_input_stays_held_and_does_not_dump_raw_input():
    raw = '{"password":"do-not-print-this","backup":[]}'
    cmd = [
        sys.executable, "-B", "-m",
        "scripts.review_inbound_057_backup_readiness", "--stdin", "--read-only",
    ]
    result = subprocess.run(cmd, input=raw, text=True, capture_output=True)
    assert result.returncode == 2
    output = json.loads(result.stdout)
    assert output["status"] == "HELD_BACKUP_RECENCY_OR_REPOSITORY"
    assert "do-not-print-this" not in result.stdout
