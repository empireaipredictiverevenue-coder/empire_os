from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router
from empire_os.saas_api_access import (
    ApiAccessEvidence,
    assess_api_access_readiness,
)
from empire_os.saas_scale import TenantMembership


def evidence(**overrides):
    values = {
        "membership": TenantMembership(
            tenant_id="tenant-1",
            user_id="user-1",
            role="admin",
            status="active",
        ),
        "active_subscription": True,
        "tenant_isolation_verified": True,
        "requested_scopes": ("read:predictions", "read:analytics"),
        "evidence_refs": ("membership:m1", "subscription:s1", "rls:r1"),
    }
    values.update(overrides)
    return ApiAccessEvidence(**values)


def test_admin_read_scopes_are_ready_for_review_only():
    result = assess_api_access_readiness(evidence())
    assert result.issuance_ready is True
    assert result.approved_scopes == (
        "read:analytics",
        "read:predictions",
    )
    assert result.rejected_scopes == ()
    assert result.execution_authority == "none"
    assert result.api_key_issuance is False
    assert result.secret_material_generated is False


def test_non_admin_role_is_blocked():
    result = assess_api_access_readiness(
        evidence(
            membership=TenantMembership(
                tenant_id="tenant-1",
                user_id="user-1",
                role="analyst",
            )
        )
    )
    assert result.issuance_ready is False
    assert "admin_role_required" in result.blockers


def test_mutating_scope_is_rejected():
    result = assess_api_access_readiness(
        evidence(
            requested_scopes=(
                "read:analytics",
                "write:campaigns",
            )
        )
    )
    assert result.issuance_ready is False
    assert result.approved_scopes == ("read:analytics",)
    assert result.rejected_scopes == ("write:campaigns",)
    assert "unsupported_or_mutating_scope_requested" in result.blockers


def test_subscription_and_isolation_evidence_are_required():
    result = assess_api_access_readiness(
        evidence(
            active_subscription=False,
            tenant_isolation_verified=False,
        )
    )
    assert result.issuance_ready is False
    assert "active_subscription_required" in result.blockers
    assert "tenant_isolation_not_verified" in result.blockers


def test_api_preview_never_generates_key_material():
    app = FastAPI()
    app.include_router(create_saas_router())
    client = TestClient(app)
    response = client.post(
        "/v1/saas/api-access/readiness/preview",
        json={
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "role": "admin",
            "membership_status": "active",
            "active_subscription": True,
            "tenant_isolation_verified": True,
            "requested_scopes": ["read:analytics"],
            "evidence_refs": [
                "membership:m1",
                "subscription:s1",
                "rls:r1",
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["api_key_issuance"] is False
    assert body["api_key_revocation"] is False
    assert body["secret_material_generated"] is False
    assert body["readiness"]["issuance_ready"] is True
