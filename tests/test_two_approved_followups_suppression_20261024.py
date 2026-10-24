"""Two approved followups: canonical read-only proof fail-closed fixtures."""
from __future__ import annotations

import pytest
from scripts import inspect_two_approved_followups_suppression_20261024 as m


class Cursor:
    def __init__(self, *, suppressed=None, ro=True, role=m.ROLE,
                 full_visibility=True, malformed=False):
        self.suppressed=suppressed or {}
        self.ro=ro
        self.role=role
        self.full_visibility=full_visibility
        self.malformed=malformed
        self.sql=""
        self.params=()
        self.rows_seen=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):
        assert "INSERT " not in sql.upper() and "DELETE " not in sql.upper()
        assert "UPDATE " not in sql.upper()
        self.sql=sql
        self.params=params or ()
        self.rows_seen.append(sql)
    def fetchone(self):
        if self.sql==m.SQL_IDENTITY:
            return (self.role,"on" if self.ro else "off",803,False,False)
        if "has_table_privilege" in self.sql:return (True,)
        if self.sql==m.SQL_TABLE:
            return (False,False,False) if self.full_visibility else (True,True,True)
        if self.sql==m.SQL_SUPPRESSIONS:
            return ("0",) if self.malformed else (self.suppressed.get(self.params[0],0),)
        if self.sql==m.SQL_HISTORY:return (1,)
        raise AssertionError("unexpected fetchone")
    def fetchall(self):
        assert self.sql==m.SQL_POLICIES
        return []


class Conn:
    def __init__(self,cur):self.cur=cur
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cur


def factory_for(cursor):
    def factory(dsn,*,connect_timeout):
        assert dsn=="test-mock-dsn"
        assert connect_timeout==5
        return Conn(cursor)
    return factory


def test_two_exact_recipients_verified_but_no_send_authority():
    cur=Cursor()
    r=m.assess("test-mock-dsn",connect_factory=factory_for(cur))
    assert r["status"]=="SUPPRESSION_CLEAR_FOR_MANUAL_SEND_REVIEW"
    assert r["full_row_visibility_verified"] is True
    assert r["transaction"]=="READ_ONLY"
    assert [x["recipient"] for x in r["recipients"]]==list(m.RECIPIENTS)
    assert all(x["suppression_verified_clear"] for x in r["recipients"])
    assert all(x["canonical_prior_intent_count"]==1 for x in r["recipients"])
    assert r["outbound_send_authorized"] is False
    assert r["gmail_messages_sent"] is False
    assert r["database_writes"] is False
    assert sum(x==m.SQL_SUPPRESSIONS for x in cur.rows_seen)==2
    assert sum(x==m.SQL_HISTORY for x in cur.rows_seen)==2


@pytest.mark.parametrize("recipient",m.RECIPIENTS)
def test_suppression_match_blocks(recipient):
    r=m.assess("test-mock-dsn",connect_factory=factory_for(Cursor(suppressed={recipient:1})))
    assert r["status"]=="HELD_CANONICAL_SUPPRESSION_MATCH"
    assert r["outbound_send_authorized"] is False


@pytest.mark.parametrize("kwargs",[
    {"ro":False},{"role":"postgres"},{"full_visibility":False},{"malformed":True}
])
def test_bad_role_visibility_or_counts_fail_closed(kwargs):
    with pytest.raises(ValueError):
        m.assess("test-mock-dsn",connect_factory=factory_for(Cursor(**kwargs)))


def test_credentials_required():
    with pytest.raises(ValueError,match="CREDENTIAL_REQUIRED"):
        m.assess("",connect_factory=factory_for(Cursor()))


def test_fixed_cohort_and_no_sending_code():
    assert m.RECIPIENTS==("info@spcgc.com","team@dentalranking.co.uk")
    assert m.TABLE=="public.outbound_suppressions"
    assert "INSERT " not in m.SQL_SUPPRESSIONS
    assert "DELETE " not in m.SQL_SUPPRESSIONS
