"""Tenant-scoped, read-only canonical Revenue CRM transport contracts."""
import pytest

from empire_os.revenue_crm_transport import (
    BUYER_LIST_SQL, PROSPECT_LIST_SQL, PROSPECT_ONE_SQL, ROLE,
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000001"
BUYER = "00000000-0000-0000-0000-000000000002"


class Description:
    def __init__(self, name):
        self.name = name


class FakeCursor:
    def __init__(self, rows, columns, *, bound_tenant=TENANT, failure=False):
        self.rows = rows
        self.description = [Description(name) for name in columns]
        self.bound_tenant = bound_tenant
        self.calls = []
        self.failure = failure

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self.failure:
            raise RuntimeError("postgresql://private:password@host")

    def fetchone(self):
        return (self.bound_tenant,)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor


def repository(rows, columns, *, bound_tenant=TENANT, scope=TENANT, failure=False):
    cursor = FakeCursor(rows, columns, bound_tenant=bound_tenant, failure=failure)
    repo = PostgresRevenueCrmRepository(
        "postgresql://test-only", tenant_id=scope,
        connect_factory=lambda dsn: FakeConnection(cursor),
    )
    return repo, cursor


def test_prospect_list_requires_trusted_tenant_and_static_filtered_view():
    repo, cursor = repository(
        [(TENANT, PROSPECT, "Acme")], ["tenant_id", "prospect_id", "business_name"],
    )
    records = repo.prospects(limit=10)
    assert records[0]["business_name"] == "Acme"
    assert records[0]["tenant_id"] == TENANT
    assert cursor.calls == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL ROLE " + ROLE, None),
        ("SET LOCAL statement_timeout = '8000ms'", None),
        ("SELECT public.empire_current_tenant_id()", None),
        (PROSPECT_LIST_SQL, (TENANT, 10)),
    ]
    assert "tenant_id = %s" in PROSPECT_LIST_SQL
    assert "SELECT *" not in PROSPECT_LIST_SQL
    assert "tenant_id," in PROSPECT_LIST_SQL


def test_buyer_list_must_be_tenant_bound_and_bounded():
    repo, cursor = repository([(TENANT, BUYER, 4)],
                              ["tenant_id", "buyer_id", "available_capacity"])
    result = repo.buyers(limit=25)
    assert result[0]["available_capacity"] == 4
    assert cursor.calls[-1] == (BUYER_LIST_SQL, (TENANT, 25))
    assert ("SET LOCAL statement_timeout = '4000ms'", None) in cursor.calls
    assert ("SET LOCAL statement_timeout = '8000ms'", None) not in cursor.calls
    assert "WHERE tenant_id = %s" in BUYER_LIST_SQL


def test_single_prospect_requires_canonical_uuid_and_tenant():
    repo, cursor = repository([], ["tenant_id", "prospect_id"])
    with pytest.raises(RevenueCrmTransportError, match="canonical prospect_id UUID"):
        repo.prospect("legacy-id")
    assert cursor.calls == []


def test_single_prospect_filters_tenant_and_prospect_even_when_empty():
    repo, cursor = repository([], ["tenant_id", "prospect_id"])
    assert repo.prospect(PROSPECT) is None
    assert cursor.calls[-1] == (PROSPECT_ONE_SQL, (TENANT, PROSPECT))
    assert ("SET LOCAL statement_timeout = '8000ms'", None) in cursor.calls
    assert "WHERE tenant_id = %s AND prospect_id = %s" in PROSPECT_ONE_SQL


def test_limit_out_of_range_fails_before_connect():
    repo = PostgresRevenueCrmRepository(
        "postgresql://test-only", tenant_id=TENANT,
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(RevenueCrmTransportError, match="limit out of range"):
        repo.prospects(limit=501)


def test_missing_dsn_fails_closed():
    with pytest.raises(RevenueCrmTransportError, match="DSN required"):
        PostgresRevenueCrmRepository("", tenant_id=TENANT)


@pytest.mark.parametrize("scope", ["", "not-uuid", "buyer@fake.test", None, OTHER+"suffix"])
def test_invalid_or_missing_tenant_authority_is_rejected_preconnect(scope):
    with pytest.raises(RevenueCrmTransportError, match="canonical tenant_id UUID"):
        PostgresRevenueCrmRepository(
            "postgresql://test-only", tenant_id=scope,
            connect_factory=lambda dsn: (_ for _ in ()).throw(
                AssertionError("no connection must occur")
            ),
        )


@pytest.mark.parametrize("bound", [None, OTHER, "", "not-a-tenant"])
def test_mismatched_or_unbound_session_never_runs_data_query(bound):
    repo, cursor = repository(
        [(TENANT, PROSPECT)], ["tenant_id", "prospect_id"],
        bound_tenant=bound,
    )
    with pytest.raises(RevenueCrmTransportError, match="scope unverified"):
        repo.prospects(limit=10)
    assert (PROSPECT_LIST_SQL, (TENANT, 10)) not in cursor.calls
    assert cursor.calls[-1][0] == "SELECT public.empire_current_tenant_id()"


def test_cross_tenant_row_is_rejected_even_if_mocked_db_ignores_sql_predicate():
    repo, cursor = repository(
        [(OTHER, PROSPECT)], ["tenant_id", "prospect_id"],
    )
    with pytest.raises(RevenueCrmTransportError, match="scope unverified"):
        repo.prospects(limit=10)
    assert cursor.calls[-1] == (PROSPECT_LIST_SQL, (TENANT, 10))


def test_missing_tenant_column_or_duplicate_columns_rejected():
    for columns, values in [
        (["prospect_id"], [(PROSPECT,)]),
        (["tenant_id", "tenant_id"], [(TENANT, TENANT)]),
    ]:
        repo, _ = repository(values, columns)
        with pytest.raises(RevenueCrmTransportError, match="scope unverified"):
            repo.prospects(limit=10)


def test_broken_database_error_redacts_credentials_and_original_exception():
    secret = "postgresql://admin:very-private@localhost/empiredb"
    repo = PostgresRevenueCrmRepository(
        secret, tenant_id=TENANT,
        connect_factory=lambda _: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    with pytest.raises(RevenueCrmTransportError) as e:
        repo.buyers(limit=10)
    assert str(e.value) == "dedicated CRM read unavailable or tenant scope unverified"
    assert "very-private" not in str(e.value)
    assert e.value.__cause__ is None


def test_query_failure_after_connection_also_redacts():
    repo, _ = repository([], ["tenant_id", "prospect_id"], failure=True)
    with pytest.raises(RevenueCrmTransportError, match="scope unverified"):
        repo.prospects(limit=10)


def test_empty_valid_tenant_scope_may_return_no_rows_without_leaking():
    repo, cursor = repository([], ["tenant_id", "prospect_id"])
    assert repo.prospects(limit=10) == []
    assert cursor.calls[-1] == (PROSPECT_LIST_SQL, (TENANT, 10))
