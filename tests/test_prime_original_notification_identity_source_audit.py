"""Original PRIME reminder Identity source discovery: cannot imply consent."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from empire_os.prime_original_notification_identity_source_audit import (
    review_original_reminder_identity_source,
    founder_reminder_identity_source_audit,
)
from empire_os.consent_api import create_consent_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service
from fastapi import FastAPI


def test_existing_original_consent_is_prospect_scoped_and_unbound():
    audit=review_original_reminder_identity_source()
    assert audit["status"]=="PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING"
    assert audit["original_hub_consent_router_created_without_repository"] is True
    assert audit["original_consent_repository_default_none"] is True
    assert audit["prospect_scoped_consent_api_present"] is True
    assert audit["unbound_consent_api_fail_closed_503"] is True
    assert audit["existing_signed_crm_auth_is_read_only"] is True
    assert audit["held_empiredb_061_deny_all_default_in_source"] is True
    assert audit["verified_reminder_device_consent_authority"] is False
    assert audit["original_identity_owner_approval_verified"] is False
    assert audit["real_provider_sandbox_configured"] is False
    assert audit["original_empiredb_writes"] is False
    assert audit["real_device_alert_sent"] is False
    assert audit["execution_authority"]=="none"
    assert len(audit["blockers"])==6


def test_original_prospect_consent_api_without_repository_refuses_grant():
    app=FastAPI()
    app.include_router(create_consent_router())
    with TestClient(app) as client:
        health=client.get("/v1/consent/health")
        assert health.status_code==200
        assert health.json()["repository_available"] is False
        assert client.get("/v1/consent/prospects/fake?channel=voice").status_code==503
        assert client.post("/v1/consent/prospects/fake/opt-in",
                           json={"channel":"voice"}).status_code==503


def test_unverified_source_code_change_returns_review_required(tmp_path):
    root=tmp_path
    (root/"empire_os").mkdir()
    (root/"migrations/empiredb").mkdir(parents=True)
    original=Path(__file__).resolve().parents[1]
    for path in (
        "empire_os/hub.py","empire_os/consent_api.py",
        "empire_os/revenue_crm_signed_auth.py",
        "migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql",
    ):
        source=original/path
        target=root/path
        target.write_text(source.read_text())
    baseline=review_original_reminder_identity_source(repo_root=root)
    assert baseline["status"]=="PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING"
    hub=root/"empire_os/hub.py"
    hub.write_text(hub.read_text().replace(
        "app.include_router(create_consent_router())",
        "app.include_router(create_consent_router(production_repository))"
    ))
    changed=review_original_reminder_identity_source(repo_root=root)
    assert changed["status"]=="ORIGINAL_IDENTITY_CONTRACT_REVIEW_REQUIRED"
    assert changed["verified_reminder_device_consent_authority"] is False
    assert changed["execution_authority"]=="none"


@pytest.mark.parametrize("field,value",[
    ("verified_reminder_device_consent_authority",True),
    ("original_identity_owner_approval_verified",True),
    ("real_provider_sandbox_configured",True),
    ("canonical_original_empiredb_migrations_approved",True),
    ("real_device_alert_sent",True),
    ("original_empiredb_writes",True),
    ("execution_authority","live"),
    ("repository_code_is_not_live_configuration_proof",False),
    ("blockers",[]),
])
def test_founder_rejects_caller_forged_activation(field,value):
    original=review_original_reminder_identity_source()
    original[field]=value
    with pytest.raises(ValueError,match="untrusted_original_identity_source_authority_claim"):
        founder_reminder_identity_source_audit(original)


def test_original_founder_status_read_only_never_connected():
    projection=founder_reminder_identity_source_audit(
        review_original_reminder_identity_source()
    )
    assert projection["real_device_consent_verified"] is False
    assert projection["real_provider_connected"] is False
    assert projection["execution_authority"]=="none"
    with TestClient(build_founder_dashboard_service()) as api:
        response=api.get("/v1/founder-dashboard/prime-digital-twin")
        assert response.status_code==200
        status=response.json()["original_reminder_identity_source"]
        assert status["status"]=="PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING"
        assert status["prospect_consent_is_not_device_permission"] is True
        assert status["real_device_consent_verified"] is False
        assert response.json()["original_notification_gateway"]["status"]=="NOT_CONNECTED"
        assert api.post("/v1/founder-dashboard/prime-digital-twin").status_code==405


def test_operator_source_audit_cli_stays_nonexecuting():
    import json
    import subprocess
    import sys
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(
        [sys.executable,"-B",str(root/"scripts/review_prime_notification_identity_sources_20261024.py")],
        cwd=root,capture_output=True,text=True,timeout=10,
    )
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data["status"]=="PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING"
    assert len(data["blockers"])==6
    assert data["verified_reminder_device_consent_authority"] is False
    assert data["execution_authority"]=="none"
    assert data["original_empiredb_writes"] is False
    assert data["real_device_alert_sent"] is False
