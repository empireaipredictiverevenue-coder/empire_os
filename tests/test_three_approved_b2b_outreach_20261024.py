"""Safety checks for the exact three-company canonical read-only preflight."""
from __future__ import annotations

import pytest
from scripts import inspect_three_approved_b2b_outreach_20261024 as m


class FakeCursor:
    def __init__(self, *, block=None, prior=None, trusted_role=True,
                 full_rows=True, bad_counts=False):
        self.block = block or {}
        self.prior = prior or {}
        self.trusted_role = trusted_role
        self.full_rows = full_rows
        self.bad_counts = bad_counts
        self.sql = ""
        self.params = ()
        self.writes = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params
        assert not any(verb in sql.upper() for verb in
                       ("INSERT INTO", "DELETE FROM", "UPDATE PUBLIC.",
                        "TRUNCATE ", "ALTER TABLE ", "CREATE TABLE "))
        self.writes.append(sql)
    def fetchone(self):
        if self.sql == m.SQL_IDENTITY:
            return ((m.ROLE if self.trusted_role else "postgres"), "on", 212,
                    False, False)
        if "has_table_privilege" in self.sql:
            return (True,)
        if self.sql == m.SQL_TABLE:
            return (False, False, False) if self.full_rows else (True, True, True)
        if self.sql == m.SQL_SUPPRESSIONS:
            return (self.block.get(self.params[0], 0),)
        if self.sql == m.SQL_HISTORY:
            return ("0", 0) if self.bad_counts else (
                0, self.prior.get(self.params[1], 0)
            )
        raise AssertionError("unknown query")
    def fetchall(self):
        assert self.sql == m.SQL_POLICIES
        return []


class FakeConn:
    def __init__(self, cursor):
        self.cursor_obj = cursor
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def cursor(self):
        return self.cursor_obj


def factory(c):
    def connect(dsn, *, connect_timeout):
        assert dsn == "fixture-only"
        assert connect_timeout == 5
        return FakeConn(c)
    return connect


def test_exact_three_clean_but_not_permission_to_send():
    c = FakeCursor()
    report = m.inspect("fixture-only", connect_factory=factory(c))
    assert report["status"] == "THREE_RECIPIENTS_CLEAR_FOR_MANUAL_GMAIL_SEND"
    assert [row["recipient"] for row in report["recipients"]] == list(m.RECIPIENTS)
    assert all(row["clear"] for row in report["recipients"])
    assert report["new_outbound_authorized_by_this_preflight"] is False
    assert report["new_message_sent"] is False
    assert report["database_writes"] is False
    assert sum(sql == m.SQL_SUPPRESSIONS for sql in c.writes) == 3
    assert sum(sql == m.SQL_HISTORY for sql in c.writes) == 3


@pytest.mark.parametrize("addr", m.RECIPIENTS)
def test_exact_or_domain_suppressed(addr):
    report = m.inspect(
        "fixture-only",
        connect_factory=factory(FakeCursor(block={addr: 1}))
    )
    assert report["status"] == "HOLD_CANONICAL_SUPPRESSION_OR_PRIOR_OUTREACH"
    assert next(x for x in report["recipients"] if x["recipient"] == addr)["clear"] is False


@pytest.mark.parametrize("addr", m.RECIPIENTS)
def test_other_company_contact_prior_intent_holds(addr):
    domain = addr.rsplit("@", 1)[1]
    report = m.inspect(
        "fixture-only",
        connect_factory=factory(FakeCursor(prior={domain: 1}))
    )
    assert report["status"] == "HOLD_CANONICAL_SUPPRESSION_OR_PRIOR_OUTREACH"
    assert next(x for x in report["recipients"] if x["recipient"] == addr)["clear"] is False


@pytest.mark.parametrize("options", (
    {"trusted_role": False}, {"full_rows": False}, {"bad_counts": True},
))
def test_untrusted_count_or_db_role_fails_closed(options):
    with pytest.raises(ValueError):
        m.inspect("fixture-only", connect_factory=factory(FakeCursor(**options)))


def test_missing_protected_dsn_fails_closed():
    with pytest.raises(ValueError, match="CREDENTIAL_REQUIRED"):
        m.inspect("", connect_factory=factory(FakeCursor()))


def test_limited_fixed_cohort():
    assert m.RECIPIENTS == (
        "hello@roofingdemandlab.com",
        "insights@sectorial.io",
        "enquiries@connectcf.com",
    )
