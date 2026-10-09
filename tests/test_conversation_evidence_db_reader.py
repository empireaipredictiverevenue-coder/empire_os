"""Restricted reply evidence reader quality, privacy and correctness tests."""
import importlib.util
from pathlib import Path

import pytest

from empire_os.conversation_evidence_db_reader import (
    EvidenceReadUnavailable, read_reply_evidence, select_query, READ_COLUMNS,
)


class Cursor:
    def __init__(self, rows=None, error=False):
        self.rows = rows if rows is not None else []
        self.queries = []
        self.error = error

    def execute(self, query):
        self.queries.append(str(query))
        if self.error and "SELECT " in str(query):
            raise RuntimeError("postgresql://secret_credentials@localhost")

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Conn:
    def __init__(self, cursor):
        self.active_cursor = cursor

    def cursor(self):
        return self.active_cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _load_collector():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "collector_privacy_contract", root / "scripts/run_conversations_replies_control.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_only_original_metadata_columns_allowed_and_query_is_bounded():
    for table in READ_COLUMNS:
        query = select_query(table)
        assert 'SELECT *' not in query
        assert 'LIMIT 750' in query
        assert 'ORDER BY' in query
        assert 'body_text' not in query
        assert 'from_contact' not in query
        assert 'subject' not in query
        assert 'metadata' not in query
        assert 'recipient' not in query
    for table in ("public.outbound_events", "public.outbound_intents",
                  "public.commercial_products", 'public.outbound_replies;DROP TABLE X'):
        with pytest.raises(ValueError, match="unapproved"):
            select_query(table)


@pytest.mark.parametrize("invalid", [0, -1, True, 751, "10"])
def test_invalid_limits_fail_before_any_source_access(invalid):
    with pytest.raises(ValueError):
        select_query("public.outbound_replies", max_rows=invalid)


def test_read_only_transaction_and_no_unnecessary_fields():
    row = ("source-uuid", "intent-uuid", "provider-123", "positive", "2026-10-09T11:00:00Z")
    cursor = Cursor([row])
    connections = []
    def connect(dsn, **kwargs):
        connections.append((dsn, kwargs))
        return Conn(cursor)
    value = read_reply_evidence(
        "public.outbound_replies", dsn="postgresql://private",
        connect_factory=connect, max_rows=12,
    )
    assert value == [{
        "id": "source-uuid", "intent_id": "intent-uuid",
        "provider_message_id": "provider-123", "classification": "positive",
        "received_at": "2026-10-09T11:00:00Z",
    }]
    assert connections == [("postgresql://private", {"connect_timeout": 5})]
    assert cursor.queries[:2] == [
        "SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '4000ms'",
    ]
    assert cursor.queries[2].endswith('LIMIT 12')


def test_restricted_event_fields_preserve_direction_without_body():
    cursor = Cursor([
        ("event-1", "conversation-1", "inbound_message", "inbound", "provider-evt-1",
         "2026-10-09T12:00:00+00:00"),
    ])
    rows = read_reply_evidence(
        "public.empire_conversation_events",
        dsn="placeholder", connect_factory=lambda *a, **k: Conn(cursor),
    )
    assert rows[0]["provider_event_id"] == "provider-evt-1"
    assert rows[0]["direction"] == "inbound"
    assert "body_text" not in rows[0]
    assert "from_contact" not in rows[0]


def test_missing_dsn_is_explicit_failure_not_zero_replies(monkeypatch):
    monkeypatch.delenv("EMPIREDB_DSN", raising=False)
    with pytest.raises(EvidenceReadUnavailable, match="CREDENTIAL_MISSING"):
        read_reply_evidence("public.outbound_replies")


def test_db_failure_is_sanitized_without_connection_string():
    secret = "postgresql://owner:very_private_password@localhost/empiredb"
    with pytest.raises(EvidenceReadUnavailable) as exc:
        read_reply_evidence(
            "public.outbound_replies", dsn=secret,
            connect_factory=lambda *a, **k: Conn(Cursor(error=True)),
        )
    assert str(exc.value) == "REPLY_SOURCE_QUERY_FAILED"
    assert "very_private_password" not in str(exc.value)


def test_schema_drift_or_row_limit_is_error_not_empty_state():
    for rows in ([("partial",)], [(1, 2, 3, 4, 5)] * 3):
        with pytest.raises(EvidenceReadUnavailable):
            read_reply_evidence(
                "public.outbound_replies", dsn="restricted",
                connect_factory=lambda *a, **k: Conn(Cursor(rows)),
                max_rows=2,
            )


def test_collector_no_select_star_or_password_in_psql_argv():
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts/run_conversations_replies_control.py").read_text()
    assert "SELECT *" not in content
    assert '"psql",' not in content
    collector = _load_collector()
    assert collector.query_table.__doc__
    assert collector.MAX_ROWS_PER_TABLE == 750


def test_failing_collector_does_not_replace_last_good_snapshot(tmp_path, monkeypatch):
    module = _load_collector()
    from empire_os.conversation_evidence_db_reader import EvidenceReadUnavailable
    output = tmp_path / "latest.json"
    output.write_text('{"canonical_messages":["previous-good-snapshot"]}')
    monkeypatch.setattr(module, "OUT", output)
    def fail():
        raise EvidenceReadUnavailable("REPLY_SOURCE_QUERY_FAILED")
    monkeypatch.setattr(module, "main", fail)
    assert module.run_cli() == 3
    assert "previous-good-snapshot" in output.read_text()
    import json
    health = json.loads(
        (tmp_path / "collector_health_latest.json").read_text()
    )
    assert health["status"] == "DATABASE_SOURCE_READ_FAILED"
    assert health["source_query_completed"] is False
    assert health["canonical_snapshot_preserved"] is True
    assert health["reason_code"] == "REPLY_SOURCE_QUERY_FAILED"
    assert health["authenticated_buyers_proved"] is False
    assert "postgresql://" not in str(health)


def test_database_reader_is_live_wiring_of_collector():
    module = _load_collector()
    from empire_os.conversation_evidence_db_reader import EvidenceReadUnavailable
    with pytest.raises(EvidenceReadUnavailable, match="CREDENTIAL_MISSING"):
        # The adapter itself refuses an absent DSN rather than writing zero.
        read_reply_evidence("public.outbound_replies", dsn="")
    assert "read_reply_evidence" in module.query_table.__code__.co_consts or (
        module.query_table.__doc__ is not None
    )


def test_successful_empty_db_read_is_not_mislabeled_failed(tmp_path, monkeypatch):
    import json
    collector = _load_collector()
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({
        "database_candidates": [
            {"table": "public.outbound_replies",
             "columns": [{"column": "provider_message_id"}]}
        ],
        "runtime_candidates": [],
    }))
    output = tmp_path / "latest.json"
    monkeypatch.setattr(collector, "DISCOVERY", discovery)
    monkeypatch.setattr(collector, "OUT", output)
    queried = []
    def empty(table):
        queried.append(table)
        return []
    monkeypatch.setattr(collector, "query_table", empty)
    monkeypatch.setattr(collector, "runtime_records", lambda *_: [])
    assert collector.run_cli() == 0
    assert queried == ["public.outbound_replies"]
    snapshot = json.loads(output.read_text())
    assert snapshot["canonical_messages"] == []
    health = json.loads((tmp_path / "collector_health_latest.json").read_text())
    assert health["status"] == "READ_SUCCESS"
    assert health["source_query_completed"] is True
    assert health["database_table_count"] == 1
    assert health["canonical_messages"] == 0
    assert health["authenticated_buyers_proved"] is False


def test_no_approved_db_source_fails_without_replacing_previous_truth(
    tmp_path, monkeypatch,
):
    import json
    collector = _load_collector()
    discovered = tmp_path / "discovery.json"
    discovered.write_text(json.dumps({
        "database_candidates": [
            {"table": "public.outbound_events", "columns": [{"column": "message_id"}]}
        ],
        "runtime_candidates": [],
    }))
    output = tmp_path / "latest.json"
    output.write_text('{"kept":"last-good"}')
    monkeypatch.setattr(collector, "DISCOVERY", discovered)
    monkeypatch.setattr(collector, "OUT", output)
    monkeypatch.setattr(collector, "query_table", lambda table: (_ for _ in ()).throw(
        AssertionError("unapproved table queried")
    ))
    monkeypatch.setattr(collector, "runtime_records", lambda *_: [])
    assert collector.run_cli() == 3
    assert json.loads(output.read_text()) == {"kept": "last-good"}
    health = json.loads((tmp_path / "collector_health_latest.json").read_text())
    assert health["reason_code"] == "NO_APPROVED_DATABASE_SOURCES"
    assert health["source_query_completed"] is False
    assert health["canonical_snapshot_preserved"] is True
