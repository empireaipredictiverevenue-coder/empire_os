import json
from copy import deepcopy
from uuid import uuid4

import pytest

from empire_os.intelligence_materializer_transport import (
    ECONOMIC_SIGNAL_SOURCE_KEYS,
    IntelligenceMaterializerTransportError,
    PostgresIntelligenceMaterializer,
    persist_economic_signal,
)

ENTITY_ID = str(uuid4())
SOURCE_ID = str(uuid4())
ROW_ID = str(uuid4())


def signal(**changes):
    base = {
        "schema_version": "empire.economic-signal.v1",
        "signal_id": "economic_signal_" + "a" * 64,
        "tenant_id": "tenant-alpha",
        "tenant_binding_ref": "canonical:tenant-binding:alpha:entity",
        "entity_id": ENTITY_ID, "source_id": SOURCE_ID,
        "signal_type": "market_gap", "signal_domain": "economic_opportunity",
        "observed_at": "2026-10-08T09:00:00+00:00",
        "strength": 0.8, "confidence": 0.9,
        "evidence_refs": ["canonical:evidence:1"],
        "payload": {"market": "roofing:denver"},
        "truth_class": "OBSERVED", "data_backend": "empiredb",
        "execution_authority": "none", "outreach_authority": "none",
        "calls_authority": "none", "traffic_authority": "none",
        "commercial_authority": "none", "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }
    base.update(changes)
    return base


class DatabaseError(Exception):
    def __init__(self, message, sqlstate="P0001"):
        super().__init__(message)
        self.sqlstate = sqlstate


class Cursor:
    def __init__(self, *, source_id=SOURCE_ID, row=(ROW_ID,), error=None):
        self.source_id = source_id
        self.row = row
        self.error = error
        self.executed = []
        self._rows = []

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        self.executed.append((sql, deepcopy(params)))
        if sql.startswith("SET TRANSACTION") or sql.startswith("SET LOCAL ROLE"):
            self._rows = []
        elif "FROM public.intelligence_sources" in sql:
            self._rows = [] if self.source_id is None else [(self.source_id,)]
        elif sql.startswith("SELECT public.empire_write_economic_signal("):
            if self.error is not None:
                raise self.error
            self._rows = [] if self.row is None else [self.row]
        else:
            raise AssertionError("Unexpected SQL: " + sql)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Connection:
    def __init__(self, cursor, *, commit_error=None, autocommit=False):
        self._cursor = cursor
        self.commit_error = commit_error
        self.autocommit = autocommit
        self.committed = False
        self.failed = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        if exc_type is not None:
            self.failed = True
        elif self.commit_error is not None:
            self.failed = True
            raise self.commit_error
        else:
            self.committed = True
        return False


def writer_for(*connections):
    calls = []
    def connect(dsn):
        if len(calls) >= len(connections):
            raise AssertionError("Unexpected reconnect")
        conn = connections[len(calls)]
        calls.append(conn)
        return conn
    result = PostgresIntelligenceMaterializer(
        "postgresql://materializer@example/db", connect_factory=connect,
    )
    return result, calls


def writer(cursor):
    return writer_for(Connection(cursor))[0]


def test_governed_call_uses_exact_nine_arguments_and_original_payload():
    cursor = Cursor()
    connection = Connection(cursor)
    transport, calls = writer_for(connection)
    candidate = signal(expires_at="2026-10-08T10:00:00+00:00")
    before = deepcopy(candidate)
    result = persist_economic_signal(transport, candidate)
    assert connection.committed and connection.closed
    assert len(calls) == 1
    assert cursor.executed[0] == ("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE", None)
    assert cursor.executed[1] == ("SET LOCAL ROLE empire_intelligence_materializer", None)
    sql, params = cursor.executed[-1]
    assert sql.startswith("SELECT public.empire_write_economic_signal(")
    assert sql.count("%s") == 9
    assert params[:-1] == (
        ENTITY_ID, "market_gap", "economic_opportunity", candidate["observed_at"],
        candidate["expires_at"], 0.8, 0.9, ["canonical:evidence:1"],
    )
    assert json.loads(params[-1]) == before["payload"]
    assert candidate == before
    assert result["id"] == ROW_ID
    assert result["input_signal_id"] == before["signal_id"]
    assert "signal_id" not in result  # Do not mislabel Fabric identity as persisted identity.
    assert result["persisted"] is True
    assert result["inserted"] is None and result["existing"] is None
    assert result["execution_authority"] == "none"
    assert not any("public.intelligence_signals" in statement for statement, _ in cursor.executed)


def test_replay_returns_same_database_uuid_without_fabric_deduplication():
    cursors = [Cursor(), Cursor()]
    transport, calls = writer_for(*(Connection(c) for c in cursors))
    first = persist_economic_signal(transport, signal())
    second = persist_economic_signal(transport, signal(signal_id="economic_signal_" + "b" * 64))
    assert first["id"] == second["id"] == ROW_ID
    assert len(calls) == 2
    assert all("empire_write_economic_signal" in c.executed[-1][0] for c in cursors)


def test_caller_tenant_labels_do_not_become_writer_arguments():
    cursor = Cursor()
    persist_economic_signal(writer(cursor), signal(tenant_id="untrusted-tenant", tenant_binding_ref="untrusted-binding"))
    params = cursor.executed[-1][1]
    assert "untrusted-tenant" not in repr(params)
    assert "untrusted-binding" not in repr(params)


@pytest.mark.parametrize("stage", ["execute", "commit"])
def test_serialization_retry_uses_fresh_connection_and_same_parameters(stage):
    error = DatabaseError("economic_writer_retry_required", "40001")
    first = Connection(Cursor(error=error if stage == "execute" else None), commit_error=error if stage == "commit" else None)
    second = Connection(Cursor())
    transport, calls = writer_for(first, second)
    result = persist_economic_signal(transport, signal())
    assert result["id"] == ROW_ID
    assert first.failed and first.closed and second.committed
    assert len(calls) == 2
    assert first._cursor.executed == second._cursor.executed


def test_serialization_retry_is_bounded():
    connections = [Connection(Cursor(error=DatabaseError("retry", "40001"))) for _ in range(3)]
    transport, calls = writer_for(*connections)
    with pytest.raises(IntelligenceMaterializerTransportError, match="retries exhausted") as caught:
        persist_economic_signal(transport, signal())
    assert caught.value.__cause__.sqlstate == "40001"
    assert len(calls) == 3
    assert all(c.failed and c.closed for c in connections)


@pytest.mark.parametrize("message,code", [
    ("economic_observation_conflict", "P0001"),
    ("authenticated_active_tenant_required", "P0001"),
    ("active_tenant_entity_binding_required", "P0001"),
    ("permission denied", "42501"),
    ("undefined function", "42883"),
    ("connection lost", "08006"),
])
def test_database_denials_never_fall_back_or_retry(message, code):
    error = DatabaseError(message, code)
    connection = Connection(Cursor(error=error))
    transport, calls = writer_for(connection)
    with pytest.raises(IntelligenceMaterializerTransportError) as caught:
        persist_economic_signal(transport, signal(strength=0.7))
    assert caught.value.__cause__ is error
    assert len(calls) == 1 and connection.failed


def test_commit_failure_cannot_report_success():
    error = DatabaseError("connection lost", "08006")
    conn = Connection(Cursor(), commit_error=error)
    transport, calls = writer_for(conn)
    with pytest.raises(IntelligenceMaterializerTransportError):
        persist_economic_signal(transport, signal())
    assert not conn.committed and len(calls) == 1


@pytest.mark.parametrize("row", [None, (None,), ("not-a-uuid",), (ROW_ID, "unexpected")])
def test_invalid_writer_result_rolls_back(row):
    conn = Connection(Cursor(row=row))
    with pytest.raises(IntelligenceMaterializerTransportError):
        persist_economic_signal(writer_for(conn)[0], signal())
    assert conn.failed and not conn.committed


def test_autocommit_connection_rejected_before_sql():
    cursor = Cursor()
    conn = Connection(cursor, autocommit=True)
    with pytest.raises(IntelligenceMaterializerTransportError, match="transactional"):
        persist_economic_signal(writer_for(conn)[0], signal())
    assert cursor.executed == []


@pytest.mark.parametrize("changes", [
    {"payload": {"_economic_signal": {"tenant_id": "forged"}}},
    {"payload": {"score": float("nan")}},
    {"payload": {"object": object()}},
    {"signal_domain": " "},
    {"evidence_refs": [None]},
    {"evidence_refs": [123]},
    {"evidence_refs": [" "]},
    {"evidence_refs": ["x", "x"]},
    {"tenant_binding_ref": ""},
])
def test_invalid_input_is_rejected_before_connect(changes):
    transport, calls = writer_for()
    with pytest.raises(IntelligenceMaterializerTransportError):
        persist_economic_signal(transport, signal(**changes))
    assert calls == []


def test_missing_source_rejected_without_writer_call():
    cursor = Cursor(source_id=None)
    with pytest.raises(IntelligenceMaterializerTransportError, match="source is missing"):
        persist_economic_signal(writer(cursor), signal())
    assert not any("empire_write_economic_signal" in sql for sql, _ in cursor.executed)


def test_supported_source_keys_are_fixed():
    assert ECONOMIC_SIGNAL_SOURCE_KEYS == {
        "revenue_leak": "empire.revenue_leak.observed.v1",
        "idle_asset": "empire.idle_asset.observed.v1",
        "market_gap": "empire.market_gap.observed.v1",
        "idle_waste": "empire.idle_waste.observed.v1",
    }


def test_source_mismatch_fails_closed():
    cursor = Cursor(source_id=str(uuid4()))

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="source mismatch",
    ):
        persist_economic_signal(writer(cursor), signal())


@pytest.mark.parametrize(
    "field",
    [
        "execution_authority",
        "outreach_authority",
        "calls_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ],
)
def test_any_authority_expansion_rejected(field):
    candidate = signal()
    candidate[field] = "allowed"

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="economic signal has",
    ):
        persist_economic_signal(
            writer(Cursor()),
            candidate,
        )


def test_missing_tenant_binding_rejected_before_connect():
    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="verified tenant binding required",
    ):
        persist_economic_signal(
            writer(Cursor()),
            signal(tenant_binding_ref=""),
        )


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_strength_fails_closed(value):
    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="strength",
    ):
        persist_economic_signal(
            writer(Cursor()),
            signal(strength=value),
        )


def test_wrong_schema_rejected():
    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="schema",
    ):
        persist_economic_signal(
            writer(Cursor()),
            signal(schema_version="legacy.v1"),
        )


def test_wrong_truth_class_rejected():
    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="observed evidence",
    ):
        persist_economic_signal(
            writer(Cursor()),
            signal(truth_class="PREDICTED"),
        )


def test_unknown_signal_type_rejected():
    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="unsupported economic signal type",
    ):
        persist_economic_signal(
            writer(Cursor()),
            signal(signal_type="magic_money"),
        )
