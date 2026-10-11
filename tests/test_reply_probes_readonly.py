"""Three bounded reply diagnostics must stay read-only, aggregate-only, and fail closed.

All database interactions are simulated; no real credentials, contacts, network or writes.
"""
from __future__ import annotations

import json
import re

import pytest

from scripts import (
    probe_reply_event_lifecycle,
    probe_reply_identity_lineage,
    probe_reply_provider_metadata,
)

PROBES = (
    probe_reply_event_lifecycle,
    probe_reply_identity_lineage,
    probe_reply_provider_metadata,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []
        self.last_result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        assert query == "BEGIN READ ONLY" or query.lstrip().upper().startswith("SELECT ")
        assert ";" not in query.strip().rstrip(";"), "no multiple statements"
        if params is not None:
            assert len(params) == 1
        self.last_result = self.rows.pop(0) if query != "BEGIN READ ONLY" else []

    def fetchall(self):
        return self.last_result


class FakeConnection:
    def __init__(self, rows):
        self.cur = FakeCursor(list(rows))
        self.rollback_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cur

    def rollback(self):
        self.rollback_count += 1


def run_mocked(monkeypatch, capsys, module, rows):
    connection = FakeConnection(rows)
    calls = []

    def connect(dsn, *, connect_timeout):
        calls.append((dsn, connect_timeout))
        assert dsn == "fake-readonly-dsn"
        assert connect_timeout == 8
        return connection

    monkeypatch.setenv("EMPIREDB_DSN", "fake-readonly-dsn")
    monkeypatch.setattr(module.psycopg, "connect", connect)
    module.main()
    result = json.loads(capsys.readouterr().out)
    assert calls == [("fake-readonly-dsn", 8)]
    assert connection.rollback_count == 1
    assert connection.cur.statements[0][0] == "BEGIN READ ONLY"
    assert all(q == "BEGIN READ ONLY" or q.lstrip().upper().startswith("SELECT ")
               for q, _ in connection.cur.statements)
    assert result["mode"] == "OBSERVE"
    assert result["outbound_authorized"] is False
    assert result["admission_authorized"] is False
    return result, connection.cur.statements


@pytest.mark.parametrize("module", PROBES)
def test_missing_dsn_refuses_to_probe(monkeypatch, module):
    monkeypatch.delenv("EMPIREDB_DSN", raising=False)

    def no_connect(*args, **kwargs):
        raise AssertionError("unauthorised database connection")

    monkeypatch.setattr(module.psycopg, "connect", no_connect)
    with pytest.raises(SystemExit, match="EMPIREDB_DSN unavailable"):
        module.main()


def test_event_lifecycle_aggregates_without_leaking_ids(monkeypatch, capsys):
    rows = [
        [("private-message-id", "private-intent"), ("unmatched-private", "other-intent")],
        [("private-message-id", "private-intent", "reply_received"),
         ("private-message-id", "private-intent", "reply_classified"),
         ("private-message-id", "private-intent", "reply_classified")],
    ]
    result, statements = run_mocked(
        monkeypatch, capsys, probe_reply_event_lifecycle, rows
    )
    assert result["reply_count"] == 2
    assert sum(p["reply_count"] for p in result["lifecycle_patterns"]) == 2
    assert any(p["pattern"]["event_types"].get("reply_received") == 1
               for p in result["lifecycle_patterns"])
    assert "private-message-id" not in json.dumps(result)
    assert "private-intent" not in json.dumps(result)
    assert "LIMIT 100" in statements[1][0]
    assert "LIMIT 2000" in statements[2][0]


def test_provider_metadata_reports_keys_only(monkeypatch, capsys):
    rows = [[
        ({"provider_thread_id": "private-thread-123",
          "tenant_id": "private-tenant",
          "sender_email": "private@example.test",
          "message_body": "SECRET_HOMEOWNER_MESSAGE"},),
        ({"provider_thread_id": "", "authenticated": False},),
        ("malformed-row",),
    ]]
    result, statements = run_mocked(
        monkeypatch, capsys, probe_reply_provider_metadata, rows
    )
    assert result["reply_count"] == 3
    assert result["metadata_types"] == {"non_object": 1, "object": 2}
    assert result["recognized_evidence_key_coverage"]["provider_thread_id"] == 1
    assert result["recognized_evidence_key_coverage"]["tenant_id"] == 1
    assert result["values_exposed"] is False
    assert result["provider_thread_authenticated"] is False
    assert result["contact_authenticated"] is False
    assert result["tenant_authenticated"] is False
    assert "SECRET_HOMEOWNER_MESSAGE" not in json.dumps(result)
    assert "private@example.test" not in json.dumps(result)
    assert "private-thread-123" not in json.dumps(result)
    assert "LIMIT 100" in statements[1][0]


def test_lineage_reports_structure_not_identity(monkeypatch, capsys):
    rows = [
        [("secret-intent-a",), ("secret-intent-b",), ("secret-intent-c",)],
        [("secret-intent-a",), ("secret-intent-b",)],
        [("secret-intent-a",)],
    ]
    result, statements = run_mocked(
        monkeypatch, capsys, probe_reply_identity_lineage, rows
    )
    assert result["reply_count"] == 3
    assert result["structural_counts"] == {
        "conversation_missing": 2, "conversation_unique": 1,
        "intent_missing": 1, "intent_unique": 2,
    }
    for key in ("provider_thread_authenticated", "contact_authenticated",
                "tenant_authenticated"):
        assert result[key] is False
    assert "secret-intent" not in json.dumps(result)
    assert "LIMIT 100" in statements[1][0]
    assert len(statements) == 4
    assert all(params is not None for _, params in statements[2:])
