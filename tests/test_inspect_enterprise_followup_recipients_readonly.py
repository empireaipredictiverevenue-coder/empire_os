"""Offline contract tests for a narrow, no-send EmpireDB enterprise review."""
from __future__ import annotations

import pytest

from scripts import inspect_enterprise_followup_recipients_readonly as subject


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []
        self.parameters = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.statements.append(sql.strip())
        self.parameters.append(params)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.reader = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.reader


def rows(suppressed=False):
    return [
        ("kmartin@sila.com", suppressed, 1, 0),
        ("richard@redwoodservices.com", False, 2, 1),
    ]


def test_all_subjects_stay_held_even_when_not_suppressed():
    c = FakeConnection(rows())
    result = subject.check("TEST_ONLY", connect_factory=lambda _: c)
    assert result["mode"] == "OBSERVE"
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False
    assert result["founder_send_authorized"] is False
    assert set(result["recipients"]) == set(subject.RECIPIENTS)
    for value in result["recipients"].values():
        assert value["recipient_send_authorized"] is False
        assert value["decision"] == "HOLD_PRIOR_GMAIL_CONTACT_AND_FOUNDER_SEND_GATES"
    assert c.reader.statements[0] == "SET TRANSACTION READ ONLY"
    assert c.reader.statements[1].startswith("SET LOCAL statement_timeout")
    assert c.reader.statements[-1] == "ROLLBACK"
    assert c.reader.parameters[2] == (list(subject.RECIPIENTS),)
    sql = c.reader.statements[2].lower()
    for clause in ("outbound_suppressions", "outbound_intents", "outbound_events",
                   "split_part(t.email", "lower(btrim", "channel='email'"):
        assert clause in sql
    for forbidden in ("insert into ", "delete from ", "update public.",
                      "drop table ", "alter table ", "grant "):
        assert forbidden not in sql


def test_canonical_suppressed_recipient_always_held():
    result = subject.check("TEST_ONLY", connect_factory=lambda _: FakeConnection(rows(True)))
    assert result["recipients"]["kmartin@sila.com"]["decision"] == "HOLD_SUPPRESSED"
    assert result["recipients"]["richard@redwoodservices.com"]["recipient_send_authorized"] is False


@pytest.mark.parametrize("invalid", [
    [], [rows()[0]], [rows()[0], rows()[0], rows()[1]],
    [("rogue@example.com", False, 0, 0), rows()[0]],
    [("kmartin@sila.com", None, 0, 0), rows()[1]],
    [("kmartin@sila.com", False, -1, 0), rows()[1]],
    [("kmartin@sila.com", False, True, 0), rows()[1]],
])
def test_missing_duplicate_or_invalid_db_evidence_fails_closed(invalid):
    with pytest.raises(ValueError):
        subject.check("TEST_ONLY", connect_factory=lambda _: FakeConnection(invalid))


@pytest.mark.parametrize("dsn", ["", None, "   "])
def test_empty_canonical_dsn_fails_closed(dsn):
    with pytest.raises(ValueError):
        subject.check(dsn, connect_factory=lambda _: FakeConnection(rows()))


def test_database_failure_prints_only_restricted_hold(monkeypatch, capsys):
    monkeypatch.delenv("EMPIREDB_DSN", raising=False)
    assert subject.main() == 2
    out = capsys.readouterr().out
    assert "HELD_CANONICAL_READER_UNAVAILABLE" in out
    assert "recipient_send_authorized" in out
    assert "password" not in out.lower()
