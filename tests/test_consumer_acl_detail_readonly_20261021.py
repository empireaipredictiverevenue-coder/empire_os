"""Exact live ACL booleans: no SQL mutation and no secret disclosures."""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from scripts import review_consumer_table_acl_detail_20261021 as diag

PASSWORD="fake-"+("a"*64)
TABLES=(
    "empire_consumer_subscriptions",
    "empire_consumer_consent_events",
    "empire_consumer_email_suppressions",
    "empire_consumer_one_time_tokens",
    "empire_consumer_delivery_receipts",
)
ORIGINAL=SimpleNamespace(
    DB="empiredb", LOGIN="empire_consumer_optin_login",
    WRITER="empire_consumer_optin_writer",TABLES=TABLES,
    read_custody=lambda:(PASSWORD,{})
)

class Connection:
    def __init__(self, fail_index=None, fail_field=2, fail_error=None):
        self.fail_index=fail_index
        self.fail_field=fail_field
        self.fail_error=fail_error
        self.queried=[]
        self.current="empire_consumer_optin_login"
        self.rollback_called=False
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params=()):
        self.queried.append((sql,params))
        if sql.startswith("SET LOCAL ROLE"):
            self.current="empire_consumer_optin_writer"
        if "has_table_privilege" in sql:
            if self.fail_error:
                raise self.fail_error
            idx=TABLES.index(params[1][len("public."):])
            result=[True]*4
            if idx==self.fail_index:
                result[self.fail_field]=False
            return SimpleNamespace(fetchone=lambda:tuple(result))
        if "SELECT session_user,current_user" in sql:
            return SimpleNamespace(fetchone=lambda:(
                "empire_consumer_optin_login",self.current,"empiredb","on"
            ))
        return SimpleNamespace(fetchone=lambda:None)
    def rollback(self):
        self.rollback_called=True


def run(conn):
    with patch.object(diag.os,"geteuid",return_value=0):
        return diag.diagnostic(original=ORIGINAL,connect=lambda **kw:conn)


def test_all_five_acl_boundary_checks_pass():
    conn=Connection()
    result=run(conn)
    assert result["status"]=="CONSUMER_ACL_READONLY_PASS"
    assert result["first_failed_table"]=="NONE"
    assert result["table_checks"]==[
        {"table":t,"status":"PASS","writer_select":True,
         "crm_app_select_denied":True,
         "crm_readonly_select_denied":True,
         "public_select_denied":True,"failed_checks":[]}
        for t in TABLES
    ]
    assert conn.rollback_called
    sql="; ".join(s for s,_ in conn.queried)
    assert "SET TRANSACTION READ ONLY" in sql
    assert "INSERT INTO" not in sql and "ALTER ROLE" not in sql
    assert "UPDATE public." not in sql
    assert "LIMIT 1" not in sql
    assert "password" not in json.dumps(result)


@pytest.mark.parametrize(("index","field","label"),[
    (0,0,"writer_select"),
    (1,1,"crm_app_select_denied"),
    (2,2,"crm_readonly_select_denied"),
    (3,3,"public_select_denied"),
    (4,1,"crm_app_select_denied")
])
def test_exact_failing_table_and_role_identified(index,field,label):
    result=run(Connection(fail_index=index,fail_field=field))
    assert result["status"]=="CONSUMER_ACL_READONLY_HOLD"
    assert result["first_failed_table"]==TABLES[index]
    assert result["first_failed_checks"]==[label]
    assert result["table_checks"][index]["failed_checks"]==[label]
    assert PASSWORD not in json.dumps(result)


def test_privileged_access_denied_before_loading_credentials():
    with patch.object(diag.os,"geteuid",return_value=1000):
        result=diag.diagnostic(original=ORIGINAL)
    assert result["first_failed_stage"]=="SOURCE"
    assert result["production_database_modified"] is False


def test_sql_error_is_redacted_and_stage_scoped():
    class SimulatedError(Exception):
        sqlstate="42704"
    conn=Connection(fail_error=SimulatedError("secret="+PASSWORD))
    result=run(conn)
    assert result["first_failed_stage"]=="TABLE_ACL"
    assert result["first_failed_table"]==TABLES[0]
    assert result["sqlstate"]=="42704"
    assert PASSWORD not in json.dumps(result)


def test_no_secret_or_data_fetched_by_acl_queries():
    result=run(Connection())
    assert result["subscriber_rows_fetched"] is False
    assert result["production_database_modified"] is False
    assert result["email_sent"] is False
    assert set(diag.LABELS)=={
        "writer_select","crm_app_select_denied",
        "crm_readonly_select_denied","public_select_denied"
    }
