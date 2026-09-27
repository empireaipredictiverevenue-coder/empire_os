import pytest

from empire_os.revenue_os_registry_transport import (
    PACKETS_SQL,
    PACKET_SQL,
    READER_ROLE,
    PostgresRevenueOsRegistryReader,
    RevenueOsRegistryTransportError,
    RpcRevenueOsRegistryRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self, rows):
        self.calls = []
        self.rows = rows
        self.description = [
            Description("id"),
            Description("packet_key"),
            Description("execution_authority"),
            Description("spend_execution"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def reader_with(rows):
    cursor = Cursor(rows)
    reader = PostgresRevenueOsRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    return reader, cursor


def test_board_reader_uses_dedicated_role_and_static_query():
    reader, cursor = reader_with([
        ("packet-1", "packet-key-1", "none", False),
    ])
    rows = reader.packets(limit=25)
    assert rows[0]["packet_key"] == "packet-key-1"
    assert rows[0]["execution_authority"] == "none"
    assert rows[0]["spend_execution"] is False
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (PACKETS_SQL, (25,))


def test_board_reader_bounds_limit_to_200():
    reader, cursor = reader_with([])
    reader.packets(limit=9999)
    assert cursor.calls[1] == (PACKETS_SQL, (200,))


def test_single_packet_uses_parameterized_query():
    reader, cursor = reader_with([
        ("packet-1", "packet-key-1", "none", False),
    ])
    row = reader.packet("packet-key-1")
    assert row["packet_key"] == "packet-key-1"
    assert cursor.calls[1] == (PACKET_SQL, ("packet-key-1",))


def test_single_packet_missing_returns_none():
    reader, _ = reader_with([])
    assert reader.packet("packet-key-1") is None


def test_empty_packet_key_fails_before_connect():
    reader = PostgresRevenueOsRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        RevenueOsRegistryTransportError,
        match="packet_key required",
    ):
        reader.packet("")


def test_repository_reads_do_not_invoke_writer():
    def writer(name, params):
        raise AssertionError("writer must not run during reads")

    class Reader:
        def packets(self, *, limit):
            return [{"packet_key": "p1"}]

        def packet(self, packet_key):
            return {"packet_key": packet_key}

    repo = RpcRevenueOsRegistryRepository(
        writer,
        reader=Reader(),
    )
    assert repo.packets(limit=5) == [{"packet_key": "p1"}]
    assert repo.packet("p1") == {"packet_key": "p1"}


def test_repository_without_reader_fails_closed():
    repo = RpcRevenueOsRegistryRepository(lambda *args: {})
    with pytest.raises(
        RevenueOsRegistryTransportError,
        match="reader not activated",
    ):
        repo.packets(limit=5)


def test_reader_requires_dsn():
    with pytest.raises(
        RevenueOsRegistryTransportError,
        match="read DSN required",
    ):
        PostgresRevenueOsRegistryReader("")


def test_reader_wraps_database_failure():
    reader = PostgresRevenueOsRegistryReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        RevenueOsRegistryTransportError,
        match="read failed",
    ):
        reader.packets(limit=10)
