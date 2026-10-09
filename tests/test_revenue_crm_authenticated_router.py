"""Request-scoped Revenue CRM activation boundary: isolated mocks, no live DB."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import (
    AuthenticatedRevenueCrmRead, create_revenue_crm_router,
)
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

A = "00000000-0000-0000-0000-000000000101"
B = "00000000-0000-0000-0000-000000000102"
P = "00000000-0000-0000-0000-000000000003"


class Column:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self, bound_tenant, *, returned_tenant=None):
        self.bound_tenant = bound_tenant
        self.returned_tenant = returned_tenant or bound_tenant
        self.calls = []
        self.description = [Column("tenant_id"), Column("prospect_id")]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return (self.bound_tenant,)

    def fetchall(self):
        return [(self.returned_tenant, P)]


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


def repo(tenant_id=A, *, session_tenant=A, row_tenant=None):
    cursor = Cursor(session_tenant, returned_tenant=row_tenant)
    reader = PostgresRevenueCrmRepository(
        "test-only-dsn", tenant_id=tenant_id,
        connect_factory=lambda _: Connection(cursor),
    )
    return reader, cursor


def client_with_server_resolver(reader, *, authenticated_tenant=None):
    app = FastAPI()
    # Test-only simulation of a pre-authenticated *server-side* identity.
    # No request header, query parameter, cookie or body is ever used.
    app.state.verified_tenant = authenticated_tenant
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=lambda request: (
            AuthenticatedRevenueCrmRead(
                tenant_id=request.app.state.verified_tenant,
                repository=reader,
            )
            if request.app.state.verified_tenant else None
        )
    ))
    return TestClient(app)


def test_unverified_request_cannot_select_tenant_with_headers_or_query():
    reader, cursor = repo()
    client = client_with_server_resolver(reader)
    response = client.get(
        f"/v1/revenue-crm/prospects?tenant_id={A}",
        headers={"X-Tenant-ID": A, "Authorization": "Bearer fake"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "authenticated_crm_scope_required"
    assert cursor.calls == []


def test_verified_request_uses_db_bound_scope_and_ignores_header_spoof():
    reader, cursor = repo()
    client = client_with_server_resolver(reader, authenticated_tenant=A)
    response = client.get(
        "/v1/revenue-crm/prospects?limit=3",
        headers={"X-Tenant-ID": B},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["tenant_id"] == A
    assert any(sql.startswith("SET LOCAL ROLE empire_revenue_crm_reader")
               for sql, _ in cursor.calls)
    assert any(sql == "SELECT public.empire_current_tenant_id()"
               for sql, _ in cursor.calls)


def test_mismatched_server_principal_and_repository_fails_before_connect():
    reader, cursor = repo()
    response = client_with_server_resolver(
        reader, authenticated_tenant=B
    ).get("/v1/revenue-crm/prospects")
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"
    assert cursor.calls == []


def test_mismatched_authenticated_database_session_remains_blocked():
    reader, cursor = repo(tenant_id=A, session_tenant=B)
    with pytest.raises(Exception, match="tenant scope unverified"):
        reader.prospects(limit=1)
    assert not any("FROM public.revenue_crm_prospects" in sql
                   for sql, _ in cursor.calls)


def test_resolver_exception_is_redacted():
    app = FastAPI()
    def failing(_):
        raise RuntimeError("private login and credential")
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=failing
    ))
    response = TestClient(app).get("/v1/revenue-crm/buyers")
    assert response.status_code == 503
    assert "private" not in str(response.json())


def test_global_postgres_reader_and_ambiguous_sources_cannot_be_mounted():
    reader, _ = repo()
    with pytest.raises(ValueError, match="request-scoped"):
        create_revenue_crm_router(repository=reader)
    with pytest.raises(ValueError, match="ambiguous"):
        create_revenue_crm_router(
            repository=object(),
            resolve_authenticated_read=lambda _: None,
        )

def test_database_read_failure_is_sanitized_to_503():
    reader, cursor = repo()
    original = cursor.execute

    def break_on_data_query(sql, params=None):
        if "FROM public.revenue_crm_prospects" in sql:
            raise RuntimeError("postgres://private:secret@host")
        original(sql, params)

    cursor.execute = break_on_data_query
    response = client_with_server_resolver(
        reader, authenticated_tenant=A
    ).get("/v1/revenue-crm/prospects")
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"
    assert "secret" not in str(response.json())
