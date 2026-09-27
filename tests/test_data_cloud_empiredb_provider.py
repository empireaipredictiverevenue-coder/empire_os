import pytest

from empire_os.canonical_data_gateway import DataGatewayOperationUnsupported
from empire_os.data_backends.empiredb import EmpireDbProvider
from empire_os.data_query import ConflictAction, DataFilter, OrderSpec


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


def test_neutral_query_compiles_parameterized_in_and_is_null():
    connection = FakeConnection()
    connection.next_cursor = Cursor([("p1",)], ("prospect_id",))
    provider = EmpireDbProvider(FakeConnector(connection))

    rows = provider.query(
        "prospect_qualifications",
        "prospect_id",
        filters=(
            DataFilter.eq("status", "scored"),
            DataFilter.in_("tier", ("hot", "warm")),
            DataFilter.is_null("entity_id"),
        ),
        order=(OrderSpec("scored_at", descending=True),),
        limit=25,
    )

    assert rows == [{"prospect_id": "p1"}]
    sql, params = connection.calls[0]
    assert '"status" = %s' in sql
    assert '"tier" IN (%s, %s)' in sql
    assert '"entity_id" IS NULL' in sql
    assert 'ORDER BY "scored_at" DESC' in sql
    assert params == ("scored", "hot", "warm", 25, 0)


def test_merge_upsert_uses_explicit_composite_conflict_target():
    connection = FakeConnection()
    connection.next_cursor = Cursor([("p1",)], ("prospect_id",))
    provider = EmpireDbProvider(FakeConnector(connection))

    rows = provider.upsert(
        "prospect_qualifications",
        {
            "prospect_id": "p1",
            "scoring_engine": "engine",
            "scoring_version": "v2",
            "status": "scored",
        },
        conflict_columns=("prospect_id", "scoring_engine", "scoring_version"),
        action=ConflictAction.MERGE,
        return_repr=True,
    )

    assert rows == [{"prospect_id": "p1"}]
    sql, _ = connection.calls[0]
    assert 'ON CONFLICT ("prospect_id", "scoring_engine", "scoring_version")' in sql
    assert 'DO UPDATE SET "status" = EXCLUDED."status"' in sql
    assert connection.commits == 1


def test_insert_ignore_conflicts_uses_untargeted_postgres_conflict_clause():
    connection = FakeConnection()
    provider = EmpireDbProvider(FakeConnector(connection))

    assert provider.insert_ignore_conflicts(
        "commercial_events",
        {"idempotency_key": "k1"},
    ) == []

    sql, params = connection.calls[0]
    assert "ON CONFLICT DO NOTHING" in sql
    assert "ON CONFLICT (" not in sql
    assert params == ("k1",)
    assert connection.commits == 1


def test_extended_query_operators_compile_to_parameterized_sql():
    connection = FakeConnection()
    connection.next_cursor = Cursor([], ("id",))
    provider = EmpireDbProvider(FakeConnector(connection))

    provider.query(
        "prospects",
        "id",
        filters=(
            DataFilter.ne("status", "archived"),
            DataFilter.ilike("metro", "denver"),
            DataFilter.gte("buy_signal_score", 50),
            DataFilter.not_in("status", ("rejected", "cancelled")),
        ),
        order=(
            OrderSpec("buy_signal_score", descending=True, nulls_last=True),
            OrderSpec("created_at"),
        ),
        limit=5,
    )

    sql, params = connection.calls[0]
    assert '"status" <> %s' in sql
    assert '"metro" ILIKE %s' in sql
    assert '"buy_signal_score" >= %s' in sql
    assert '"status" NOT IN (%s, %s)' in sql
    assert 'ORDER BY "buy_signal_score" DESC NULLS LAST, "created_at" ASC' in sql
    assert params == ("archived", "denver", 50, "rejected", "cancelled", 5, 0)
