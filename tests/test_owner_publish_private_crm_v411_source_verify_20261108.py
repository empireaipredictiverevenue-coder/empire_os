"""Guarded single-CRM owner release invariants; tests never restart services."""
from __future__ import annotations
import ast
from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest

SOURCE=Path(__file__).resolve().parents[1]/(
    "scripts/owner_publish_private_crm_v411_source_verify_20261108.py")
spec=importlib.util.spec_from_file_location("private_held_source_owner_release",SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_only_existing_private_crm_single_port_restarted():
    body=SOURCE.read_text()
    assert mod.UNIT=="empire-revenue-crm-pilot.service"
    assert "127.0.0.1 --port 8783 --no-proxy-headers" in body
    assert mod.OLD_MAIN=="data_cloud_verify_ui_entrypoint_20261108:app"
    assert mod.NEW_MAIN=="private_crm_original_v411_source_entrypoint_20261108:app"
    assert mod.OLD_MAIN != mod.NEW_MAIN
    assert "public-gateway" not in body
    assert "daemon-reload" in body
    assert "systemctl" in body


def test_original_owner_release_sha_pins_and_unique_dropin():
    assert len(mod.FILES)==2
    for filename,sha in mod.FILES.items():
        data=(mod.ROOT/"scripts"/filename).read_bytes()
        assert sha256(data).hexdigest()==sha
    assert mod.COMMIT=="b9570b2f0c0a2e1776ccbc3824bc8cbb74b60a33"
    assert mod.DROPIN.name.startswith("zzzzzzzzzzzz-")
    assert mod.RELEASE.name.startswith("data-cloud-predictive-source-review")
    assert not mod.DROPIN.exists()
    assert not mod.RELEASE.exists()


def test_original_private_credential_loaded_by_systemd_only():
    code=SOURCE.read_text()
    assert mod.CREDS.name=="rights_reader_dsn"
    assert mod.CRED_NAME=="empire-predictive-source-rights-dsn"
    assert "LoadCredential=" in code
    assert "private_file(RELEASE/filename,data,0o444)" in code
    assert "private_file(DROPIN,text.encode(),0o644)" in code
    assert "os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW" in code
    assert 'BACKUP.mkdir(mode=0o700)' in code
    assert "private_file(BACKUP/\"original_effective_systemd_unit.txt\"" in code


def test_route_identity_and_unverified_real_browser_not_misrepresented():
    code=SOURCE.read_text()
    assert mod.REV=="/v1/predictive-cloud/source-rights/verify"
    assert '"anonymous_new_source_route"]!=401' in code
    assert '"read_only_source_get"]!=405' in code
    assert '"anonymous_data_exchange"]!=401' in code
    assert '"signed_browser_http200_verified":False' in code
    assert '"source_rights_independently_approved":False' in code
    assert '"customer_predictions_enabled":False' in code
    assert '"paid_providers_enabled":False' in code
    assert "CREDENTIALS_DIRECTORY" not in code  # owned by sealed entrypoint


def test_original_browser_assets_must_remain_sha_pinned():
    assert len(mod.HTML_SHA)==64 and len(mod.JS_SHA)==64
    assert mod.HTML_SHA=="1d86ce33e8f7b4edb63a52a14ccf76f0f7dfc617a2763173eceaa845ab849282"
    assert mod.JS_SHA=="7f50fa36289a7539a33e7b058038c4373b9d64e556f2f5c751fb3932c707be6f"
    assert '"Cache-Control")!="no-store"' in SOURCE.read_text()


def test_pre_restart_failed_release_does_not_restart_healthy_crm(monkeypatch):
    actions=[]
    from types import SimpleNamespace
    monkeypatch.setattr(mod,"DROPIN",SimpleNamespace(unlink=lambda *a,**kw:actions.append("remove")))
    monkeypatch.setattr(mod,"cmd",lambda args,**kw:actions.append(tuple(args)) or "ok")
    monkeypatch.setattr(mod,"http",lambda path,**kw:(404 if path==mod.REV else 200,b"",{}))
    result=mod.rollback(restart_needed=False)
    assert result=="ORIGINAL_CRM_EXECSTART_RESTORED_AND_HEALTHY"
    assert ("systemctl","daemon-reload") in actions
    assert ("systemctl","restart",mod.UNIT) not in actions


def test_release_script_is_syntactically_stable_and_not_installer_migration():
    ast.parse(SOURCE.read_text())
    code=SOURCE.read_text()
    for prohibited in ("pg_dump", "CREATE TABLE", "CREATE ROLE", "ALTER ROLE", "ALTER SYSTEM",
                       "INSERT INTO public.empire_predictive_source"):
        assert prohibited not in code
    assert "systemd-analyze" in code
    assert "restart_needed=started" in code
