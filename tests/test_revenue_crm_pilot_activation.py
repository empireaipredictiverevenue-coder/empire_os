"""Private CRM activation wiring: no credentials, tenant or API activation by default."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_pilot_activation import (
    ACTIVATION_MODE, CONFIG_SCHEMA, build_pilot_routers,
    create_crm_routers_for_hub,
)

A = "00000000-0000-0000-0000-000000000101"
B = "00000000-0000-0000-0000-000000000102"


def dsn(user: str) -> str:
    return (
        "host=/var/run/postgresql port=5432 dbname=empiredb "
        "user=" + user
    )


def private_config(tmp_path: Path) -> tuple[Path, Path, dict]:
    signer = Ed25519PrivateKey.generate()
    key_file = tmp_path / "signing.pem"
    key_file.write_bytes(signer.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    key_file.chmod(0o600)
    cfg = {
        "schema_version": CONFIG_SCHEMA,
        "founder_approval_ref": "founder:crm-pilot-v1",
        "key_id": "empire-crm-pilot",
        "signing_private_key_file": str(key_file),
        "auth_dsn": dsn("empire_crm_auth_login"),
        "membership_dsn": dsn("empire_crm_membership_login"),
        "tenant_dsns": {A: dsn("empire_crm_tenant_0123456789ab")},
    }
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(cfg))
    path.chmod(0o600)
    return path, key_file, cfg


def test_hub_default_mode_is_unconfigured_without_login_endpoint(monkeypatch):
    monkeypatch.delenv("EMPIRE_CRM_PILOT_MODE", raising=False)
    monkeypatch.delenv("EMPIRE_CRM_PILOT_CONFIG_FILE", raising=False)
    routers = create_crm_routers_for_hub()
    assert len(routers) == 1
    api = FastAPI()
    api.include_router(routers[0])
    response = TestClient(api).get("/v1/revenue-crm/prospects")
    assert response.status_code == 503
    assert response.json()["detail"] == "revenue_crm_repository_not_activated"
    assert TestClient(api).post("/v1/revenue-crm/auth/login", json={}).status_code == 404


def test_valid_private_config_only_mounts_authenticated_routes(tmp_path, monkeypatch):
    path, key_file, _ = private_config(tmp_path)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.setenv("EMPIRE_CRM_PILOT_CONFIG_FILE", str(path))
    routers = create_crm_routers_for_hub()
    assert len(routers) == 2
    api = FastAPI()
    for router in routers:
        api.include_router(router)
    client = TestClient(api)
    response = client.get("/v1/revenue-crm/prospects")
    assert response.status_code == 401
    assert response.json()["detail"] == "authenticated_crm_scope_required"
    assert client.post("/v1/revenue-crm/auth/login", json={}).status_code == 422
    assert key_file.exists()
    assert path.exists()


@pytest.mark.parametrize("bad", [
    "NO", "true", "OBSERVE", "APPROVED", "APPROVED_PRODUCTION",
])
def test_unknown_activation_mode_fails_closed(monkeypatch, bad):
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", bad)
    with pytest.raises(ValueError, match="unrecognised CRM activation"):
        create_crm_routers_for_hub()


def test_explicit_mode_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("EMPIRE_CRM_PILOT_MODE", ACTIVATION_MODE)
    monkeypatch.delenv("EMPIRE_CRM_PILOT_CONFIG_FILE", raising=False)
    with pytest.raises(ValueError, match="configuration missing"):
        create_crm_routers_for_hub()


def test_world_readable_config_is_rejected(tmp_path):
    path, _, _ = private_config(tmp_path)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        build_pilot_routers(path)


def test_world_readable_private_signing_key_rejected(tmp_path):
    path, key, _ = private_config(tmp_path)
    key.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        build_pilot_routers(path)


def test_symlink_config_rejected(tmp_path):
    path, _, _ = private_config(tmp_path)
    fake = tmp_path / "shortcut.json"
    fake.symlink_to(path)
    with pytest.raises(ValueError, match="absolute regular"):
        build_pilot_routers(fake)


@pytest.mark.parametrize("corruption", [
    {"founder_approval_ref": ""},
    {"schema_version": "other"},
    {"key_id": ".."},
    {"tenant_dsns": {}},
    {"tenant_dsns": {"unknown-tenant": dsn("empire_crm_tenant_0123456789ab")}},
    {"tenant_dsns": {A: dsn("empiredb_app")}},
    {"tenant_dsns": {A: dsn("empire_revenue_crm_reader")}},
    {"tenant_dsns": {
        A: dsn("empire_crm_tenant_0123456789ab"),
        B: dsn("empire_crm_tenant_0123456789ab"),
    }},
    {"auth_dsn": dsn("empiredb_app")},
    {"membership_dsn": dsn("empiredb_app")},
    {"auth_dsn": "host=db.example.com port=5432 dbname=empiredb user=empire_crm_auth_login"},
    {"membership_dsn": "host=/var/run/postgresql port=5432 dbname=otherdb user=empire_crm_membership_login"},
])
def test_unapproved_or_unsafe_identity_configurations_rejected(tmp_path, corruption):
    path, _, cfg = private_config(tmp_path)
    cfg.update(corruption)
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        build_pilot_routers(path)


def test_private_key_mismatch_or_absent_file_fails_closed(tmp_path):
    path, key_path, cfg = private_config(tmp_path)
    key_path.write_text("not a signing key")
    with pytest.raises(ValueError, match="signing key"):
        build_pilot_routers(path)
    cfg["signing_private_key_file"] = str(tmp_path / "missing.pem")
    path.write_text(json.dumps(cfg))
    with pytest.raises(FileNotFoundError):
        build_pilot_routers(path)


def test_unexpected_runtime_config_field_fails_closed(tmp_path):
    path, _, cfg = private_config(tmp_path)
    cfg["tenant_approved"] = True
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="approved complete"):
        build_pilot_routers(path)
