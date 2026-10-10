"""Dedicated founder CRM HTTP mount: existing first-party auth; fail closed."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_revenue_crm_pilot_activation import (
    A, ACTIVATION_MODE, private_config,
)
from empire_os.revenue_crm_pilot_service import build_revenue_crm_pilot_service

UNIT = (
    Path(__file__).resolve().parents[1]
    / "deploy/systemd/empire-revenue-crm-pilot.service"
)


def test_default_and_wrong_mode_do_not_build_http_app(monkeypatch):
    monkeypatch.delenv("EMPIRE_CRM_PILOT_MODE", raising=False)
    monkeypatch.delenv("EMPIRE_CRM_PILOT_CONFIG_FILE", raising=False)
    with pytest.raises(RuntimeError, match="not_authorized"):
        build_revenue_crm_pilot_service()
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", "OBSERVE")
    with pytest.raises(RuntimeError, match="not_authorized"):
        build_revenue_crm_pilot_service()


def test_approved_mode_still_requires_private_complete_config(monkeypatch):
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.delenv("EMPIRE_CRM_PILOT_CONFIG_FILE", raising=False)
    with pytest.raises(RuntimeError, match="config_missing"):
        build_revenue_crm_pilot_service()


def test_real_existing_routes_no_public_signup_and_no_hub_exposure(tmp_path, monkeypatch):
    path, _, _ = private_config(tmp_path)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_CONFIG_FILE", str(path))
    client = TestClient(build_revenue_crm_pilot_service())
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {
        "ok": True, "service": "empire-crm-first-party-pilot",
        "mode": ACTIVATION_MODE, "outbound_authority": "none",
        "payment_authority": "none", "database_provisioning": False,
    }
    assert health.headers["cache-control"] == "no-store"
    assert health.headers["x-frame-options"] == "DENY"

    # No bearer identity -> cannot read or preview any tenant prospect.
    for endpoint in (
        "/v1/revenue-crm/prospects",
        "/v1/revenue-crm/buyers",
        "/v1/revenue-crm/journeys/designer",
    ):
        res = client.get(endpoint, headers={"X-Tenant-ID": A, "X-Role": "owner"})
        assert res.status_code == 401
        assert res.json()["detail"] == "authenticated_crm_scope_required"
        assert res.headers["cache-control"] == "no-store"
    assert client.post("/v1/revenue-crm/auth/login", json={}).status_code == 422
    assert client.post("/v1/revenue-crm/auth/accept-invite", json={}).status_code == 422

    # No self-signup, backend hub, or unrelated commercial actions mounted.
    for endpoint in ("/openapi.json", "/docs", "/v1/revenue-crm/auth/register",
                     "/v1/revenue-os/execute", "/v1/affiliate/ingress"):
        assert client.get(endpoint).status_code == 404
    assert not any(
        getattr(route, "path", "").startswith("/v1/revenue-crm/auth/signup")
        for route in client.app.routes
    )


def test_privately_provisioned_config_failure_blocks_startup(tmp_path, monkeypatch):
    path, _, _ = private_config(tmp_path)
    path.chmod(0o644)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_CONFIG_FILE", str(path))
    with pytest.raises(ValueError, match="permissions"):
        build_revenue_crm_pilot_service()


def test_unit_is_loopback_and_separate_from_legacy_founder_read_api():
    text = UNIT.read_text()
    assert "127.0.0.1 --port 8775" in text
    assert "--no-proxy-headers" in text
    assert "/etc/empire/crm-pilot.env" in text
    assert "EnvironmentFile=/etc/empire/crm-pilot.env" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ReadOnlyPaths=/srv/empire_os" in text
    assert "revenue_crm_pilot_asgi:app" in text
    assert "empire_os.hub:app" not in text
    assert "founder_dashboard_service:app" not in text
    assert "0.0.0.0" not in text
    assert "ExecStartPre=/bin/sh" not in text
