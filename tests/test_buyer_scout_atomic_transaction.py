"""Offline SQL transaction contracts; no network or production connections.

SQLite supplies actual commit/rollback storage for this test-only PostgreSQL
connection double. PostgreSQL isolation is asserted as emitted SQL, not claimed
as live PostgreSQL concurrency proof.
"""
from copy import deepcopy
import json
import re
import sqlite3

import pytest

from empire_os import sb
from empire_os.buyer_scout_canonical_person_bridge import materialize_buyer_scout_identity
from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.data_backends.empiredb import EmpireDbProvider
from test_buyer_scout_canonical_person_bridge import Store, PID, run
from test_data_cloud_empiredb_provider import Cursor

JSON_COLUMNS = {"evidence", "provenance", "fact_value", "metadata"}
BOOL_COLUMNS = {"active", "is_current", "enabled"}
STAGES = ["business_entities", "prospect_entity_links", "intelligence_sources",
          "intelligence_people", "intelligence_employment", "intelligence_contact_points",
          "intelligence_facts", "prospects"]


class SerializationFailure(RuntimeError):
    sqlstate = "40001"


class SQLStore:
    config_snapshot = {"dsn_configured": True}

    def __init__(self, seed=None):
        seed = seed or Store()
        schema = deepcopy(seed)
        assert run(schema)["ok"]
        self.db = sqlite3.connect(":memory:")
        self.sessions = []
        self.fail_stage = None
        self.commit_failure = None
        self.concurrent_projection = False
        self.columns = {}
        for table, rows in schema.tables.items():
            columns = sorted({key for row in rows for key in row})
            self.columns[table] = columns
            definitions = []
            for column in columns:
                if column == "id":
                    definitions.append('"id" TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))')
                else:
                    kind = "INTEGER" if column in BOOL_COLUMNS else ""
                    definitions.append(f'"{column}" {kind}')
            conflict = {"prospect_entity_links": "prospect_id", "intelligence_sources": "source_key"}.get(table)
            if conflict:
                definitions.append(f'UNIQUE ("{conflict}")')
            self.db.execute(f'CREATE TABLE "{table}" ({", ".join(definitions)})')
            if table == "intelligence_facts":
                self.db.execute('CREATE UNIQUE INDEX uq_intelligence_facts_evidence_hash '
                                'ON intelligence_facts(evidence_hash) WHERE evidence_hash IS NOT NULL')
            for row in seed.tables[table]:
                names = ','.join(f'"{key}"' for key in row)
                placeholders = ','.join('?' for _ in row)
                self.db.execute(f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})',
                                tuple(self.adapt_value(value) for value in row.values()))
        self.db.commit()

    def adapt_value(self, value):
        return json.dumps(value, sort_keys=True) if isinstance(value, dict) else value

    def _open_connection(self):
        connection = Session(self)
        self.sessions.append(connection)
        return connection

    def snapshot(self):
        return {table: self.db.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
                for table in self.columns}

    def execute(self):
        return materialize_buyer_scout_identity(prospect_id=PID, write_authorized=True)


class Session:
    def __init__(self, store):
        self.store = store
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if sql.startswith("SET LOCAL"):
            return Cursor()
        if sql.startswith("SET TRANSACTION"):
            self.store.db.execute("BEGIN")
            return Cursor()
        if self.store.concurrent_projection and sql.startswith('UPDATE public."prospects"'):
            raise SerializationFailure("concurrent stronger projection")
        translated = sql.replace("public.", "").replace("%s", "?").replace(" ILIKE ", " LIKE ")
        cursor = self.store.db.execute(translated, params)
        names = [column[0] for column in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        def decode(name, value):
            if value is None:
                return None
            if name in JSON_COLUMNS:
                return json.loads(value)
            return bool(value) if name in BOOL_COLUMNS else value
        result = Cursor([tuple(decode(name, value) for name, value in zip(names, row)) for row in rows], names)
        if sql.startswith(("INSERT", "UPDATE")):
            table = re.search(r'public\."([a-z_]+)"', sql).group(1)
            if self.store.fail_stage == table:
                raise RuntimeError("injected after SQL write; private details")
        return result

    def commit(self):
        self.commits += 1
        if self.store.commit_failure == "serialization":
            raise SerializationFailure("retry")
        if self.store.commit_failure == "before":
            raise ConnectionError("private connection string")
        self.store.db.commit()
        if self.store.commit_failure == "after":
            raise ConnectionError("private connection string")

    def rollback(self):
        self.rollbacks += 1
        self.store.db.rollback()

    def close(self):
        self.closed = True


@pytest.fixture
def database(monkeypatch):
    store = SQLStore()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: CanonicalDataGateway(EmpireDbProvider(store)))
    yield store
    store.db.close()


@pytest.mark.parametrize("stage", STAGES)
def test_provider_rollback_after_every_write(database, stage):
    before = database.snapshot()
    database.fail_stage = stage
    result = database.execute()
    assert result["ok"] is False
    assert result["failure_stage"] == stage
    assert result["transaction_state"] == "rolled_back"
    assert result["internal_mutation_performed"] is False
    assert not result["write_outcome_unknown"]
    assert database.snapshot() == before
    assert len(database.sessions) == 1
    session = database.sessions[0]
    assert session.commits == 0
    assert session.rollbacks == 2  # read-only connector setup + materialization
    assert session.closed
    assert "private details" not in str(result)


def test_complete_unit_one_connection_one_commit_and_idempotent(database):
    result = database.execute()
    assert result["ok"], result
    assert result["transaction_state"] == "committed"
    assert result["projection_performed"]
    assert len(database.sessions) == 1
    session = database.sessions[0]
    assert session.commits == 1 and session.closed
    assert session.calls[0][0] == "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"
    fact_inserts = [sql for sql, _ in session.calls
                    if sql.startswith('INSERT INTO public."intelligence_facts"')]
    assert len(fact_inserts) == 1
    assert "ON CONFLICT DO NOTHING RETURNING" in fact_inserts[0]
    before = database.snapshot()
    assert database.execute()["ok"]
    assert database.snapshot() == before
    assert len(database.sessions) == 2
    assert database.sessions[1].commits == 1
    assert database.db.execute('SELECT contacted_status FROM prospects').fetchone() == ('not_contacted',)
    assert not any(result[key] for key in ("outbound_actions", "payment_actions", "revenue_actions"))
    assert all(not re.search(r'outbound|payment|revenue|rpc', sql) for sql, _ in session.calls)


@pytest.mark.parametrize("when", ["before", "after", "serialization"])
def test_commit_failure_retry_converges_from_canonical_state(database, when):
    before = database.snapshot()
    database.commit_failure = when
    result = database.execute()
    assert not result["ok"] and result["retryable"]
    assert result["failure_stage"] == "commit"
    assert result["write_outcome_unknown"] == (when != "serialization")
    assert "private connection" not in str(result)
    if when != "after":
        assert database.snapshot() == before
    else:
        assert database.snapshot() != before
    database.commit_failure = None
    assert database.execute()["ok"]
    complete = database.snapshot()
    assert database.execute()["ok"]
    assert database.snapshot() == complete
    assert len(complete["intelligence_people"]) == 1
    assert len(complete["intelligence_facts"]) == 1


def test_serialization_conflict_preserves_stronger_projection_on_retry(database):
    before = database.snapshot()
    database.concurrent_projection = True
    result = database.execute()
    assert not result["ok"] and result["retryable"]
    assert not result["write_outcome_unknown"]
    assert result["blocker"] == "CANONICAL_TRANSACTION_RETRY_REQUIRED"
    assert database.snapshot() == before
    # A separate writer commits its stronger projection after our abort.
    database.concurrent_projection = False
    database.db.execute("UPDATE prospects SET contact_name='Existing Person', contact_title='CEO'")
    database.db.commit()
    result = database.execute()
    assert result["ok"] and result["projection_status"] == "EXISTING_PROJECTION_PRESERVED"
    assert not result["review_input"]["review_ready"]
    assert database.db.execute("SELECT contact_name FROM prospects").fetchone() == ("Existing Person",)


def test_real_boundary_recovers_operator_shaped_partial_state(database):
    assert database.execute()["ok"]
    database.db.execute("DELETE FROM intelligence_facts")
    database.db.execute("UPDATE prospects SET contact_name=NULL, contact_title=NULL, contact_source='buyer_scout_review_ready'")
    database.db.commit()
    before = database.snapshot()
    assert database.execute()["ok"]
    after = database.snapshot()
    for table in STAGES:
        if table not in {"prospects", "intelligence_facts"}:
            assert before[table] == after[table]
    assert len(after["intelligence_facts"]) == 1


def test_final_readback_failure_rolls_back(database, monkeypatch):
    original = Session.execute
    reads = 0
    def fail_final(self, sql, params=()):
        nonlocal reads
        result = original(self, sql, params)
        if sql.startswith('SELECT') and 'FROM public."prospects"' in sql:
            reads += 1
            if reads == 2:
                raise RuntimeError("final readback failed")
        return result
    monkeypatch.setattr(Session, "execute", fail_final)
    before = database.snapshot()
    result = database.execute()
    assert not result["ok"] and result["transaction_state"] == "rolled_back"
    assert database.snapshot() == before
