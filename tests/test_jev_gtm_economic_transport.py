"""Read-only founder transport authorization and session-scope regression."""
from datetime import datetime, timezone
from uuid import UUID

import pytest

from empire_os.jev_gtm_economic_transport import (
    PostgresJevEconomicResearchReader,
    JevEconomicResearchReadUnavailable,
    AUTHORITY_SQL,
)

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
TENANT = str(UUID(int=1))
ENTITY = str(UUID(int=2))


class FakeSession:
    def __init__(self, role=(True, False, False, False), tenant=TENANT, error=None):
        self.role = role
        self.tenant = tenant
        self.error = error
        self.calls = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True
        return False

    def cursor(self):
        return self

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if self.error and "empire_read_economic_signals" in statement:
            raise self.error

    def fetchone(self):
        statement = self.calls[-1][0]
        if statement == AUTHORITY_SQL:
            return self.role
        if statement == "SELECT public.empire_current_tenant_id()":
            return (self.tenant,)
        if statement == "SHOW transaction_read_only":
            return ("on",)
        raise AssertionError("unexpected query")

    def fetchall(self):
        return []


def reader(session):
    return PostgresJevEconomicResearchReader(
        "test-dsn", authenticated_tenant_id=TENANT,
        connect_factory=lambda dsn, connect_timeout: session,
    )


def test_existing_reader_login_and_empty_bound_evidence():
    session = FakeSession()
    packet = reader(session).read(entity_id=ENTITY, as_of=NOW)
    sqls = [statement for statement, _ in session.calls]
    assert sqls[:3] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '4000ms'",
        "SET LOCAL lock_timeout = '2000ms'",
    ]
    assert sqls[3] == AUTHORITY_SQL
    assert sqls[4] == "SET LOCAL ROLE empiredb_tenant_reader"
    assert sqls[5] == "SELECT public.empire_current_tenant_id()"
    assert sqls[6] == "SHOW transaction_read_only"
    assert "empire_read_economic_signals" in sqls[8]
    assert packet["status"] == "NO_CANONICAL_ECONOMIC_EVIDENCE"
    assert packet["signal_count"] == 0
    assert packet["execution_authority"] == "none"
    assert session.closed is True
    assert not any("INSERT" in sql or "UPDATE" in sql or "DELETE" in sql for sql in sqls)


@pytest.mark.parametrize("role", [
    (False, False, False, False),
    (True, True, False, False),
    (True, False, True, False),
    (True, False, False, True),
])
def test_extra_or_privileged_login_membership_is_rejected(role):
    session = FakeSession(role=role)
    with pytest.raises(JevEconomicResearchReadUnavailable, match="authority invalid"):
        reader(session).read(entity_id=ENTITY, as_of=NOW)
    assert not any("empire_read_economic_signals" in sql for sql, _ in session.calls)


def test_wrong_bound_tenant_stops_before_data_access():
    session = FakeSession(tenant=str(UUID(int=99)))
    with pytest.raises(JevEconomicResearchReadUnavailable, match="tenant mismatch"):
        reader(session).read(entity_id=ENTITY, as_of=NOW)
    assert not any("empire_read_economic_signals" in sql for sql, _ in session.calls)


def test_missing_session_tenant_does_not_default():
    session = FakeSession(tenant=None)
    with pytest.raises(JevEconomicResearchReadUnavailable, match="tenant mismatch"):
        reader(session).read(entity_id=ENTITY, as_of=NOW)


def test_missing_dedicated_credentials_fails_before_transport():
    with pytest.raises(JevEconomicResearchReadUnavailable, match="DSN required"):
        PostgresJevEconomicResearchReader("", authenticated_tenant_id=TENANT)


def test_invalid_request_entity_rejected_preconnect():
    session = FakeSession()
    with pytest.raises(JevEconomicResearchReadUnavailable, match="entity UUID"):
        reader(session).read(entity_id="invalid", as_of=NOW)
    assert session.calls == []


def test_database_error_is_sanitized():
    session = FakeSession(error=PermissionError("SENSITIVE PASSWORD OR DSN"))
    with pytest.raises(JevEconomicResearchReadUnavailable) as exc:
        reader(session).read(entity_id=ENTITY, as_of=NOW)
    assert "SENSITIVE" not in str(exc.value)
    assert str(exc.value) == "canonical economic research source unavailable"


def test_caller_supplied_timestamp_needs_timezone():
    session = FakeSession()
    with pytest.raises(JevEconomicResearchReadUnavailable, match="timezone-aware"):
        reader(session).read(entity_id=ENTITY, as_of=datetime(2026, 10, 14))
    assert session.calls == []


def test_http_to_authenticated_readonly_database_chain_with_no_rows():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.founder_jev_api import create_founder_jev_router

    session = FakeSession()
    economic_reader = reader(session)
    app = FastAPI()
    app.include_router(create_founder_jev_router(
        reader=economic_reader, authorizer=lambda request: True,
    ))
    response = TestClient(app).get("/v1/founder-jev/research/" + ENTITY)
    assert response.status_code == 200
    summary = response.json()
    assert summary["status"] == "NO_CANONICAL_ECONOMIC_EVIDENCE"
    assert summary["signal_count"] == 0
    assert summary["outbound_sent"] is False
    assert summary["contains_contact_data"] is False
    assert session.closed is True
    assert sum("empire_read_economic_signals" in sql for sql, _ in session.calls) == 1
    assert session.calls[0][0] == "SET TRANSACTION READ ONLY"


def test_http_unauthorised_does_not_even_open_readonly_database_connection():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.founder_jev_api import create_founder_jev_router

    calls = []
    economic_reader = PostgresJevEconomicResearchReader(
        "test-dsn", authenticated_tenant_id=TENANT,
        connect_factory=lambda *_args, **_kwargs: calls.append(True),
    )
    app = FastAPI()
    app.include_router(create_founder_jev_router(
        reader=economic_reader, authorizer=lambda request: False,
    ))
    response = TestClient(app).get("/v1/founder-jev/research/" + ENTITY)
    assert response.status_code == 403
    assert calls == []
