"""Offline-only operator deployment/rollback tests for founder CRM verify button."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/activate_data_cloud_verify_ui_20261108.py"
spec=importlib.util.spec_from_file_location("data_cloud_verify_release_test",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_exact_original_service_rollback_footprint():
    source=SRC.read_text()
    assert 'SERVICE="empire-revenue-crm-pilot.service"' in source
    assert 'EXISTING_ENTRYPOINT="data_cloud_private_entrypoint_20261107:app"' in source
    assert 'NEW_ENTRYPOINT="data_cloud_verify_ui_entrypoint_20261108:app"' in source
    assert "systemctl" in source
    assert 'systemctl","restart",SERVICE' in source
    assert "empire-public-gateway.service" not in source
    assert "ALTER ROLE" not in source
    assert "GRANT CONNECT" not in source
    assert "paid_provider" not in source
    assert "POST /v1/data/search" not in source
    assert "LoadCredential" not in source
    assert "ROLLBACK" in source.upper()


def test_operator_services_deny_unverified_original_chain(monkeypatch):
    monkeypatch.setattr(m,"run",lambda args: {
        ("systemctl","is-active",m.SERVICE):"active",
        ("systemctl","show",m.SERVICE,"-p","ExecStart","--value"):
            "ExecStart=/srv/empire_os/.venv/bin/uvicorn other_module:app",
        }.get(tuple(args),""))
    with pytest.raises(RuntimeError,match="original_owner_entrypoint_changed"):
        m.systemd_preimage()


def test_atomic_file_refuses_existing_file_and_symlinks(monkeypatch,tmp_path):
    file=tmp_path/"original"
    file.write_text("other")
    symlink=tmp_path/"alias"
    symlink.symlink_to(file)
    with pytest.raises(RuntimeError,match="refusing_other_owner_release_path"):
        m.atomic_install(symlink,b"replace",0o600)
    assert file.read_text()=="other"
    with pytest.raises(RuntimeError,match="refusing_other_owner_release_path"):
        m.atomic_install(file,b"replace",0o600)
    assert file.read_text()=="other"


def test_rollback_does_not_restart_services_if_no_overlay(monkeypatch,tmp_path):
    monkeypatch.setattr(m,"OVERLAY",tmp_path/"missing.conf")
    called=[]
    monkeypatch.setattr(m,"run",lambda args:called.append(args) or "")
    monkeypatch.setattr(m,"fetch",lambda path,method="GET":(200,""))
    assert m.rollback_only_additive_overlay() is False
    assert called==[]


def test_scoped_overlay_rollback_restores_original_service(monkeypatch,tmp_path):
    overlay=tmp_path/"verify-ui.conf"
    overlay.write_bytes(b"temporary-test-overlay")
    other=tmp_path/"other-owner.conf"
    other.write_bytes(b"never touch")
    monkeypatch.setattr(m,"OVERLAY",overlay)
    called=[]
    def systemd(args):
        if "-p" in args and "ExecStart" in args:
            return m.EXISTING_ENTRYPOINT
        called.append(tuple(args))
        return ""
    monkeypatch.setattr(m,"run",systemd)
    monkeypatch.setattr(m,"fetch",lambda path,method="GET":(200,""))
    assert m.rollback_only_additive_overlay(m.sha(b"temporary-test-overlay")) is True
    assert not overlay.exists()
    assert other.read_bytes()==b"never touch"
    assert called==[("systemctl","daemon-reload"),("systemctl","restart",m.SERVICE)]


def test_scoped_overlay_rollback_rejects_other_owner_drift(monkeypatch,tmp_path):
    overlay=tmp_path/"verify-ui.conf"
    overlay.write_bytes(b"unexpected owner mutation")
    monkeypatch.setattr(m,"OVERLAY",overlay)
    with pytest.raises(RuntimeError,match="rollback_blocked_other_owner_changed_overlay"):
        m.rollback_only_additive_overlay(m.sha(b"old approved content"))
    assert overlay.read_bytes()==b"unexpected owner mutation"


def test_preflight_rejects_earlier_or_partial_release(monkeypatch,tmp_path):
    monkeypatch.setattr(m.os,"geteuid",lambda:0)
    monkeypatch.setattr(m,"RELEASE",tmp_path)
    monkeypatch.setattr(m,"run",lambda args:"" if "status" in args else (
        "feature/predictive-cloud-usage-review-20261107"))
    with pytest.raises(RuntimeError,match="prior_or_partial_verify_ui_release_present"):
        m.preflight()


def test_readback_requires_button_and_existing_security(monkeypatch):
    def fetch(path,method="GET"):
        if path==m.PAGE:
            return 200,'<button id="verify-data-cloud"></button><p id="data-cloud-verify-status"></p>'
        if path==m.JS:
            return 200,'function verifyDataCloudExchange(){}; "/v1/data/auth/exchange"'
        return {
            "/health":(200,"ok"),
            m.EXCHANGE:(401,"") if method=="POST" else (405,""),
            m.LOGIN:(405,""),
            "/v1/revenue-crm/journeys/blueprint":(401,""),
        }.get(path,(404,""))
    monkeypatch.setattr(m,"fetch",fetch)
    class Reply:
        status_code=401
    class Client:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url):return Reply()
    import httpx
    monkeypatch.setattr(httpx,"Client",Client)
    m.verify_live(after_restart=False)


def test_readback_fails_if_data_exchange_unprotected(monkeypatch):
    monkeypatch.setattr(m,"fetch",lambda path,method="GET":(
        (200,"<button id=\"verify-data-cloud\"></button><p id=\"data-cloud-verify-status\"></p>")
        if path==m.PAGE else
        (200,'function verifyDataCloudExchange(){}; "/v1/data/auth/exchange"')
        if path==m.JS else
        (200,"badly exposed") if path==m.EXCHANGE else
        (200,"ok")
    ))
    with pytest.raises(RuntimeError,match="original_private_issuer_exchange_auth_regressed"):
        m.verify_live(after_restart=False)


def test_resume_is_scoped_to_exact_failed_ui_frozen_patch():
    s=SRC.read_text()
    assert 'OLD_PATCH_SHA="fdb6fb78b41079df8fa9e7eaee2fef03ba0c4ef6436575787f50e7eb8a5f1721"' in s
    assert 'ORIGINAL_ENTRYPOINT_SHA="52f0cee04a7236426053eb38273e920a398bd87257cb4f0bb0ac1b0156f19624"' in s
    assert 'PATCH_BACKUP=Path("/etc/empire-data-cloud-founder-20261107/verify-ui-patch-before-lazy-router-fix.py")' in s
    assert 'def preflight(*, resuming:bool=False)' in s
    assert 'def repair_exact_original_staged_patch():' in s
    assert 'if resuming:' in s
    assert 'repair_exact_original_staged_patch()' in s
    assert 'mode=0o444' not in s or 'atomic_install(RELEASE/name,(SRC/name).read_bytes(),0o444)' in s
    assert '--resume-preflight-read-only' in s
    assert '--resume-founder-approved' in s


def test_resume_rejects_unknown_old_image_without_any_mutation(monkeypatch,tmp_path):
    stage=tmp_path/"release"
    stage.mkdir()
    (stage/m.SOURCES[1]).write_bytes(b"unexpected foreign code")
    monkeypatch.setattr(m,"RELEASE",stage)
    monkeypatch.setattr(m,"PATCH_BACKUP",tmp_path/"root_only"/"original.py")
    with pytest.raises(RuntimeError,match="original_ui_patch_preimage_not_recognised"):
        m.repair_exact_original_staged_patch()
    assert (stage/m.SOURCES[1]).read_bytes()==b"unexpected foreign code"


def test_resume_preflight_requires_exact_failed_release_inventory(monkeypatch,tmp_path):
    # Fail-closed when original approved review source is not in place.
    monkeypatch.setattr(m,"ROOT",tmp_path/"absent")
    monkeypatch.setattr(m.os,"geteuid",lambda:0)
    with pytest.raises(RuntimeError,match="current_review_branch_missing"):
        m.preflight(resuming=True)


def test_rollback_waits_for_original_private_service_after_delayed_restart(monkeypatch,tmp_path):
    overlay=tmp_path/"verify-ui.conf"
    overlay.write_bytes(b"known staged version")
    monkeypatch.setattr(m,"OVERLAY",overlay)
    calls=[]
    states=iter([0,0,200])
    def fake_fetch(path,method="GET"):
        return next(states,200),""
    def fake_run(args):
        calls.append(tuple(args))
        return m.EXISTING_ENTRYPOINT if "ExecStart" in args else ""
    monkeypatch.setattr(m,"fetch",fake_fetch)
    monkeypatch.setattr(m,"run",fake_run)
    monkeypatch.setattr(m.time,"sleep",lambda t:None)
    assert m.rollback_only_additive_overlay(m.sha(b"known staged version")) is True
    assert not overlay.exists()
    assert ("systemctl","restart",m.SERVICE) in calls


def test_live_real_app_lazy_router_detection_is_explicit():
    p=(ROOT/"scripts/data_cloud_verify_ui_patch_20261108.py").read_text()
    assert '"fastapi.routing", "_IncludedRouter"' in p
    assert 'getattr(outer, "original_router", None)' in p
    assert 'original_routes.extend(leaves)' in p
    assert "app.router.routes.insert(0" in p
    assert "original_lazy_crm_router_contract_changed" in p
