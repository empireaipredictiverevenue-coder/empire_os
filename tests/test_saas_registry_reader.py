import pytest

from empire_os.saas_registry_transport import (
    READ_SQL,
    READER_ROLE,
    PostgresSaasRegistryReader,
    RpcSaasRegistryRepository,
    SaasRegistryTransportError,
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
            Description("tenant_id"),
            Description("execution_authority"),
            Description("billing_execution"),
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
            "tenant-1-v1",
            "tenant-1",
            "none",
            False,
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
    reader = PostgresSaasRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["tenant_id"] == "tenant-1"
    assert rows[0]["execution_authority"] == "none"
    assert rows[0]["billing_execution"] is False
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_reader_bounds_limit_to_500():
    cursor = Cursor()
    reader = PostgresSaasRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_list_does_not_invoke_writer():
    def writer(name, params):
        raise AssertionError("writer must not run during readiness list")

    repo = RpcSaasRegistryRepository(
        writer,
        reader=lambda *, limit: [{"readiness_key": "r1"}],
    )
    assert repo.list_readiness(limit=10) == [{"readiness_key": "r1"}]


def test_repository_without_reader_fails_closed():
    repo = RpcSaasRegistryRepository(lambda *args: {})
    with pytest.raises(
        SaasRegistryTransportError,
        match="reader not activated",
    ):
        repo.list_readiness(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        SaasRegistryTransportError,
        match="read DSN required",
    ):
        PostgresSaasRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresSaasRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        SaasRegistryTransportError,
        match="read failed",
    ):
        reader(limit=10)
