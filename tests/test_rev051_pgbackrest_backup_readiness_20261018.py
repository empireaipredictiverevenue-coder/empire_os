"""No live backup/DB calls. Explicitly tests healthy stanza without repo[]."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import subprocess
from types import SimpleNamespace

import pytest

from empire_os.rev051_pgbackrest_readiness import (
    review_pgbackrest_info, MAX_AGE_HOURS
)
from scripts import review_rev051_pgbackrest_backup_readonly as cli

NOW=datetime(2026,10,18,15,0,tzinfo=timezone.utc)
STOP=int((NOW-timedelta(hours=22)).timestamp())


def stanza(*,repo_present=False,healthy=True,stop=STOP,full=True):
    s={
        "name":"empiredb",
        "status":{"code":0 if healthy else 2},
        "backup":([
            {"type":"full","timestamp":{"start":stop-100,"stop":stop}}
        ] if full else []),
    }
    if repo_present:
        s["repo"]=[{"key":1,"status":{"code":0}}]
    return s


def test_healthy_single_repo_without_repo_array_passes_with_real_backup():
    data=review_pgbackrest_info([stanza()],now_utc=NOW)
    assert data["status"]=="PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"
    assert data["recent_completed_backup_count"]==1
    assert data["healthy_stanza_count"]==1
    assert data["newest_backup_age_hours"]==22
    assert data["backup_info_is_independent_restore_drill"] is False


def test_healthy_explicit_repo_passes_but_no_backup_stays_hold():
    passed=review_pgbackrest_info([stanza(repo_present=True)],now_utc=NOW)
    assert passed["status"]=="PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"
    x=stanza(repo_present=True,full=False)
    held=review_pgbackrest_info([x],now_utc=NOW)
    assert held["status"].startswith("HOLD_")
    assert held["reason"]=="NO_FULL_BACKUP_IN_STANZA"


@pytest.mark.parametrize("bad,reason", [
    ([stanza(healthy=False)],"STANZA_UNHEALTHY"),
    ([{"name":"empiredb","status":{"code":0},"backup":[]}],"NO_FULL_BACKUP_IN_STANZA"),
    ([dict(stanza(),repo=[])],"INVALID_REPOSITORY_STATUS_LIST"),
    ([dict(stanza(),repo=[{"key":1,"status":{"code":2}}])],"NO_HEALTHY_REPOSITORY"),
    ([stanza(stop=STOP-9*24*3600)],"NO_RECENT_COMPLETED_BACKUP"),
    ([stanza(stop=STOP+5*24*3600)],"NO_RECENT_COMPLETED_BACKUP"),
    ([], "EXPECTED_SINGLE_EMPIREDB_STANZA_NOT_RETURNED"),
    ({"status": {"code":0}}, "EXPECTED_SINGLE_EMPIREDB_STANZA_NOT_RETURNED"),
])
def test_absent_stale_invalid_repo_and_stanza_status_fail_closed(bad,reason):
    result=review_pgbackrest_info(bad,now_utc=NOW)
    assert result["status"]=="HOLD_RECENT_COMPLETED_BACKUP_NOT_PROVEN"
    assert result["recent_completed_backup_count"]==0
    assert result["backup_info_is_independent_restore_drill"] is False
    assert result["reason"]==reason


def test_stale_recently_finished_diff_without_full_base_not_accepted():
    diff={"name":"empiredb","status":{"code":0},"backup":[{
        "type":"diff",
        "timestamp":{"start":STOP-10,"stop":STOP},
    }]}
    assert review_pgbackrest_info([diff],now_utc=NOW)["status"].startswith("HOLD_")


@pytest.mark.parametrize("bad_time", [None,True,"2026",0,-5,1.2])
def test_timestamp_must_be_positive_integer(bad_time):
    meta=stanza()
    meta["backup"][0]["timestamp"]["stop"]=bad_time
    state=review_pgbackrest_info([meta],now_utc=NOW)
    assert state["status"].startswith("HOLD_")


def test_future_or_non_timezone_aware_review_time_rejected():
    with pytest.raises(ValueError):
        review_pgbackrest_info([stanza()],now_utc=datetime(2026,10,18))


def test_sanitized_root_diagnostic_never_outputs_raw_backup_metadata(monkeypatch,capsys):
    monkeypatch.setattr(cli.os,"geteuid",lambda:0)
    called=[]
    def fake_run(args,**kwargs):
        called.append(args)
        assert args == ["runuser","-u","postgres","--",
                        "pgbackrest", "--config=/etc/pgbackrest/empiredb.conf",
                        "--stanza=empiredb", "--output=json", "info"]
        assert kwargs["capture_output"] is True
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps([stanza()]).encode(),
            stderr=b"private_backup_repository_path",
        )
    info=cli.diagnostic(run=fake_run)
    assert info["status"]=="PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"
    assert "private_backup_repository_path" not in json.dumps(info)
    assert called


def test_sanitized_diagnostic_not_privileged_returns_hold(monkeypatch):
    monkeypatch.setattr(cli.os,"geteuid",lambda:1000)
    assert cli.diagnostic()["status"]=="HOLD_ROOT_LOCAL_READ_REQUIRED"


def test_pgbackrest_error_never_exposes_stderr(monkeypatch):
    monkeypatch.setattr(cli.os,"geteuid",lambda:0)
    def fake_run(*args,**kwargs):
        return SimpleNamespace(returncode=41,stdout=b"",stderr=b"SECRET")
    result=cli.diagnostic(run=fake_run)
    assert result["status"]=="HOLD_PGBACKREST_INFO_NOT_READABLE"
    assert "SECRET" not in json.dumps(result)


def test_release_backup_verification_uses_same_strict_shared_parser():
    from pathlib import Path
    content=(Path(__file__).resolve().parents[1]/
             "scripts/deploy_approved_rev051_guarded_20261018.sh").read_text()
    assert "review_pgbackrest_info(metadata)" in content
    assert "RECENT_VERIFIED_BACKUP_NOT_PROVEN" in content
    assert "latest_backup_age_hours" in content
    assert '--config="$BACKUP_CONFIG" --stanza="$BACKUP_STANZA" --output=json info' in content
    assert "BACKUP_CONFIG=/etc/pgbackrest/empiredb.conf" in content
    assert "archive_command_matches_active_repo" in content
    assert 'if ! pg -f "$SQL"' in content


def test_wrong_or_multiple_backup_stanzas_never_authorize_empiredb():
    extra=stanza()
    extra["name"]="different_tenant"
    assert review_pgbackrest_info([extra],now_utc=NOW)["reason"] == "UNEXPECTED_STANZA_IDENTITY"
    assert review_pgbackrest_info([stanza(),extra],now_utc=NOW)["reason"] == "EXPECTED_SINGLE_EMPIREDB_STANZA_NOT_RETURNED"
    mismatched=stanza(repo_present=True)
    mismatched["repo"][0]["key"]=2
    assert review_pgbackrest_info([mismatched],now_utc=NOW)["reason"] == "NO_HEALTHY_REPOSITORY"
