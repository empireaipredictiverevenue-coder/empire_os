import pytest

from empire_os.revenue_crm_transport import (
    BUYER_LIST_SQL,
    PROSPECT_LIST_SQL,
    PROSPECT_ONE_SQL,
    ROLE,
    PostgresRevenueCrmRepository,
    RevenueCrmTransportError,
)


class Description:
    def __init__(self, name):
        self.name = name


class FakeCursor:
    def __init__(self, rows, columns):
        self.rows = rows
        self.description = [Description(name) for name in columns]
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def repository(rows, columns):
    cursor = FakeCursor(rows, columns)
    repo = PostgresRevenueCrmRepository(
        "postgresql://example",
        connect_factory=lambda dsn: FakeConnection(cursor),
    )
    return repo, cursor


def test_prospect_list_uses_dedicated_role_and_static_view():
    repo, cursor = repository(
        [("00000000-0000-0000-0000-000000000001", "Acme")],
        ["prospect_id", "business_name"],
    )
    rows = repo.prospects(limit=10)
    assert rows[0]["business_name"] == "Acme"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + ROLE, None)
    assert cursor.calls[1] == (PROSPECT_LIST_SQL, (10,))
    assert "revenue_crm_prospects" in PROSPECT_LIST_SQL


def test_buyer_list_is_bounded_and_read_only():
    repo, cursor = repository(
        [("00000000-0000-0000-0000-000000000002", 4)],
        ["buyer_id", "available_capacity"],
    )
    rows = repo.buyers(limit=25)
    assert rows[0]["available_capacity"] == 4
    assert cursor.calls[1] == (BUYER_LIST_SQL, (25,))
    assert "revenue_crm_buyers" in BUYER_LIST_SQL


def test_single_prospect_requires_canonical_uuid():
    repo, _ = repository([], ["prospect_id"])
    with pytest.raises(
        RevenueCrmTransportError,
        match="canonical prospect_id UUID",
    ):
        repo.prospect("legacy-id")


def test_single_prospect_returns_none_when_missing():
    repo, cursor = repository([], ["prospect_id"])
    prospect_id = "00000000-0000-0000-0000-000000000003"
    assert repo.prospect(prospect_id) is None
    assert cursor.calls[1] == (PROSPECT_ONE_SQL, (prospect_id,))


def test_limit_out_of_range_fails_before_connect():
    def must_not_connect(dsn):
        raise AssertionError("must not connect")

    repo = PostgresRevenueCrmRepository(
        "postgresql://example",
        connect_factory=must_not_connect,
    )
    with pytest.raises(
        RevenueCrmTransportError,
        match="limit out of range",
    ):
        repo.prospects(limit=501)


def test_missing_dsn_fails_closed():
    with pytest.raises(
        RevenueCrmTransportError,
        match="DSN required",
    ):
        PostgresRevenueCrmRepository("")


def test_database_failure_is_wrapped():
    def broken(dsn):
        raise RuntimeError("db unavailable")

    repo = PostgresRevenueCrmRepository(
        "postgresql://example",
        connect_factory=broken,
    )
    with pytest.raises(
        RevenueCrmTransportError,
        match="database read failed",
    ):
        repo.buyers(limit=10)
