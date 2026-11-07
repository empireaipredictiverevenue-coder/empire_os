"""Focused tests for the original Data Cloud founder usage deployment adapter.

All checks are offline. No sudo, production SQL, service restarts or secrets.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    ROOT / "scripts/data_cloud_public_entrypoint_20261107.py",
    ROOT / "scripts/data_cloud_private_entrypoint_20261107.py",
)
SCRIPT = ROOT / "scripts/activate_data_cloud_founder_usage_20261107.py"


@pytest.fixture
def install_module():
    spec = importlib.util.spec_from_file_location("pilot_release_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_proposed_release_is_syntactically_complete():
    for path in (*ENTRYPOINTS, SCRIPT):
        ast.parse(path.read_text(encoding="utf8"))


def test_public_data_cloud_key_and_real_original_route():
    text = ENTRYPOINTS[0].read_text()
    assert "from linkedin_browser_ui_entrypoint import app" in text
    assert "DataCloudPublicVerifier" in text
    assert "create_gateway_candidate_app" in text
    assert "usage_only=True" in text
    assert "RELEASE_EVIDENCE.json" in text
    assert "verified_requirements" in text
    assert "Ed25519PrivateKey" not in text
    assert "signing_private_key_file" not in text
    assert "release_evidence=lambda:" not in text
    assert "DataCloudFounderAuthority" not in text


def test_private_exchange_reuses_existing_crm_and_separate_key():
    text = ENTRYPOINTS[1].read_text()
    assert "from linkedin_oidc_issuer_workqueue_entrypoint import app" in text
    assert "DataCloudFounderAuthority" in text
    assert "build_account_bound_membership_lookup" in text
    assert "SignedCrmTenantVerifier" in text
    assert "CREDENTIALS_DIRECTORY" in text
    assert "attach_founder_session(" in text
    assert "expose_exchange=True" in text
    assert "empire-data-cloud-signing.pem" in text
    assert "create_gateway_candidate_app" not in text


def test_runtime_uses_only_one_original_gateway_and_no_new_services():
    src = SCRIPT.read_text()
    assert 'PUB_SVC = "empire-public-gateway.service"' in src
    assert 'CRM_SVC = "empire-revenue-crm-pilot.service"' in src
    assert 'LoadCredential=empire-data-cloud-signing.pem:' in src
    assert 'data_cloud_public_entrypoint_20261107:app' in src
    assert 'data_cloud_private_entrypoint_20261107:app' in src
    assert 'billing_enabled":False' in src
    assert 'search_and_audits_enabled":False' in src
    assert 'paid_providers_enabled":False' in src
    assert 'owner_lease_verified":True' in src
    assert "systemctl" in src and "daemon-reload" in src
    assert "ROLLBACK" in src or "rollback" in src
    assert "SOURCE=" not in src
    assert "sqlite" not in src.lower()


def test_operator_command_preserves_existing_pythonpath(install_module, monkeypatch):
    monkeypatch.setattr(install_module, "run",
                        lambda args: 'ONE=1 PYTHONPATH=/existing/crm:/existing/oauth OTHER=2')
    path = install_module.environment_path("original-issuer")
    assert path == "/existing/crm:/existing/oauth:" + str(install_module.RELEASE)


def test_operator_command_rejects_changed_entrypoint(install_module, monkeypatch):
    monkeypatch.setattr(install_module, "run", lambda args: 'ONE=1')
    with pytest.raises(RuntimeError,match="existing_service_pythonpath"):
        install_module.environment_path("missing")


def test_credential_writer_refuses_symlink_and_existing_file(install_module, tmp_path):
    original = tmp_path/"original"
    original.write_text("do-not-modify")
    alias = tmp_path/"alias"
    alias.symlink_to(original)
    with pytest.raises(RuntimeError,match="refusing_existing_release_file"):
        install_module.atomic_file(alias, b"secret", 0o600)
    assert original.read_text()=="do-not-modify"
    path = tmp_path/"private"
    install_module.atomic_file(path,b"sample",0o600,uid=os.geteuid(),gid=os.getegid())
    assert path.read_bytes()==b"sample"
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    with pytest.raises(RuntimeError,match="refusing_existing_release_file"):
        install_module.atomic_file(path,b"overwrite",0o600)


def test_original_source_provenance_is_preserved():
    manifest = json.loads(
        (ROOT/"empire_os/predictive_cloud_customer_api/SOURCE_PROVENANCE.json").read_text()
    )
    assert manifest["source_archive_sha256"] == (
        "718e752945abd27a20ca28f168f8e20e3b7fe0011151a1a270af76cd0c090ff5"
    )
    assert manifest["only_import_rewrites"] is True
    assert manifest["public_gateway_activation"] is False
    assert manifest["production_migration"] is False



def test_actual_existing_crm_owner_column_and_preflight_safe_mode():
    src = SCRIPT.read_text()
    assert "SELECT subject::text||'|'||tenant_id::text" in src
    assert "FROM public.empire_crm_tenant_memberships" in src
    assert "ORDER BY subject;" in src
    assert "SELECT user_id::text" not in src
    assert "revoked_at IS NULL" in src
    assert "(valid_until IS NULL OR valid_until>now())" in src
    assert 'mode.add_argument("--preflight-read-only"' in src
    assert 'elif args.preflight_read_only:' in src
    assert 'pre = identity_preflight()' in src
    assert 'PRODUCTION_WRITES=0; RESTARTS=0; SECRETS_ISSUED=0' in src
