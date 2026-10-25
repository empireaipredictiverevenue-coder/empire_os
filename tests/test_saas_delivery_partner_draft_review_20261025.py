"""Read-only single-partner sender gates; no real DB credential or email sent."""
from __future__ import annotations

import json
import pytest

from scripts import review_saas_delivery_partner_draft_20261025 as target


class Cursor:
    def __init__(self, *, suppressed=0, prior_exact=0, prior_domain=0,
                 valid_role=True, table_select=True, full_visibility=True):
        self.calls=[]
        self.fetched=[
            ("empire_outbound_sender","on",1234,False,False)
            if valid_role else ("postgres","off",1,True,True),
            (True,) if table_select else (False,),
            (False,False,False) if full_visibility else (True,True,True),
            (True,),
            (False,False,False),
            (suppressed,),
            (prior_exact,prior_domain),
        ]
        self.policies=[[],[]]
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params=None):
        self.calls.append((sql,params))
    def fetchone(self):
        return self.fetched.pop(0)
    def fetchall(self):
        return self.policies.pop(0)


class Connection:
    def __init__(self,**kwargs):
        self.cursor_obj=Cursor(**kwargs)
        self.rollbacks=0
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cursor_obj
    def rollback(self):self.rollbacks+=1


def make_conn(**kwargs):
    instance=Connection(**kwargs)
    return instance,lambda dsn,connect_timeout:instance


def test_clean_full_row_scan_still_cannot_authorize_send():
    conn,connect=make_conn()
    result=target.inspect("a_nonproduction_stub",connect_factory=connect)
    assert result["status"]=="NO_CANONICAL_BLOCK_OBSERVED_REVIEW_ONLY"
    assert result["counts_full_visibility_verified"] is True
    assert result["recipient"]=="dennis.lupo@teconomy.ch"
    assert result["founder_approval_for_this_send_verified"] is False
    assert result["outbound_authorized"] is False
    assert result["recipient_clearance_granted"] is False
    assert result["message_sent"] is False
    assert conn.rollbacks==1
    sql_calls=conn.cursor_obj.calls
    assert sql_calls[0][0]=="SET TRANSACTION READ ONLY"
    assert sql_calls[1][0]=="SET LOCAL ROLE empire_outbound_sender"
    assert sum("has_table_privilege" in sql for sql,_ in sql_calls)==2
    assert sum("pg_catalog.pg_policy" in sql for sql,_ in sql_calls)==2
    assert not any(sql.lstrip().upper().startswith(("INSERT","DELETE","UPDATE","ALTER","CREATE","DROP"))
                   for sql,_ in sql_calls)
    assert sql_calls[-2][1] == (
        "dennis.lupo@teconomy.ch","teconomy.ch","@teconomy.ch")
    assert sql_calls[-1][1] == (
        "dennis.lupo@teconomy.ch","teconomy.ch")


@pytest.mark.parametrize("suppressed,exact,domain",[
    (1,0,0),(0,1,1),(0,0,2),(5,2,5),
])
def test_suppressed_or_prior_company_contact_holds(suppressed,exact,domain):
    conn,connect=make_conn(
        suppressed=suppressed,prior_exact=exact,prior_domain=domain)
    x=target.inspect("stub",connect_factory=connect)
    assert x["status"]=="HOLD_CANONICAL_SUPPRESSION_OR_PREVIOUS_DOMAIN_OUTREACH"
    assert x["recipient_clearance_granted"] is False
    assert x["outbound_authorized"] is False


@pytest.mark.parametrize("counts",[
    (-1,0,0),(0,-1,0),(0,1,0),(0,0,-1),(True,0,0),
    (0,0,1.5),("0",0,0),
])
def test_fake_zero_and_inconsistent_counts_cannot_clear(counts):
    with pytest.raises(ValueError):
        target.decide(counts)


@pytest.mark.parametrize("overrides",[
    {"valid_role":False},{"table_select":False},{"full_visibility":False},
])
def test_missing_role_privilege_or_rls_visibility_fails_closed(overrides):
    conn,connect=make_conn(**overrides)
    with pytest.raises(ValueError):
        target.inspect("stub",connect_factory=connect)


def test_no_root_secret_fail_closed_and_no_traceback(monkeypatch,capsys):
    def deny(*args,**kwargs):raise PermissionError("NEVER_PRINT_A_SECRET")
    monkeypatch.setattr(target,"load_sender_dsn",deny)
    rc=target.main()
    obj=json.loads(capsys.readouterr().out)
    assert rc==2
    assert obj["status"]=="HOLD_EXISTING_PROTECTED_SENDER_READER_UNAVAILABLE"
    assert obj["outbound_authorized"] is False
    assert obj["recipient_clearance_granted"] is False
    assert "NEVER_PRINT_A_SECRET" not in json.dumps(obj)


def test_unexpected_database_driver_error_holds_without_exposing_dsn(
    monkeypatch,capsys,
):
    monkeypatch.setattr(target,"load_sender_dsn",lambda *_:"SECRET_SENTINEL_DSN")
    class DatabaseNotAvailable(Exception):pass
    def fail(*args,**kwargs):raise DatabaseNotAvailable("SENSITIVE_DRIVER_DETAIL")
    import sys
    class DummyModule:
        connect=staticmethod(fail)
    monkeypatch.setitem(sys.modules,"psycopg",DummyModule())
    code=target.main()
    payload=json.loads(capsys.readouterr().out)
    assert code==2
    assert payload["status"]=="HOLD_EXISTING_PROTECTED_SENDER_READER_UNAVAILABLE"
    assert payload["database_writes"] is False
    assert payload["message_sent"] is False
    assert "SECRET_SENTINEL_DSN" not in json.dumps(payload)
    assert "SENSITIVE_DRIVER_DETAIL" not in json.dumps(payload)
