from types import SimpleNamespace
from uuid import uuid4

import pytest

from empire_os.lead_intelligence_transport import (
    LeadIntelligenceTransportError,
    PostgresLeadIntelligenceReader,
    ROLE,
)


class FakeCursor:
    def __init__(self, rows=None, fail_on_execute=None):
        self.rows = list(rows or [])
        self.fail_on_execute = fail_on_execute
        self.calls = []
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self.fail_on_execute:
            raise RuntimeError(self.fail_on_execute)
        if not sql.startswith("SET LOCAL ROLE"):
            self.description = [
                SimpleNamespace(name="id"),
                SimpleNamespace(name="business_name"),
            ]

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class FakeConnect:
    def __init__(self, cursor):
        self.cursor = cursor
        self.dsns = []

    def __call__(self, dsn):
        self.dsns.append(dsn)
        return FakeConnection(self.cursor)


def test_from_env_requires_dedicated_dsn(monkeypatch):
    monkeypatch.delenv(
        "EMPIRE_LEAD_INTELLIGENCE_DSN",
        raising=False,
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="EMPIRE_LEAD_INTELLIGENCE_DSN is required",
    ):
        PostgresLeadIntelligenceReader.from_env()


def test_reader_sets_dedicated_role_before_select():
    prospect_id = str(uuid4())
    cursor = FakeCursor(rows=[
        (prospect_id, "Acme Ltd"),
    ])
    connect = FakeConnect(cursor)
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=connect,
    )

    rows = reader(
        "/rest/v1/prospects",
        {
            "select": "id,business_name",
            "id": f"eq.{prospect_id}",
            "limit": "1",
        },
    )

    assert rows == [{
        "id": prospect_id,
        "business_name": "Acme Ltd",
    }]
    assert connect.dsns == ["postgresql://reader@example/db"]
    assert cursor.calls[0] == (
        f"SET LOCAL ROLE {ROLE}",
        None,
    )
    select_sql, values = cursor.calls[1]
    assert select_sql.startswith(
        "SELECT id,business_name FROM public.prospects"
    )
    assert values == (prospect_id, 1)


def test_unsupported_path_rejected_before_connect():
    cursor = FakeCursor()
    connect = FakeConnect(cursor)
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=connect,
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="unsupported Lead Intelligence read path",
    ):
        reader(
            "/rest/v1/secret_admin_table",
            {"select": "id"},
        )

    assert connect.dsns == []


def test_unsafe_select_column_rejected_before_connect():
    prospect_id = str(uuid4())
    cursor = FakeCursor()
    connect = FakeConnect(cursor)
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=connect,
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="unsafe Lead Intelligence select list",
    ):
        reader(
            "/rest/v1/prospects",
            {
                "select": "id,password_hash",
                "id": f"eq.{prospect_id}",
                "limit": "1",
            },
        )

    assert connect.dsns == []


def test_unexpected_query_parameter_rejected():
    prospect_id = str(uuid4())
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=FakeConnect(FakeCursor()),
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="unexpected Lead Intelligence query parameters",
    ):
        reader(
            "/rest/v1/prospects",
            {
                "select": "id",
                "id": f"eq.{prospect_id}",
                "limit": "1",
                "danger": "true",
            },
        )


def test_identity_query_requires_active_true():
    prospect_id = str(uuid4())
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=FakeConnect(FakeCursor()),
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="active=true",
    ):
        reader(
            "/rest/v1/prospect_entity_links",
            {
                "select": "prospect_id,entity_id",
                "prospect_id": f"eq.{prospect_id}",
                "active": "eq.false",
                "limit": "2",
            },
        )


def test_database_error_is_sanitized():
    prospect_id = str(uuid4())
    cursor = FakeCursor(
        fail_on_execute="database password is secret",
    )
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=FakeConnect(cursor),
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="dedicated Lead Intelligence database read failed",
    ) as raised:
        reader(
            "/rest/v1/prospects",
            {
                "select": "id",
                "id": f"eq.{prospect_id}",
                "limit": "1",
            },
        )

    message = str(raised.value)
    assert "database password" not in message


def test_entity_intelligence_order_is_fixed():
    entity_id = str(uuid4())
    reader = PostgresLeadIntelligenceReader(
        "postgresql://reader@example/db",
        connect_factory=FakeConnect(FakeCursor()),
    )

    with pytest.raises(
        LeadIntelligenceTransportError,
        match="unexpected entity intelligence ordering",
    ):
        reader(
            "/rest/v1/intelligence_signals",
            {
                "select": "id,entity_id",
                "entity_id": f"eq.{entity_id}",
                "order": "created_at.asc",
                "limit": "10",
            },
        )
