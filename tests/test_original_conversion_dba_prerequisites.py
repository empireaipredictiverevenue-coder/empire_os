"""Protected, read-only EmpireDB & pgBackRest prerequisites, never DDL."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from types import SimpleNamespace

import pytest

import scripts.review_original_conversion_dba_prerequisites_20261021 as mod

NOW=datetime(2026,10,21,20,0,tzinfo=timezone.utc)

def evidence(*,age_hours=2,stanza_code=0,full=True):
    seconds=int((NOW-timedelta(hours=age_hours)).timestamp())
    return [{
        "name":"empiredb",
        "status":{"code":stanza_code},
        "repo":[{"key":1,"status":{"code":0}}],
        "backup":([{
            "type":"full",
            "timestamp":{"start":seconds-100,"stop":seconds}
        }] if full else [])
    }]

def catalogue(**kwargs):
    original={k:True for k in (
        "canonical_database","postgres_version_18","migrator_role_present",
        "service_role_present","tenant_resolver_owner_shape",
        "dedicated_conversion_table_absent","dedicated_writer_fn_absent",
        "dedicated_reader_fn_absent","dedicated_writer_role_absent",
        "dedicated_reader_role_absent","archive_mode_enabled",
    )}
    original["archiver_failed_count"]=0
    original["archiver_last_failed_later_than_last_archived"]=False
    original.update(kwargs)
    return original

def test_healthy_metadata_never_approves_production_ddl():
    calls=[]
    items=[evidence(),catalogue()]
    def run(args,**opts):
        calls.append(args)
        assert opts=={"capture_output":True,"timeout":20,"check":False}
        return SimpleNamespace(returncode=0,stdout=json.dumps(items.pop(0)).encode())
    report=mod.diagnostic(run=run,is_root=True,now=NOW)
    assert report["status"]=="PRE_DDL_BACKUP_AND_AUTHORITY_METADATA_REVIEW_READY"
    assert report["newest_backup_age_hours"]==2
    assert report["max_backup_age_hours_for_change"]==24
    assert report["metadata_prerequisites_observed"] is True
    assert report["empiredb_migrator_and_tenant_resolver_shape_verified"] is True
    assert report["original_conversion_registry_absence_reconfirmed"] is True
    for key in (
        "independent_restoration_or_pitr_drill_verified",
        "offnode_backup_verified",
        "original_operator_dba_security_review_signed",
        "release_commit_approved_for_database_ddl",
        "registry_ddl_executed",
        "credentials_or_role_memberships_changed",
        "production_forecasting_enabled","database_writes",
    ):
        assert report[key] is False
    assert len(calls)==2
    assert calls[0][-1]=="info"
    assert "pgbackrest" in calls[0]
    assert "psql" in calls[1]
    assert calls[1][-2]=="-c"
    assert calls[1][-1]==mod.SQL
    assert "SELECT " in mod.SQL
    assert all(token not in mod.SQL.upper() for token in (
        "ALTER ROLE ","CREATE ROLE ","DROP TABLE ","GRANT ",
        "TRUNCATE ","INSERT INTO ","UPDATE ", "DELETE FROM ",
    ))


@pytest.mark.parametrize("archive,e,expected",[
    ({},evidence(age_hours=50),False),
    ({},evidence(stanza_code=1),False),
    ({},evidence(full=False),False),
    ({"migrator_role_present":False},evidence(),False),
    ({"tenant_resolver_owner_shape":False},evidence(),False),
    ({"archive_mode_enabled":False},evidence(),False),
    ({"archiver_last_failed_later_than_last_archived":True},evidence(),False),
    ({"dedicated_conversion_table_absent":False},evidence(),False),
    ({"dedicated_writer_role_absent":False},evidence(),False),
])
def test_missing_backup_or_database_authority_fail_closed(archive,e,expected):
    results=[e,catalogue(**archive)]
    def run(args,**kwargs):
        return SimpleNamespace(returncode=0,stdout=json.dumps(results.pop(0)).encode())
    review=mod.diagnostic(run=run,is_root=True,now=NOW)
    assert review["metadata_prerequisites_observed"] is expected
    assert review["status"]=="PRE_DDL_BACKUP_OR_AUTHORITY_METADATA_HOLD"
    assert review["registry_ddl_executed"] is False


def test_absent_root_does_not_read_protected_sources():
    def impossible(*args,**kwargs):
        raise AssertionError("must not connect")
    with pytest.raises(mod.DBAEvidenceHold):
        mod.diagnostic(run=impossible,is_root=False,now=NOW)


@pytest.mark.parametrize("bad",[
    {"archiver_failed_count":True},
    {"archiver_failed_count":-2},
    {"archive_mode_enabled":"on"},
    {"archive_mode_enabled":None},
    {"extra_unreviewed_field":True},
])
def test_untrusted_pg_catalogue_shape_refused(bad):
    row=catalogue(**bad)
    with pytest.raises(mod.DBAEvidenceHold):
        mod._archive_row(row)


@pytest.mark.parametrize("which",["pgbackrest","sql"])
def test_original_command_failure_does_not_leak_logs(which):
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        if (which=="pgbackrest" and len(calls)==1 or
                which=="sql" and len(calls)==2):
            return SimpleNamespace(
                returncode=1,stdout=b"password=protected-secret",
                stderr=b"password=protected-secret"
            )
        return SimpleNamespace(returncode=0,stdout=json.dumps(evidence()).encode())
    with pytest.raises(mod.DBAEvidenceHold) as exc:
        mod.diagnostic(run=run,is_root=True,now=NOW)
    assert "protected-secret" not in str(exc.value)


def test_nonprivileged_cli_is_a_guard_not_an_success(capsys,monkeypatch):
    monkeypatch.setattr(mod.os,"geteuid",lambda:1000)
    assert mod.main(["--read-only"])==2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="ORIGINAL_DBA_PROTECTED_READ_HELD"
    assert result["registry_ddl_executed"] is False
    assert result["database_writes"] is False
    assert result["execution_authority"]=="none"
