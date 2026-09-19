from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router
from empire_os.saas_readiness import (
    SaasScaleSnapshot,
    assess_saas_scale_readiness,
)


def client():
    app = FastAPI()
    app.include_router(create_saas_router())
    return TestClient(app)


def test_missing_scale_evidence_blocks_readiness():
    result = assess_saas_scale_readiness(
        SaasScaleSnapshot(
            tenant_id="tenant-1",
            active_members=5,
            observed_monthly_usage=800,
            observed_usage_limit=None,
            active_subscription=False,
            tenant_isolation_verified=False,
            white_label_requested=True,
            white_label_configured=False,
            evidence_refs=("tenant-read-model",),
        )
    )
    assert result.ready_for_review is False
    assert "observed_usage_limit" in result.missing_evidence
    assert "active_subscription" in result.missing_evidence
    assert "tenant_isolation_verified" in result.missing_evidence
    assert "white_label_configured" in result.missing_evidence
    assert result.execution_authority == "none"


def test_verified_scale_evidence_is_review_ready_only():
    result = assess_saas_scale_readiness(
        SaasScaleSnapshot(
            tenant_id="tenant-1",
            active_members=12,
            observed_monthly_usage=800,
            observed_usage_limit=1000,
            active_subscription=True,
            tenant_isolation_verified=True,
            white_label_requested=True,
            white_label_configured=True,
            evidence_refs=("usage-meter", "tenant-isolation-check"),
        )
    )
    assert result.ready_for_review is True
    assert result.utilization_ratio == 0.8
    assert result.provisioning_execution is False
    assert result.billing_execution is False
    assert result.approval_required is True


def test_scale_readiness_api_is_non_executing():
    response = client().post(
        "/v1/saas/scale-readiness/preview",
        json={
            "tenant_id": "tenant-1",
            "active_members": 12,
            "observed_monthly_usage": 800,
            "observed_usage_limit": 1000,
            "active_subscription": True,
            "tenant_isolation_verified": True,
            "white_label_requested": False,
            "white_label_configured": False,
            "evidence_refs": ["usage-meter"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["provisioning_execution"] is False
    assert body["billing_execution"] is False
    assert body["readiness"]["ready_for_review"] is True
