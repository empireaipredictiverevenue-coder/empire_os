import pytest

from empire_os.revenue_exchange_transport import (
    READ_SQL,
    READER_ROLE,
    RevenueExchangeTransportError,
    PostgresRevenueExchangeReader,
    RpcRevenueExchangeRepository,
)


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("niche"),
            Description("metro"),
            Description("qualified_inventory_count"),
            Description("active_buyer_capacity"),
            Description("verified_price_per_lead_cents"),
            Description("observed_at"),
            Description("source"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [(
            "roofing",
            "London",
            12,
            6,
            [7500, 10000],
            "2026-09-19T20:00:00+00:00",
            "canonical_exchange_projection",
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
    reader = PostgresRevenueExchangeReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=25)
    assert rows[0]["niche"] == "roofing"
    assert rows[0]["active_buyer_capacity"] == 6
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (25,))


def test_reader_bounds_limit():
    cursor = Cursor()
    reader = PostgresRevenueExchangeReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    reader(limit=9999)
    assert cursor.calls[1] == (READ_SQL, (500,))


def test_repository_market_read_never_calls_writer():
    def writer(name, params):
        raise AssertionError("writer must not be used for observations")

    repo = RpcRevenueExchangeRepository(
        writer,
        reader=lambda *, limit: [{
            "niche": "roofing",
            "metro": "London",
            "qualified_inventory_count": 1,
            "active_buyer_capacity": 1,
            "verified_price_per_lead_cents": [7500],
            "observed_at": "2026-09-19T20:00:00+00:00",
            "source": "canonical_exchange_projection",
        }],
    )
    rows = repo.observations(limit=10)
    assert rows[0]["metro"] == "London"


def test_reader_only_repository_cannot_append():
    repo = RpcRevenueExchangeRepository(
        reader=lambda *, limit: [],
    )
    with pytest.raises(
        RevenueExchangeTransportError,
        match="writer not activated",
    ):
        repo.append(None)


def test_repository_without_reader_fails_closed():
    repo = RpcRevenueExchangeRepository(lambda *args: {})
    with pytest.raises(
        RevenueExchangeTransportError,
        match="reader not activated",
    ):
        repo.observations(limit=10)


def test_reader_requires_dsn():
    with pytest.raises(
        RevenueExchangeTransportError,
        match="read DSN required",
    ):
        PostgresRevenueExchangeReader("")


def test_reader_wraps_database_failure():
    reader = PostgresRevenueExchangeReader(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    with pytest.raises(
        RevenueExchangeTransportError,
        match="read failed",
    ):
        reader(limit=10)
