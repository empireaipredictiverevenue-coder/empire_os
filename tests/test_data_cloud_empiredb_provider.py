import pytest

from empire_os.canonical_data_gateway import DataGatewayOperationUnsupported
from empire_os.data_backends.empiredb import EmpireDbProvider
from empire_os.data_query import ConflictAction, DataFilter, OrderSpec
from empire_os.data_values import JsonValue


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self, rows=(), columns=()):
        self._rows = list(rows)
        self.description = [Description(name) for name in columns] if columns else None

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


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
        self.adapted = []

    def _open_connection(self):
        return self.connection

    def adapt_value(self, value):
        self.adapted.append(value)
        if isinstance(value, JsonValue):
            return ("jsonb", value.value)
        if isinstance(value, dict):
            return ("jsonb", value)
        return value


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


def test_write_values_use_connector_json_adaptation():
    connection = FakeConnection()
    connection.next_cursor = Cursor([("1",)], ("id",))
    connector = FakeConnector(connection)
    provider = EmpireDbProvider(connector)

    provider.insert(
        "commercial_events",
        {
            "id": "1",
            "payload": {"score": 90},
            "tags": JsonValue(["qualified", "hot"]),
        },
    )

    _, params = connection.calls[0]
    assert params == (
        "1",
        ("jsonb", {"score": 90}),
        ("jsonb", ["qualified", "hot"]),
    )


def test_delete_match_values_use_connector_adaptation():
    connection = FakeConnection()
    connector = FakeConnector(connection)
    provider = EmpireDbProvider(connector)

    provider.delete("events", {"payload_key": JsonValue({"id": "x"})})

    _, params = connection.calls[0]
    assert params == (("jsonb", {"id": "x"}),)


def test_targeted_ignore_conflicts_uses_explicit_conflict_target():
    connection = FakeConnection()
    provider = EmpireDbProvider(FakeConnector(connection))

    assert provider.insert_ignore_conflicts(
        "business_entities",
        {"id": "e1", "canonical_name": "Example"},
        conflict_columns=("id",),
    ) == []

    sql, params = connection.calls[0]
    assert 'ON CONFLICT ("id") DO NOTHING' in sql
    assert params == ("e1", "Example")
    assert connection.commits == 1


def test_targeted_ignore_conflicts_requires_target_columns_in_row():
    provider = EmpireDbProvider(FakeConnector(FakeConnection()))

    with pytest.raises(ValueError, match="conflict columns must be present"):
        provider.insert_ignore_conflicts(
            "business_entities",
            {"canonical_name": "Example"},
            conflict_columns=("id",),
        )


def test_mapped_rpc_uses_exact_contract_order_and_commits():
    connection = FakeConnection()
    connection.next_cursor = Cursor([({"exists": True},)], ("result",))
    provider = EmpireDbProvider(FakeConnector(connection))

    result = provider.rpc(
        "get_commercial_product_readiness",
        {"p_product_code": "managed_service"},
    )

    assert result == {"exists": True}
    sql, params = connection.calls[0]
    assert sql == 'SELECT public."get_commercial_product_readiness"(%s)'
    assert params == ("managed_service",)
    assert connection.commits == 1
    assert connection.closed is True


def test_sensitive_payment_rpc_stays_off_generic_gateway():
    provider = EmpireDbProvider(FakeConnector(FakeConnection()))

    with pytest.raises(DataGatewayOperationUnsupported, match="not mapped"):
        provider.rpc(
            "approve_bsc_payment_request",
            {
                "p_request_id": "00000000-0000-0000-0000-000000000001",
                "p_approved_by": "operator",
                "p_approval_note": "approved",
            },
        )


def test_mapped_rpc_rejects_parameter_shape_drift():
    provider = EmpireDbProvider(FakeConnector(FakeConnection()))

    with pytest.raises(ValueError, match="parameters do not match contract"):
        provider.rpc(
            "get_commercial_product_readiness",
            {"wrong_key": "managed_service"},
        )


def test_cutover_safe_rpc_is_mapped_but_voice_auto_approval_is_not():
    from empire_os.data_backends.empiredb import _RPC_PARAMS

    assert "propose_call_ready_voice_intent" in _RPC_PARAMS
    assert "ingest_prospect_atomic" in _RPC_PARAMS
    assert "register_commercial_product_identity" in _RPC_PARAMS
    assert "auto_approve_voice_intent" not in _RPC_PARAMS


def test_migration_017_numeric_rpc_contract_is_explicit():
    import re
    from pathlib import Path

    from empire_os.data_backends.empiredb import (
        _RPC_NUMERIC_PARAMS,
        _RPC_PARAMS,
    )

    sql = Path(
        "migrations/empiredb/"
        "017_cutover_compatibility_rpc_parity.sql"
    ).read_text()

    pattern = re.compile(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\."
        r"([A-Za-z0-9_]+)\s*\((.*?)\)\s*"
        r"RETURNS",
        re.I | re.S,
    )

    expected = {}

    for match in pattern.finditer(sql):
        name = match.group(1)

        if name not in _RPC_PARAMS:
            continue

        numeric = []

        for raw in match.group(2).split(","):
            raw = raw.strip()

            m = re.match(
                r"(p_[A-Za-z0-9_]+)\s+(.+)",
                raw,
                re.I,
            )

            if (
                m
                and re.search(
                    r"\bnumeric\b",
                    m.group(2),
                    re.I,
                )
            ):
                numeric.append(m.group(1))

        if numeric:
            expected[name] = frozenset(numeric)

    assert _RPC_NUMERIC_PARAMS == expected


def test_numeric_rpc_scores_bind_as_decimal():
    from decimal import Decimal

    connection = FakeConnection()
    connection.next_cursor = Cursor(
        [({"decision": "proposed"},)],
        ("result",),
    )

    provider = EmpireDbProvider(
        FakeConnector(connection)
    )

    provider.rpc(
        "propose_buyer_candidate_review",
        {
            "p_prospect_id":
                "00000000-0000-0000-0000-000000000001",
            "p_entity_id": None,
            "p_contact_name": "Test Buyer",
            "p_contact_title": "Director",
            "p_contact_email": "buyer@example.com",
            "p_offer_key": "test-offer",
            "p_company_score": 85.5,
            "p_decision_score": 0.91,
            "p_evidence": {"source": "test"},
            "p_idempotency_key": "numeric-contract-test",
        },
    )

    _, params = connection.calls[0]

    assert params[6] == Decimal("85.5")
    assert params[7] == Decimal("0.91")
    assert isinstance(params[6], Decimal)
    assert isinstance(params[7], Decimal)


def test_ingest_prospect_atomic_binds_text_and_text_array_contract():
    connection = FakeConnection()
    connection.next_cursor = Cursor([({"decision": "created"},)], ("result",))
    provider = EmpireDbProvider(FakeConnector(connection))

    result = provider.rpc(
        "ingest_prospect_atomic",
        {
            "p_prospect": {"business_name": "Example"},
            "p_evidence": {"source": "test"},
            "p_ingest_key": "ingest:test",
            "p_identity_keys": ["domain:example.com", "name_metro:example|denver"],
        },
    )

    assert result == {"decision": "created"}
    sql, params = connection.calls[0]
    assert sql == (
        'SELECT public."ingest_prospect_atomic"('
        '%s::jsonb, %s::jsonb, %s::text, %s::text[])'
    )
    assert params[2] == "ingest:test"
    assert params[3] == [
        "domain:example.com",
        "name_metro:example|denver",
    ]
