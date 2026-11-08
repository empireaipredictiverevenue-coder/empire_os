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
    monkeypatch.setattr(m,"run",lambda args:called.append(tuple(args)) or "")
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
