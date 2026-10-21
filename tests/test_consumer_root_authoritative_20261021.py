"""One-shot, separated-authority production gate. Synthetic unit tests."""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import review_consumer_root_authoritative_20261021 as guard

DUMMY="synthetic_secret_"+"a"*64


def admin_state():
    return {
        "correct_database":True,
        "five_forced_rls_owned_tables":True,
        "exact_scoped_policies":True,
        "login_restricted":True,
        "writer_restricted":True,
        "exact_one_writer_membership":True,
        "table_acl":[{
            "name":name,"writer_select":True,"crm_denied":True,
            "readonly_denied":True,"public_denied":True
        } for name in guard.TABLES]
    }


def test_validated_admin_acl_safe_and_complete():
    pass_,details=guard._validated_admin_acl(admin_state())
    assert pass_ and len(details["tables"])==5
    assert all(details["checks"].values())


@pytest.mark.parametrize(("table_idx","field"),[
    (0,"crm_denied"),(1,"readonly_denied"),(2,"public_denied"),
    (3,"writer_select"),
])
def test_admin_hold_on_any_permission_drift(table_idx,field):
    state=admin_state()
    state["table_acl"][table_idx][field]=False
    passed,details=guard._validated_admin_acl(state)
    assert not passed
    assert details["tables"][guard.TABLES[table_idx]][field] is False


@pytest.mark.parametrize(("modification","expected"),[
    ("extra","INVALID"),("missing","INVALID"),("wrong_name","INVALID")
])
def test_invalid_admin_catalog_shape_denied(modification,expected):
    state=admin_state()
    if modification=="extra":
        state["table_acl"].append(state["table_acl"][0].copy())
    elif modification=="missing":
        state["table_acl"].pop()
    else:
        state["table_acl"][1]["name"]="other_tenant_table"
    passed,detail=guard._validated_admin_acl(state)
    assert not passed and detail["tables"]==expected


class FakeConnection:
    def __init__(self,fail_stage=None):
        self.user=guard.LOGIN
        self.last_role=guard.LOGIN
        self.calls=[]
        self.fail_stage=fail_stage
        self.rollback_called=False
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=()):
        self.calls.append((sql,params))
        if self.fail_stage=="connect":
            raise RuntimeError("NO_AUTH_"+DUMMY)
        if sql=="SET LOCAL ROLE "+guard.WRITER:
            self.last_role=guard.WRITER
        if "SELECT session_user,current_user,current_database()" in sql:
            value=(guard.LOGIN,self.last_role,guard.DB,"on")
        elif "has_table_privilege(current_user" in sql:
            value=(True,)
        else:
            value=None
        return SimpleNamespace(fetchone=lambda:value)
    def rollback(self):self.rollback_called=True


def original_stub():
    return SimpleNamespace(read_custody=lambda:(DUMMY,{}))


def test_pass_on_original_credential_and_isolated_admin():
    connection=FakeConnection()
    with patch.object(guard.os,"geteuid",return_value=0):
        result=guard.check(
            original=original_stub(),admin=admin_state,
            connect=lambda **kwargs:connection
        )
    assert result["status"]=="CONSUMER_ROOT_AND_LOGIN_READONLY_VERIFIED"
    assert result["authoritative_admin_acl"] is True
    assert connection.rollback_called
    assert result["email_sent"] is False
    assert result["database_modified"] is False
    assert result["subscriber_rows_fetched"] is False
    all_sql=" ".join(sql for sql,_ in connection.calls)
    assert "SET TRANSACTION READ ONLY" in all_sql
    assert all_sql.count(" LIMIT 0")==5
    assert "has_table_privilege('empiredb_app'" not in all_sql
    assert "INSERT INTO" not in all_sql and "CREATE ROLE" not in all_sql
    assert DUMMY not in json.dumps(result)


def test_only_admin_checks_other_role_permission_and_guards_drift():
    state=admin_state()
    state["table_acl"][2]["crm_denied"]=False
    with patch.object(guard.os,"geteuid",return_value=0):
        result=guard.check(
            original=original_stub(),admin=lambda:state,
            connect=lambda **kwargs:pytest.fail("should not access consumer DB")
        )
    assert result["status"]=="CONSUMER_ROOT_ACL_HOLD"
    assert result["catalogue"]["tables"][guard.TABLES[2]]["crm_denied"] is False


def test_sql_errors_are_only_classified_no_secret_strings():
    with patch.object(guard.os,"geteuid",return_value=0):
        result=guard.check(
            original=original_stub(),admin=admin_state,
            connect=lambda **kw:(_ for _ in ()).throw(
                RuntimeError("FATAL password="+DUMMY)
            )
        )
    assert result["status"]=="CONSUMER_ROOT_READONLY_HOLD"
    assert result["step"]=="SCOPED_LOGIN"
    assert DUMMY not in json.dumps(result)
    assert "FATAL" not in json.dumps(result)


def test_root_only_denies_dba_and_credentials_before_read(monkeypatch):
    monkeypatch.setattr(guard.os,"geteuid",lambda:1000)
    result=guard.check(
        original=original_stub(),
        admin=lambda:pytest.fail("DB queried as unprivileged"),
    )
    assert result["step"]=="ROOT"
    assert result["status"]=="CONSUMER_ROOT_READONLY_HOLD"


def test_source_contract_no_mutations_and_independent_privilege_boundary():
    from pathlib import Path
    source=Path(guard.__file__).read_text()
    assert "BEGIN READ ONLY;" in guard.ADMIN_SQL
    assert "SET TRANSACTION READ ONLY" in source
    assert "LIMIT 0" in source
    assert "--apply" not in source
    assert "GRANT empire_consumer_optin_writer" not in source
    assert "REVOKE SELECT" not in source
    assert "has_table_privilege(\n        'empiredb_app'" in guard.ADMIN_SQL
    assert "has_table_privilege(current_user" in source
    assert "ROOT_SOURCE" not in source or guard.ORIGINAL_SHA256
