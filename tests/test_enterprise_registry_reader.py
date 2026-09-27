import pytest

from empire_os.enterprise_registry_transport import (
    READ_SQL,
    READER_ROLE,
    EnterpriseRegistryTransportError,
    PostgresEnterpriseRegistryReader,
    RpcEnterpriseRegistryRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("id"),
            Description("readiness_key"),
            Description("control_passes"),
            Description("slo_passes"),
            Description("execution_authority"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [(
            "registry-1",
            "enterprise-v1",
            1,
            1,
            "none",
        )]


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
    reader = PostgresEnterpriseRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["readiness_key"] == "enterprise-v1"
    assert rows[0]["execution_authority"] == "none"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_reader_bounds_limit_to_500():
    cursor = Cursor()
    reader = PostgresEnterpriseRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_history_does_not_invoke_writer():
    def writer(name, params):
        raise AssertionError("writer must not run during history read")

    repo = RpcEnterpriseRegistryRepository(
        writer,
        reader=lambda *, limit: [{"readiness_key": "r1"}],
    )
    assert repo.list_readiness(limit=10) == [{"readiness_key": "r1"}]


def test_repository_without_reader_fails_closed():
    repo = RpcEnterpriseRegistryRepository(lambda *args: {})
    with pytest.raises(
        EnterpriseRegistryTransportError,
        match="reader not activated",
    ):
        repo.list_readiness(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        EnterpriseRegistryTransportError,
        match="read DSN required",
    ):
        PostgresEnterpriseRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresEnterpriseRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        EnterpriseRegistryTransportError,
        match="read failed",
    ):
        reader(limit=10)
