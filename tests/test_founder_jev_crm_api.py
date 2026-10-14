"""Founder CRM review is reachable only through authenticated tenant-bound reader."""
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.founder_jev_api import create_founder_jev_router
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, PROSPECT_COLUMNS, PROSPECT_LIST_SQL,
)

TENANT, OTHER, PROSPECT = (str(UUID(int=i)) for i in (1, 99, 2))
PATH = "/v1/founder-jev/crm-prospects/review"
COLUMNS = PROSPECT_COLUMNS.split(",")


class Column:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self, bound_tenant=TENANT):
        self.bound_tenant = bound_tenant
        self.description = [Column(c) for c in COLUMNS]
        self.calls = []
        values = dict.fromkeys(COLUMNS)
        values.update({
            "tenant_id": TENANT, "prospect_id": PROSPECT,
            "business_name": "PRIVATE_FICTIONAL_COMPANY_NAME",
            "prospect_status": "new",
            "niche": "roofing", "metro": "London",
        })
        self.rows = [tuple(values[c] for c in COLUMNS)]

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None): self.calls.append((sql, params))
    def fetchone(self): return (self.bound_tenant,)
    def fetchall(self): return self.rows


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor


def actual_type_resolver(cursor, *, claimed_tenant=TENANT):
    repo = PostgresRevenueCrmRepository(
        "synthetic", tenant_id=TENANT,
        connect_factory=lambda _: Connection(cursor),
    )
    access = AuthenticatedRevenueCrmRead(
        tenant_id=claimed_tenant, repository=repo,
    )
    return lambda req: access


def client(*, cursor=None, authorizer=None, resolver=None):
    app = FastAPI()
    app.include_router(create_founder_jev_router(
        authorizer=authorizer,
        resolve_authenticated_crm=resolver,
    ))
    return TestClient(app)


def test_default_service_does_not_publish_crm_data_path():
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    paths = build_founder_dashboard_service().openapi()["paths"]
    assert PATH not in paths


def test_server_authorizer_required_for_any_crm_resolver():
    with pytest.raises(ValueError, match="must be paired"):
        create_founder_jev_router(resolve_authenticated_crm=lambda req: None)


def test_access_denial_skips_resolver_and_db():
    cursor = Cursor()
    touched = []
    result = client(
        cursor=cursor,
        authorizer=lambda req: False,
        resolver=lambda req: touched.append(True),
    ).get(PATH)
    assert result.status_code == 403
    assert touched == []
    assert cursor.calls == []


def test_unbound_request_does_not_read_db():
    cursor = Cursor()
    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=lambda req: None,
    ).get(PATH)
    assert response.status_code == 401
    assert cursor.calls == []


def test_validated_crm_session_returns_only_review_not_buyers():
    cursor = Cursor()
    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor),
    ).get(PATH + "?limit=10")
    assert response.status_code == 200
    packet = response.json()
    assert packet["scanned_count"] == 1
    assert packet["original_provider_reply_count_verified"] is None
    assert packet["commercial_buyer_count_verified"] is None
    assert packet["contact_permission_granted"] is False
    assert packet["execution_authority"] == "none"
    assert packet["items"][0]["buyer_identity_verified"] is False
    assert "PRIVATE_FICTIONAL_COMPANY_NAME" not in response.text
    assert cursor.calls[0] == ("SET TRANSACTION READ ONLY", None)
    assert cursor.calls[-1] == (PROSPECT_LIST_SQL, (TENANT, 10))


def test_server_side_tenant_mismatch_fails_closed():
    cursor = Cursor(bound_tenant=OTHER)
    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor),
    ).get(PATH)
    assert response.status_code == 503
    assert "PRIVATE_FICTIONAL_COMPANY_NAME" not in response.text


def test_claimed_scope_mismatch_fails_before_connect():
    cursor = Cursor()
    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor, claimed_tenant=OTHER),
    ).get(PATH)
    assert response.status_code == 503
    assert cursor.calls == []


def test_arbitrary_object_is_not_a_trusted_repository():
    cursor = Cursor()
    class Rogue:
        tenant_id = TENANT
        def prospects(self, *, limit):
            raise AssertionError("untrusted reader should never run")

    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=lambda req: AuthenticatedRevenueCrmRead(TENANT, Rogue()),
    ).get(PATH)
    assert response.status_code == 503
    assert cursor.calls == []


def test_client_cannot_increase_bounded_scan():
    cursor = Cursor()
    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor),
    ).get(PATH + "?limit=10000")
    assert response.status_code == 422
    assert cursor.calls == []


def test_read_error_sanitizes_credentials():
    cursor = Cursor()
    def boom(_):
        raise RuntimeError("secret private password")
    response = client(
        cursor=cursor,
        authorizer=lambda req: True,
        resolver=boom,
    ).get(PATH)
    assert response.status_code == 503
    assert "password" not in response.text


def test_unsafe_unauthenticated_founding_configuration_is_not_activated():
    response = client(
        authorizer=lambda req: True,
        resolver=lambda req: None,
    ).get("/v1/founder-jev/status")
    assert response.status_code == 200
    status = response.json()
    assert status["crm_reader_configured"] is True
    assert status["production_activated"] is False
    assert status["buyers_identified"] is None


def test_extra_contact_fields_in_crm_api_output_refused(monkeypatch):
    import empire_os.founder_jev_api as api

    cursor = Cursor()
    original = api.read_jev_crm_review

    def leaking(*args, **kwargs):
        packet = original(*args, **kwargs)
        packet["items"][0]["email"] = "private@example.invalid"
        return packet

    monkeypatch.setattr(api, "read_jev_crm_review", leaking)
    response = client(
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor),
    ).get(PATH)
    assert response.status_code == 503
    assert "private@example.invalid" not in response.text


def test_malicious_buyer_verified_flag_is_refused(monkeypatch):
    import empire_os.founder_jev_api as api

    cursor = Cursor()
    original = api.read_jev_crm_review

    def unsafe(*args, **kwargs):
        packet = original(*args, **kwargs)
        packet["items"][0]["buyer_identity_verified"] = True
        return packet

    monkeypatch.setattr(api, "read_jev_crm_review", unsafe)
    response = client(
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor),
    ).get(PATH)
    assert response.status_code == 503


def test_founder_crm_status_does_not_expose_live_prospect_totals():
    cursor = Cursor()
    response = client(
        authorizer=lambda req: True,
        resolver=actual_type_resolver(cursor),
    ).get("/v1/founder-jev/status")
    assert response.status_code == 200
    status = response.json()
    assert status["crm_prospect_review_available"] is True
    assert status["real_canonical_rows_verified"] is None
    assert status["buyers_identified"] is None
    assert cursor.calls == []
