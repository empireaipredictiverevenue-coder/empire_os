"""First-party CRM V11 opt-in HTTP boundary over disposable PostgreSQL 18.

Real Ed25519 verifier, original CRM resolver, original PostgreSQL signed
reader, held SQL applied ONLY to fixture, V11 reducer and redacted HTTP DTO.
"""
from inspect import getclosurevars

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import revenue_crm_transport as transport
from empire_os.crm_revenue_case_private_api import create_private_revenue_case_router
from empire_os.revenue_crm_api import (
    build_authenticated_revenue_crm_resolver, create_revenue_crm_router,
)
from empire_os.revenue_crm_signed_auth import (
    SignedCrmTenantVerifier, build_signed_crm_tenant_authenticator,
)
from empire_os.revenue_crm_suppression_evidence_reader import CRM_LOGIN_AUTHORITY_SQL
from tests.test_crm_scoped_lineage_sql_ephemeral import pg, P, O, OA, OB, TA, TB
from tests.test_crm_v11_scoped_reader_pg18_end_to_end import PROSPECT_VIEW_SQL
from tests.test_revenue_crm_signed_auth import (
    NOW as AUTH_NOW, live_membership, signed, token,
)


def setup_http(pg, signed, monkeypatch, *, enabled=True):
    pg(sql=PROSPECT_VIEW_SQL)
    root = getclosurevars(pg).nonlocals
    assert root["address"].startswith("/tmp/empire-lineage-fixture-")
    dsn = (f"host={root['address']} port={root['port']} "
           "dbname=crm_exact_lineage_fixture user=crm_fixture_a")
    private, keys = signed
    authenticate = build_signed_crm_tenant_authenticator(
        keys, load_membership=live_membership, now=lambda: AUTH_NOW,
    )
    reader = build_authenticated_revenue_crm_resolver(authenticate, {TA: dsn})
    verifier = SignedCrmTenantVerifier(
        keys, load_membership=live_membership, now=lambda: AUTH_NOW,
    )
    # Original transport owner's login-attestation code remains unpublished.
    # Restore pre-existing suppression-reader SQL strictly within this test.
    monkeypatch.setattr(
        transport, "CRM_LOGIN_AUTHORITY_SQL", CRM_LOGIN_AUTHORITY_SQL,
        raising=False,
    )
    router = create_revenue_crm_router(resolve_authenticated_read=reader)
    if enabled:
        router.include_router(create_private_revenue_case_router(
            resolve_authenticated_read=reader,
            signed_crm_verifier=verifier,
            dedicated_tenant_dsns={TA: dsn},
        ))
    app = FastAPI()
    app.include_router(router)
    path = (f"/v1/revenue-crm/prospects/{P}/opportunities/{O}/"
            f"orders/{OA}/revenue-case")
    return TestClient(app), token(private, claims={"tenant_id": TA}), path


def test_original_crm_router_exposes_no_v11_endpoint_by_default(pg, signed, monkeypatch):
    client, bearer, path = setup_http(pg, signed, monkeypatch, enabled=False)
    result = client.get(path, headers={"Authorization": f"Bearer {bearer}"})
    assert result.status_code == 404


def test_private_signed_order_to_founder_http_actual_pg18(pg, signed, monkeypatch):
    client, bearer, path = setup_http(pg, signed, monkeypatch)
    result = client.get(path, headers={"Authorization": f"Bearer {bearer}"})
    assert result.status_code == 200, result.text
    row = result.json()
    assert row["schema_version"] == "empire.crm.founder_revenue_case_view.v1"
    assert row["case_ref"].startswith("revenue_case:")
    assert row["reported_order_state"] == "paid"
    assert row["next_missing_stage"] == "BUYER_ACCEPTANCE"
    assert len(row["stages"]) == 5
    assert all(stage["status"] == "NOT_OBSERVED" for stage in row["stages"])
    assert row["recognized_revenue_verified_here"] is False
    assert row["independent_evidence_attested_here"] is False
    assert row["economic_memory_training_authorized"] is False
    assert row["execution_authority"] == "NONE"
    assert result.headers["cache-control"] == "no-store"
    for secret in (TA, P, O, OA, bearer, "crm_fixture_a", "password", "host="):
        assert secret not in result.text


@pytest.mark.parametrize("authorization", [None, "Bearer fake", "Basic c3Bvb2Y=", "Bearer "])
def test_untrusted_login_cannot_read_existing_order(pg, signed, monkeypatch, authorization):
    client, _, path = setup_http(pg, signed, monkeypatch)
    headers = {} if authorization is None else {"Authorization": authorization}
    result = client.get(path, headers=headers)
    assert result.status_code == 401
    assert "tenant_id" not in result.text


def test_signed_tenant_cannot_claim_other_tenant_order(pg, signed, monkeypatch):
    client, bearer, path = setup_http(pg, signed, monkeypatch)
    result = client.get(path.replace(OA, OB), headers={"Authorization": f"Bearer {bearer}"})
    assert result.status_code == 503
    assert result.json()["detail"] == "authenticated_order_case_unavailable"
    assert TB not in result.text


def test_reader_auth_cannot_be_replaced_by_tenant_header(pg, signed, monkeypatch):
    client, _, path = setup_http(pg, signed, monkeypatch)
    result = client.get(path, headers={"X-Tenant-ID": TA, "Authorization": "Bearer untrusted"})
    assert result.status_code == 401


def test_original_pilot_optin_default_off_and_exact_one_enables_private_route(
    tmp_path, monkeypatch,
):
    from empire_os.revenue_crm_pilot_activation import build_pilot_routers
    from tests.test_revenue_crm_pilot_activation import private_config
    config, _, _ = private_config(tmp_path)
    fragment = "/orders/{order_id}/revenue-case"
    monkeypatch.delenv("EMPIRE_CRM_V11_ORDER_READ_ENABLED", raising=False)
    read_router, login_router = build_pilot_routers(config)
    assert not any(fragment in route.path for route in read_router.routes)
    assert any("/auth/login" in route.path for route in login_router.routes)
    monkeypatch.setenv("EMPIRE_CRM_V11_ORDER_READ_ENABLED", "true")
    read_router, _ = build_pilot_routers(config)
    assert not any(fragment in route.path for route in read_router.routes)
    monkeypatch.setenv("EMPIRE_CRM_V11_ORDER_READ_ENABLED", "1")
    read_router, _ = build_pilot_routers(config)
    assert any(fragment in route.path for route in read_router.routes)
    api = FastAPI()
    api.include_router(read_router)
    response = TestClient(api).get(
        f"/v1/revenue-crm/prospects/{P}/opportunities/{O}/"
        f"orders/{OA}/revenue-case"
    )
    assert response.status_code == 401


def test_untrusted_extra_private_field_is_not_exposed(pg, signed, monkeypatch):
    client, bearer, path = setup_http(pg, signed, monkeypatch)
    from empire_os import crm_revenue_case_private_api as module
    def untrusted(**kwargs):
        return {
            "tenant_id": TA,
            "fulfilment_order_id": OA,
            "founder_case_view": {
                "schema_version": "empire.crm.founder_revenue_case_view.v1",
                "status": "SIGNED_ORDER_OBSERVED_FINANCIAL_PROOF_UNATTESTED",
                "mode": "OBSERVE",
                "case_ref": "revenue_case:" + "a"*24,
                "reported_order_state": "paid",
                "next_missing_stage": "BUYER_ACCEPTANCE",
                "next_original_owner": "SmartCRM",
                "next_original_action": "CHECK",
                "stages": [
                    {"stage": s, "status": "NOT_OBSERVED"}
                    for s in module.STAGES
                ],
                "independent_evidence_attested_here": False,
                "recognized_revenue_verified_here": False,
                "economic_memory_training_authorized": False,
                "database_writes": False,
                "outbound_sent": False,
                "execution_authority": "NONE",
                "password": "private_secret_must_not_leave_server",
            },
        }
    monkeypatch.setattr(module, "review_signed_crm_revenue_case", untrusted)
    result = client.get(path, headers={"Authorization": f"Bearer {bearer}"})
    assert result.status_code == 503
    assert "private_secret_must_not_leave_server" not in result.text
    assert "password" not in result.text


def test_existing_loopback_pilot_service_accepts_optin_without_public_access(
    tmp_path, monkeypatch,
):
    from empire_os.revenue_crm_pilot_service import build_revenue_crm_pilot_service
    from empire_os.revenue_crm_pilot_activation import ACTIVATION_MODE
    from tests.test_revenue_crm_pilot_activation import private_config
    config, _, _ = private_config(tmp_path)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_CONFIG_FILE", str(config))
    monkeypatch.setenv("EMPIRE_CRM_V11_ORDER_READ_ENABLED", "1")
    app = build_revenue_crm_pilot_service()
    client = TestClient(app)
    path = (f"/v1/revenue-crm/prospects/{P}/opportunities/{O}/"
            f"orders/{OA}/revenue-case")
    denied = client.get(path)
    assert denied.status_code == 401
    assert denied.headers["cache-control"] == "no-store"
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["payment_authority"] == "none"
