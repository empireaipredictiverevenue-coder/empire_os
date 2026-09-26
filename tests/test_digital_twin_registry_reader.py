import pytest

from empire_os.digital_twin_registry_transport import (
    READ_SQL,
    READER_ROLE,
    DigitalTwinRegistryTransportError,
    PostgresDigitalTwinRegistryReader,
    RpcDigitalTwinRegistryRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("scenario_id"),
            Description("scenario_key"),
            Description("execution_authority"),
            Description("capital_execution"),
            Description("result_execution_authority"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [(
            "scenario-1",
            "roofing-london-v1",
            "none",
            False,
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
    reader = PostgresDigitalTwinRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["scenario_key"] == "roofing-london-v1"
    assert rows[0]["execution_authority"] == "none"
    assert rows[0]["capital_execution"] is False
    assert rows[0]["result_execution_authority"] == "none"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_reader_bounds_limit_to_500():
    cursor = Cursor()
    reader = PostgresDigitalTwinRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_list_does_not_invoke_writer():
    def writer(name, params):
        raise AssertionError("writer must not run during scenario list")

    repo = RpcDigitalTwinRegistryRepository(
        writer,
        reader=lambda *, limit: [{"scenario_key": "s1"}],
    )
    assert repo.list_scenarios(limit=10) == [{"scenario_key": "s1"}]


def test_repository_without_reader_fails_closed():
    repo = RpcDigitalTwinRegistryRepository(lambda *args: {})
    with pytest.raises(
        DigitalTwinRegistryTransportError,
        match="reader not activated",
    ):
        repo.list_scenarios(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        DigitalTwinRegistryTransportError,
        match="read DSN required",
    ):
        PostgresDigitalTwinRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresDigitalTwinRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        DigitalTwinRegistryTransportError,
        match="read failed",
    ):
        reader(limit=10)
