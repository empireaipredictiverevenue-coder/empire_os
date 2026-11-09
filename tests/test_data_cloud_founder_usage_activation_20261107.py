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


def test_meter_connections_follow_existing_loopback_scram_hba():
    original = SCRIPT.read_text()
    public = ENTRYPOINTS[0].read_text()
    assert 'host="127.0.0.1",port=5432,password=password' in original
    assert 'host="127.0.0.1",' in public
    assert 'meter_loopback_scram_hba_not_verified' in original
    assert 'meter_loopback_postgresql_not_available' in original
    assert 'host="/var/run/postgresql",port=5432,password=password' not in original


def test_resume_requires_exact_disabled_existing_admission():
    text = SCRIPT.read_text()
    assert 'identity_preflight(resuming=True)' in text
    assert 'SELECT active,held,monthly_request_cap,monthly_cost_cap_micros' in text
    assert 'rolled_back_tenant_not_held' in text
    assert 'rolled_back_key_not_exactly_disabled_or_expired' in text
    assert 'rolled_back_meter_role_not_disabled' in text
    assert 'data_cloud_signing_credential_missing' not in text
    assert 'resumed_existing_founder_credentials":True' in text
    assert '--resume-preflight-read-only' in text
    assert '--resume-founder-approved' in text


def test_resume_preflight_fails_before_writes_when_state_invalid(install_module, monkeypatch):
    actions = []
    monkeypatch.setattr(install_module, "resume_preflight",
                        lambda: (_ for _ in ()).throw(RuntimeError("unexpected_state")))
    monkeypatch.setattr(install_module, "repair_exact_frozen_public_wrapper",
                        lambda: actions.append("unwanted_mutation"))
    with pytest.raises(RuntimeError, match="unexpected_state"):
        install_module.resume()
    assert actions == []


def test_resume_failed_operation_rolls_back_original_services(install_module, monkeypatch):
    actions=[]
    monkeypatch.setattr(install_module, "resume_preflight",
                        lambda: ({"actor":"founder","tenant":"test"}, {}, "existing-key"))
    monkeypatch.setattr(install_module, "repair_exact_frozen_public_wrapper",
                        lambda: (_ for _ in ()).throw(RuntimeError("frozen_image_drift")))
    monkeypatch.setattr(install_module, "clean_failed_release",
                        lambda: actions.append("rollback") or True)
    with pytest.raises(RuntimeError, match="frozen_image_drift"):
        install_module.resume()
    assert actions == ["rollback"]


def test_resume_happy_path_uses_existing_key_and_one_original_service_chain(
    install_module, monkeypatch
):
    events = []
    pre={"actor":"founder","tenant":"test"}
    cfg={"meter_password":"stored-not-output"}
    monkeypatch.setattr(install_module, "resume_preflight",
                        lambda: (pre,cfg,"preexisting-test-key"))
    monkeypatch.setattr(install_module, "repair_exact_frozen_public_wrapper",
                        lambda: events.append("reconcile_exact_wrapper"))
    monkeypatch.setattr(install_module, "resume_existing_database",
                        lambda p,c,k: events.append(("reactivate_only",k)))
    monkeypatch.setattr(install_module, "record_verified_evidence",
                        lambda p: events.append("owner_evidence"))
    monkeypatch.setattr(install_module, "environment_path",
                        lambda svc: "/existing/owner/env")
    monkeypatch.setattr(install_module, "install_overlays",
                        lambda pub,priv: events.append("additive_overlays"))
    monkeypatch.setattr(install_module, "run",
                        lambda args: events.append(tuple(args)) or "")
    monkeypatch.setattr(install_module, "verify_service_route",
                        lambda path,port,status: True)
    monkeypatch.setattr(install_module, "canary",
                        lambda p,key: events.append(("live_canary",key)))
    monkeypatch.setattr(install_module, "atomic_file",
                        lambda path,data,mode,**kw: events.append("receipt"))
    monkeypatch.setattr(install_module, "clean_failed_release",
                        lambda: pytest.fail("unexpected rollback in happy path"))
    install_module.resume()
    assert events[0] == "reconcile_exact_wrapper"
    assert events[1] == ("reactivate_only","preexisting-test-key")
    assert events[2] == "owner_evidence"
    assert events[3] == "additive_overlays"
    assert ("live_canary","preexisting-test-key") in events
    assert events[-1] == "receipt"
    assert not any("CREATE ROLE" in str(e) or "INSERT INTO" in str(e) for e in events)


def test_rollback_updates_only_original_key_and_tenant(install_module,monkeypatch,tmp_path):
    from dataclasses import dataclass
    from uuid import UUID
    tenant="11111111-2222-4333-8444-555555555555"
    runtime=tmp_path/"runtime"
    runtime.mkdir()
    original=tmp_path/"root-only"
    original.mkdir()
    (runtime/"runtime.json").write_text(json.dumps({
        "owner_tenant_id":tenant,
        "scope":"FOUNDER_ONLY_USAGE_NO_PROVIDERS",
        "release_version":1,
    }))
    (original/"founder-api-key.secret").write_text("synthetic-test-key-with-safe-length-001")
    monkeypatch.setattr(install_module,"RUNTIME",runtime)
    monkeypatch.setattr(install_module,"ROOT_ONLY",original)
    calls=[]
    monkeypatch.setattr(install_module,"postgres",lambda sql:calls.append(sql) or "")
    assert install_module.hold_database() is True
    assert len(calls)==1
    statement=calls[0]
    assert "SET held=true,active=false\n              WHERE tenant_id=" in statement
    assert "SET active=false\n              WHERE tenant_id=" in statement
    assert "ALTER ROLE empire_data_cloud_meter_login NOLOGIN;" in statement
    assert "UPDATE empire_data_cloud_api.tenants SET held=true,active=false;" not in statement
    assert "UPDATE empire_data_cloud_api.api_keys SET active=false;" not in statement
    assert tenant in statement


def test_resume_preexisting_evidence_same_identity_reused(install_module,monkeypatch,tmp_path):
    from hashlib import sha256
    baseline={
        "public_service_preimage_sha":sha256(b"pub-original").hexdigest(),
        "crm_service_preimage_sha":sha256(b"crm-original").hexdigest(),
    }
    monkeypatch.setattr(
        install_module, "run",
        lambda args: "pub-original" if install_module.PUB_SVC in args else "crm-original",
    )
    previous=tmp_path/"RELEASE_EVIDENCE.json"
    evidence={
        "mode":"FOUNDER_ONLY_USAGE_NO_PROVIDERS",
        "source_sql_sha256":install_module.SRC_SHA,
        "public_service_preimage_sha256":baseline["public_service_preimage_sha"],
        "crm_service_preimage_sha256":baseline["crm_service_preimage_sha"],
        "verified_requirements":{key:True for key in (
            "owner_lease_verified","founder_only_path_verified",
            "signed_data_session_verified","production_meter_role_verified",
            "production_meter_functions_verified","rollback_preflight_verified",
            "fresh_local_restore_receipt_verified",
            "dba_sql_and_acl_acceptance_verified",
            "existing_gateway_rollback_verified",
            "billing_and_paid_provider_calls_disabled"
        )},
    }
    previous.write_text(json.dumps(evidence))
    previous.chmod(0o600)
    monkeypatch.setattr(install_module,"RUNTIME",tmp_path)
    monkeypatch.setattr(install_module,"UBUNTU",type("U",(),{
        "pw_uid":__import__("os").geteuid(),"pw_gid":__import__("os").getegid(),
    })())
    monkeypatch.setattr(install_module,"atomic_file",
                        lambda *args,**kwargs: pytest.fail("should reuse verified evidence"))
    install_module.record_verified_evidence(baseline)
    evidence["source_sql_sha256"]="unexpected-drift"
    previous.write_text(json.dumps(evidence))
    with pytest.raises(RuntimeError,match="earlier_release_evidence_mismatch"):
        install_module.record_verified_evidence(baseline)



def test_failed_db_auth_does_not_restart_unmodified_owner_services(
    install_module,monkeypatch,tmp_path
):
    # The first failed attempt restarted both unrelated services even though
    # their drop-ins were never installed. Never repeat that churn.
    calls=[]
    monkeypatch.setattr(install_module,"PUB_OVERLAY",tmp_path/"public.conf")
    monkeypatch.setattr(install_module,"CRM_OVERLAY",tmp_path/"private.conf")
    monkeypatch.setattr(install_module,"hold_database",lambda:calls.append("hold") or True)
    monkeypatch.setattr(install_module,"run",lambda args:calls.append(tuple(args)) or "")
    assert install_module.clean_failed_release() is True
    assert calls==["hold"]


def test_rollback_removes_only_our_two_overlays_and_restores_services(
    install_module,monkeypatch,tmp_path
):
    calls=[]
    pub=tmp_path/"founder-public.conf"
    private=tmp_path/"founder-private.conf"
    pub.write_text("scoped")
    private.write_text("scoped")
    other=tmp_path/"other-owners.conf"
    other.write_text("keep me")
    monkeypatch.setattr(install_module,"PUB_OVERLAY",pub)
    monkeypatch.setattr(install_module,"CRM_OVERLAY",private)
    monkeypatch.setattr(install_module,"hold_database",lambda:calls.append("hold") or True)
    monkeypatch.setattr(install_module,"run",lambda args:calls.append(tuple(args)) or "")
    assert install_module.clean_failed_release() is True
    assert not pub.exists() and not private.exists()
    assert other.read_text()=="keep me"
    assert calls==["hold",("systemctl","daemon-reload"),
        ("systemctl","restart",install_module.CRM_SVC),
        ("systemctl","restart",install_module.PUB_SVC)]


def test_existing_database_connect_is_the_only_added_database_privilege():
    source = SCRIPT.read_text()
    connect_grant = "GRANT CONNECT ON DATABASE empiredb TO empire_data_cloud_meter_login;"
    connect_revoke = "REVOKE CONNECT ON DATABASE empiredb FROM empire_data_cloud_meter_login;"
    assert source.count(connect_grant) == 2  # original admission and exact resume
    assert source.count(connect_revoke) == 1  # fail-closed rollback
    assert source.count("verify_meter_database_connect_only()") == 3
    assert "founder_pilot_database_privilege_drift" in source
    assert "ALTER ROLE empire_data_cloud_meter_login LOGIN;" in source
    assert "GRANT ALL ON DATABASE" not in source
    assert "GRANT CREATE ON DATABASE" not in source
    assert "GRANT TEMPORARY ON DATABASE" not in source


@pytest.mark.parametrize(
    ("acl","allowed"),
    [
        ("t|f|f",True),
        ("f|f|f",False),
        ("t|t|f",False),
        ("t|f|t",False),
        ("t|t|t",False),
    ],
)
def test_meter_db_grant_reader_fails_closed_on_extra_privileges(
    install_module,monkeypatch,acl,allowed
):
    monkeypatch.setattr(install_module,"postgres",lambda sql:acl)
    if allowed:
        install_module.verify_meter_database_connect_only()
    else:
        with pytest.raises(RuntimeError,match="meter_database_connect_only_grant_not_verified"):
            install_module.verify_meter_database_connect_only()


def test_resume_does_not_connect_when_exact_db_acl_is_wrong(install_module,monkeypatch):
    import psycopg
    calls=[]
    def sql_runner(sql):
        calls.append(sql)
        if sql.startswith("BEGIN;"):
            return ""
        return "f|f|f"
    monkeypatch.setattr(install_module,"postgres",sql_runner)
    monkeypatch.setattr(
        psycopg,"connect",
        lambda **kwargs:pytest.fail("driver_connect_must_follow_exact_db_acl_check"),
    )
    with pytest.raises(RuntimeError,match="meter_database_connect_only_grant_not_verified"):
        install_module.resume_existing_database(
            {"tenant":"11111111-2222-4333-8444-555555555555"},
            {"meter_password":"synthetic-only"}, "synthetic-only-test-key",
        )
    assert len(calls)==2
    assert "GRANT CONNECT ON DATABASE empiredb TO empire_data_cloud_meter_login;" in calls[0]
    assert "ALTER ROLE empire_data_cloud_meter_login LOGIN;" in calls[0]
