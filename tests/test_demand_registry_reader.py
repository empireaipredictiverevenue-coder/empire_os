import pytest

from empire_os.demand_registry_transport import (
    READ_SQL,
    READER_ROLE,
    DemandRegistryTransportError,
    PostgresDemandRegistryReader,
    RpcDemandRegistryRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("id"),
            Description("plan_id"),
            Description("execution_authority"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [("registry-1", "plan-1", "none")]


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def test_reader_uses_dedicated_role_and_static_query():
    cursor = Cursor()
    reader = PostgresDemandRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=25)
    assert rows == [{
        "id": "registry-1",
        "plan_id": "plan-1",
        "execution_authority": "none",
    }]
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (25,))


def test_reader_bounds_limit_to_500():
    cursor = Cursor()
    reader = PostgresDemandRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_lists_through_reader_only():
    calls = []

    def writer(name, params):
        raise AssertionError("writer must not run for list")

    def reader(*, limit):
        calls.append(limit)
        return [{"plan_id": "plan-1"}]

    repo = RpcDemandRegistryRepository(writer, reader=reader)
    assert repo.list_plans(limit=10) == [{"plan_id": "plan-1"}]
    assert calls == [10]


def test_repository_without_reader_fails_closed():
    repo = RpcDemandRegistryRepository(lambda *args: {})
    with pytest.raises(
        DemandRegistryTransportError,
        match="reader not activated",
    ):
        repo.list_plans(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        DemandRegistryTransportError,
        match="read DSN required",
    ):
        PostgresDemandRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresDemandRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        DemandRegistryTransportError,
        match="read failed",
    ):
        reader(limit=10)
