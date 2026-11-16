"""Proof-only diagnostic for original one-tenant SCRAM census reader.

No production grant, no credentials printed and no additional source stream.
"""
from datetime import date, datetime, timezone
import json

import pytest

from scripts.activate_predictive_native_reader_existing_login_20261116 import (
    LOGIN, diagnose_readonly, _safe_error_category,
)


class FakeCursor:
    def __init__(self, deny_at=None, denied=None):
        self.calls=[]
        self.deny_at=deny_at
        self.denied=denied
        self.last=""
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, query, *_params):
        self.last=query
        self.calls.append(query)
        if self.deny_at and self.deny_at in query:
            raise self.denied or RuntimeError("fail")
    def fetchone(self):
        if "current_database(),session_user" in self.last:
            return ("empiredb",LOGIN,"on")
        return (
            date(2026,11,15),"708efd4b-53b2-43d7-961d-1cecab67f17a",
            0,0,0,0,0,datetime(2026,11,16,tzinfo=timezone.utc)
        )


class FakeConnection:
    def __init__(self, cur):
        self.cur=cur
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def cursor(self):
        return self.cur


def setup_pgpass(tmp_path, target=None):
    path=tmp_path/"reader.pgpass"
    path.write_text(
        (target or "/var/run/postgresql:5432:empiredb:"+LOGIN)+
        ":synthetic-not-a-real-secret\n"
    )
    path.chmod(0o600)
    return path


def test_readonly_diagnostic_reaches_original_census_without_writes(tmp_path):
    path=setup_pgpass(tmp_path)
    cursor=FakeCursor()
    def connect(dsn):
        assert "passfile=" in dsn
        assert "password=" not in dsn
        return FakeConnection(cursor)
    result=diagnose_readonly(
        path_provider=lambda:path,
        catalog_reader=lambda:{"existing_membership":False},
        connect_factory=connect,
    )
    assert result["status"]=="ORIGINAL_READER_DIAGNOSTIC_PASSED",result
    assert all(result["observations"].values())
    assert result["database_writes"] is False
    assert result["registry_role_currently_granted"] is False
    sql="\n".join(cursor.calls)
    assert "SET TRANSACTION READ ONLY" in sql
    assert "SET LOCAL ROLE empire_predictive_revenue_evidence_reader" in sql
    assert "read_predictive_revenue_day_v1" in sql
    assert all(part not in sql.upper() for part in ("GRANT ", "CREATE ROLE", "DELETE FROM", "INSERT INTO"))


def test_wrong_pgpass_target_returns_safe_hold_without_connection(tmp_path):
    path=setup_pgpass(tmp_path,target="localhost:5432:postgres:"+LOGIN)
    result=diagnose_readonly(
        path_provider=lambda:path,
        catalog_reader=lambda:pytest.fail("not needed"),
        connect_factory=lambda _dsn:pytest.fail("unexpected connect"),
    )
    assert result["status"]=="ORIGINAL_READER_DIAGNOSTIC_HOLD"
    assert result["failure"]=="PGPASS_TARGET_MISMATCH"
    assert result["database_writes"] is False
    assert "synthetic" not in str(result)


def test_scram_auth_failure_category_does_not_expose_secret(tmp_path):
    path=setup_pgpass(tmp_path)
    result=diagnose_readonly(
        path_provider=lambda:path,
        catalog_reader=lambda:{"existing_membership":False},
        connect_factory=lambda _:(_ for _ in ()).throw(RuntimeError(
            "password authentication failed for secret-fake-user"))
    )
    assert result["stage"]=="ORIGINAL_SCRAM_CONNECTION"
    assert result["failure"]=="SCRAM_PASSWORD_REJECTED"
    assert "secret-fake-user" not in str(result)


def test_restricted_role_sqlstate_denial_is_isolated(tmp_path):
    class FakeDenied(Exception):
        sqlstate="42501"
    path=setup_pgpass(tmp_path)
    cursor=FakeCursor(deny_at="SET LOCAL ROLE",denied=FakeDenied("private"))
    result=diagnose_readonly(
        path_provider=lambda:path,
        catalog_reader=lambda:{"existing_membership":False},
        connect_factory=lambda _:FakeConnection(cursor))
    assert result["stage"]=="ORIGINAL_REV052_CENSUS_ROLE"
    assert result["failure"]=="SQL_PERMISSION_DENIED_42501"
    assert not result["observations"]["original_rev077_census_query_executed"]
    assert "private" not in str(result)


def test_wrong_source_day_is_distinguished_from_login_denial(tmp_path):
    class FakeIncomplete(Exception):
        sqlstate="P0001"
    path=setup_pgpass(tmp_path)
    cursor=FakeCursor(
        deny_at="read_predictive_revenue_day_v1",
        denied=FakeIncomplete("sensitive original events"))
    result=diagnose_readonly(
        path_provider=lambda:path,
        catalog_reader=lambda:{"existing_membership":False},
        connect_factory=lambda _:FakeConnection(cursor))
    assert result["observations"]["scram_authenticated_login"] is True
    assert result["observations"]["original_restricted_census_role_set"] is True
    assert result["stage"]=="ORIGINAL_REV077_SOURCE_DAY"
    assert result["failure"]=="SOURCE_DAY_INCOMPLETE_OR_TENANT_REJECTED_P0001"
    assert "sensitive original events" not in str(result)
