from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.astra_activation import (
    AstraActivationEvidence,
    assess_astra_activation_readiness,
)
from empire_os.astra_api import create_astra_router


def evidence(**overrides):
    values = {
        "canonical_migrations_applied": True,
        "observer_login_provisioned": True,
        "observer_dsn_configured": True,
        "policy_bindings_complete": True,
        "observer_service_installed": True,
        "observer_timer_enabled": True,
        "feedback_rpc_verified": True,
        "operational_evidence_rpc_verified": True,
        "first_revenue_loop_verified": False,
        "evidence_refs": ("migration:phase4", "rpc:astra"),
    }
    values.update(overrides)
    return AstraActivationEvidence(**values)


def test_observe_activation_can_be_ready_before_revenue_loop():
    result = assess_astra_activation_readiness(evidence())
    assert result.observe_activation_ready is True
    assert result.consequential_authority_ready is False
    assert result.observe_blockers == ()
    assert result.consequential_blockers == (
        "first_revenue_loop_not_verified",
    )


def test_missing_runtime_prerequisites_are_explicit():
    result = assess_astra_activation_readiness(
        evidence(
            observer_dsn_configured=False,
            observer_timer_enabled=False,
        )
    )
    assert result.observe_activation_ready is False
    assert "observer_dsn_not_configured" in result.observe_blockers
    assert "observer_timer_not_enabled" in result.observe_blockers


def test_consequential_authority_requires_every_gate():
    result = assess_astra_activation_readiness(
        evidence(first_revenue_loop_verified=True)
    )
    assert result.observe_activation_ready is True
    assert result.consequential_authority_ready is True
    assert result.execution_authority == "none"
    assert result.side_effects == "none"


def test_api_preview_is_non_mutating():
    app = FastAPI()
    app.include_router(create_astra_router())
    client = TestClient(app)
    response = client.post(
        "/v1/astra/activation/readiness/preview",
        json={
            "canonical_migrations_applied": True,
            "observer_login_provisioned": True,
            "observer_dsn_configured": True,
            "policy_bindings_complete": True,
            "observer_service_installed": True,
            "observer_timer_enabled": True,
            "feedback_rpc_verified": True,
            "operational_evidence_rpc_verified": True,
            "first_revenue_loop_verified": False,
            "evidence_refs": ["migration:phase4", "rpc:astra"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    readiness = body["readiness"]
    assert readiness["observe_activation_ready"] is True
    assert readiness["consequential_authority_ready"] is False
