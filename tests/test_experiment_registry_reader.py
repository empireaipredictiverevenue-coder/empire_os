import pytest

from empire_os.experiment_registry_transport import (
    READ_SQL,
    READER_ROLE,
    ExperimentRegistryTransportError,
    PostgresExperimentRegistryReader,
    RpcExperimentRegistryRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("id"),
            Description("experiment_key"),
            Description("execution_authority"),
            Description("traffic_mutation"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [("r1", "exp-1", "none", False)]


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
    reader = PostgresExperimentRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["experiment_key"] == "exp-1"
    assert rows[0]["execution_authority"] == "none"
    assert rows[0]["traffic_mutation"] is False
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_reader_bounds_limit_to_500():
    cursor = Cursor()
    reader = PostgresExperimentRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_list_does_not_invoke_writer():
    def writer(name, params):
        raise AssertionError("writer must not run during list")

    repo = RpcExperimentRegistryRepository(
        writer,
        reader=lambda *, limit: [{"experiment_key": "exp-1"}],
    )
    assert repo.list_experiments(limit=10) == [
        {"experiment_key": "exp-1"}
    ]


def test_repository_without_reader_fails_closed():
    repo = RpcExperimentRegistryRepository(lambda *args: {})
    with pytest.raises(
        ExperimentRegistryTransportError,
        match="reader not activated",
    ):
        repo.list_experiments(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        ExperimentRegistryTransportError,
        match="read DSN required",
    ):
        PostgresExperimentRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresExperimentRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        ExperimentRegistryTransportError,
        match="read failed",
    ):
        reader(limit=10)
