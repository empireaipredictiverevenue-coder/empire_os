import pytest

from empire_os.canonical_data_gateway import DataGatewayOperationUnsupported
from empire_os.data_backends.empiredb import EmpireDbProvider


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self, rows=(), columns=()):
        self._rows = list(rows)
        self.description = [Description(name) for name in columns] if columns else None

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.next_cursor = Cursor()

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self.next_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakeConnector:
    config_snapshot = {"dsn_configured": True}

    def __init__(self, connection):
        self.connection = connection

    def _open_connection(self):
        return self.connection


def test_select_is_parameterized_and_identifier_bounded():
    connection = FakeConnection()
    connection.next_cursor = Cursor([("1", "new")], ("id", "status"))
    provider = EmpireDbProvider(FakeConnector(connection))

    rows = provider.select(
        "prospects",
        "id,status",
        {"status": "new"},
        "id.desc",
        10,
        0,
    )

    assert rows == [{"id": "1", "status": "new"}]
    sql, params = connection.calls[0]
    assert 'FROM public."prospects"' in sql
    assert '"status" = %s' in sql
    assert 'ORDER BY "id" DESC' in sql
    assert params == ("new", 10, 0)
    assert connection.closed is True


def test_unsafe_table_or_column_is_rejected():
    provider = EmpireDbProvider(FakeConnector(FakeConnection()))
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        provider.select("prospects;drop", "id")
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        provider.select("prospects", "id,(select secret)")


def test_insert_commits_and_returns_rows():
    connection = FakeConnection()
    connection.next_cursor = Cursor([("1",)], ("id",))
    provider = EmpireDbProvider(FakeConnector(connection))

    rows = provider.insert("prospects", {"id": "1"})

    assert rows == [{"id": "1"}]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed is True


def test_update_and_delete_require_match_criteria():
    provider = EmpireDbProvider(FakeConnector(FakeConnection()))
    with pytest.raises(ValueError, match="match criteria"):
        provider.update("prospects", {}, {"status": "x"})
    with pytest.raises(ValueError, match="match criteria"):
        provider.delete("prospects", {})


def test_rpc_fails_closed_until_explicitly_mapped():
    provider = EmpireDbProvider(FakeConnector(FakeConnection()))
    with pytest.raises(DataGatewayOperationUnsupported, match="not mapped"):
        provider.rpc("claim_next_gtm_job")


def test_zero_limit_is_preserved():
    connection = FakeConnection()
    connection.next_cursor = Cursor([], ("id",))
    provider = EmpireDbProvider(FakeConnector(connection))

    assert provider.select("prospects", "id", limit=0) == []
    _, params = connection.calls[0]
    assert params[-2:] == (0, 0)


def test_count_is_parameterized_and_returns_exact_value():
    connection = FakeConnection()
    connection.next_cursor = Cursor([(42,)], ("count",))
    provider = EmpireDbProvider(FakeConnector(connection))

    assert provider.count("prospects", {"status": "new"}) == 42

    sql, params = connection.calls[0]
    assert sql == 'SELECT count(*) AS count FROM public."prospects" WHERE "status" = %s'
    assert params == ("new",)
    assert connection.closed is True
