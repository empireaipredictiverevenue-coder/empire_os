import pytest

from empire_os.capital_registry_transport import (
    READ_SQL,
    READER_ROLE,
    CapitalRegistryTransportError,
    PostgresCapitalRegistryReader,
    RpcCapitalRegistryRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("id"),
            Description("review_key"),
            Description("candidate_id"),
            Description("execution_authority"),
            Description("funds_movement"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [(
            "review-1",
            "candidate-1-policy-v1",
            "candidate-1",
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
    reader = PostgresCapitalRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["review_key"] == "candidate-1-policy-v1"
    assert rows[0]["execution_authority"] == "none"
    assert rows[0]["funds_movement"] is False
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_reader_bounds_limit_to_500():
    cursor = Cursor()
    reader = PostgresCapitalRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_lists_without_invoking_writer():
    def writer(name, params):
        raise AssertionError("writer must not run during review list")

    repo = RpcCapitalRegistryRepository(
        writer,
        reader=lambda *, limit: [{"review_key": "r1"}],
    )
    assert repo.list_reviews(limit=10) == [{"review_key": "r1"}]


def test_repository_without_reader_fails_closed():
    repo = RpcCapitalRegistryRepository(lambda *args: {})
    with pytest.raises(
        CapitalRegistryTransportError,
        match="reader not activated",
    ):
        repo.list_reviews(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        CapitalRegistryTransportError,
        match="read DSN required",
    ):
        PostgresCapitalRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresCapitalRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        CapitalRegistryTransportError,
        match="read failed",
    ):
        reader(limit=10)
