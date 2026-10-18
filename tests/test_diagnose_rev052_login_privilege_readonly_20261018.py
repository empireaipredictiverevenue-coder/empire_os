"""REV052 pure observe-only denied-function diagnostic tests."""
from __future__ import annotations
import json
from types import SimpleNamespace

from scripts import diagnose_rev052_login_privilege_readonly_20261018 as probe


def test_catalog_calls_are_metadata_only():
    assert len(probe.PROBES)==5
    assert probe.PROBES[0][0]=="identity"
    assert "has_schema_privilege" in probe.PROBES[1][1]
    assert all(
        query.startswith("SELECT ") and "commercial_events FROM" not in query
        for _,query in probe.PROBES
    )
    assert probe.ZERO_EVENT=="00000000-0000-4000-8000-000000000000"


def test_wrong_or_missing_explicit_flag_never_reads_credentials(monkeypatch,capsys):
    assert probe.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_REQUIRED" in capsys.readouterr().out
    monkeypatch.setattr(probe.os,"geteuid",lambda:1000)
    assert probe.main(["--read-only"])==2
    assert "HOLD_ROOT_LOCAL_READONLY_REQUIRED" in capsys.readouterr().out


def test_private_credential_error_redacts_secret():
    def deny():
        raise RuntimeError("veryprivate-production-pass")
    result=probe.diagnose(password_reader=deny)
    assert result["failure_stage"]=="PRIVATE_CREDENTIAL_CUSTODY"
    assert "veryprivate" not in json.dumps(result)
    assert result["permission_changes"] is False
    assert result["database_writes"] is False
    assert result["real_event_rows_read"]==0


def test_failed_connection_only_prints_sqlstate():
    class Denied(Exception):
        sqlstate="28P01"
    def fake_connect(**kwargs):
        raise Denied("password=secret")
    result=probe.diagnose(password_reader=lambda:"hidden",
                          connector=fake_connect)
    assert result["sqlstate"]=="28P01"
    assert result["authenticated"] is False
    assert result["status"].startswith("HOLD_")
    assert "secret" not in json.dumps(result)
    assert "hidden" not in json.dumps(result)


def test_sqlstate_field_limits_to_five_alphanumeric():
    assert probe._code(SimpleNamespace(sqlstate="42501"))=="42501"
    assert probe._code(SimpleNamespace(sqlstate="28P01"))=="28P01"
    assert probe._code(SimpleNamespace(sqlstate="unexpected_secret"))=="UNAVAILABLE"
    assert probe._code(SimpleNamespace(sqlstate=None))=="UNAVAILABLE"


class SampleCursor:
    def __init__(self, *, denial_at=None):
        self.denial_at=denial_at
        self.calls=[]
    def execute(self,statement,params=None):
        self.calls.append((statement,params))
        if (self.denial_at is not None and
            statement == self.denial_at):
            class Denied(Exception):
                sqlstate="42501"
            raise Denied("do not print denial text")
        return self
    def fetchone(self):
        return (False,)


def test_permission_denial_is_recovered_by_savepoint_no_sql_error_printed():
    sql=probe.PROBES[2][1]
    cur=SampleCursor(denial_at=sql)
    result=probe._bool_query(cur,"raw_commercial_select",sql)
    assert result=={
        "status":"HOLD","reason":"POSTGRES_PRIVILEGE_OR_QUERY_ERROR",
        "sqlstate":"42501",
    }
    cmds=[x[0] for x in cur.calls]
    assert "ROLLBACK TO SAVEPOINT rev052_probe" in cmds
    assert "RELEASE SAVEPOINT rev052_probe" in cmds
    assert "do not print" not in json.dumps(result)


def test_successful_metadata_boolean_releases_savepoint():
    cur=SampleCursor()
    sql=probe.PROBES[1][1]
    result=probe._bool_query(cur,"schema_public_usage",sql)
    assert result == {"status":"PASS","value":False}
    cmds=[x[0] for x in cur.calls]
    assert "SAVEPOINT rev052_probe" in cmds
    assert "RELEASE SAVEPOINT rev052_probe" in cmds
    assert "ROLLBACK TO SAVEPOINT rev052_probe" not in cmds
