"""Founder CRM private runtime staging: exact tenant, safe files, no activation."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import json
import os
import stat
from datetime import datetime, timezone, timedelta

S=Path(__file__).resolve().parents[1]/"scripts/stage_founder_crm_pilot_private.py"
spec=importlib.util.spec_from_file_location("crm_stage_private",S)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def _isolate(tmp_path,monkeypatch):
    p=tmp_path/"crm"
    p.mkdir(mode=0o700)
    monkeypatch.setattr(m,"ROOT",p)
    monkeypatch.setattr(m,"KEY",p/"pilot-signing.pem")
    monkeypatch.setattr(m,"CONFIG",p/"pilot-runtime.json")
    monkeypatch.setattr(m,"ENV",p/"pilot-staged.env")
    monkeypatch.setattr(m,"PASSFILE",p/"pgpass")
    monkeypatch.setattr(m,"PENDING",p/"founder_invitation"/"pending_invitation.json")
    m.PASSFILE.write_text("synthetic-only-secret-not-production")
    m.PASSFILE.chmod(0o600)
    m.PENDING.parent.mkdir(mode=0o700)
    token="EI1_"+"A"*43
    m.PENDING.write_text(json.dumps({
        "schema":"empire.crm.founder_invitation_server_secret.v1",
        "status":"PENDING_NOT_SENT",
        "login_email":"flavag83@gmail.com",
        "subject":"founder:phil_livesley",
        "tenant_id":m.TENANT,
        "token":token,
        "expires_at_utc":(datetime.now(timezone.utc)+timedelta(hours=30)).isoformat()
    }))
    m.PENDING.chmod(0o600)
    return p


def test_private_staging_creates_single_exact_scope(tmp_path,monkeypatch):
    _isolate(tmp_path,monkeypatch)
    assert m.prerequisites()=="READY"
    m.stage()
    assert m.prerequisites()=="ALREADY_STAGED"
    for f in (m.KEY,m.CONFIG,m.ENV):
        assert stat.S_IMODE(f.stat().st_mode)==0o600
    cfg=json.loads(m.CONFIG.read_text())
    assert cfg["tenant_dsns"]=={
        m.TENANT:"host=/var/run/postgresql port=5432 dbname=empiredb user=empire_crm_tenant_708efd4b53b2"
    }
    assert "password" not in m.CONFIG.read_text().lower()
    assert "PGPASSFILE="+str(m.PASSFILE) in m.ENV.read_text()
    assert "PENDING_NOT_SENT" in m.PENDING.read_text()


def test_existing_staging_mismatch_refused(tmp_path,monkeypatch):
    _isolate(tmp_path,monkeypatch)
    m.stage()
    raw=json.loads(m.CONFIG.read_text())
    raw["tenant_dsns"]={}
    m.CONFIG.write_text(json.dumps(raw))
    assert m.prerequisites()=="BLOCKED_STAGED_CONTENT_MISMATCH"


def test_expired_invite_denied(tmp_path,monkeypatch):
    _isolate(tmp_path,monkeypatch)
    data=json.loads(m.PENDING.read_text())
    data["expires_at_utc"]=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    m.PENDING.write_text(json.dumps(data))
    assert m.prerequisites()=="BLOCKED_INVITATION_NOT_CURRENT"


def test_privilege_scope_static():
    s=S.read_text()
    assert "os.O_EXCL" in s
    assert "NoNewPrivileges" not in s
    assert "offline_check()" in s
    assert "Ed25519PrivateKey.generate()" in s
    assert "os.fchmod(output.fileno(),0o600)" in s
    assert "SET TRANSACTION" not in s
    assert "ALTER ROLE" not in s
    assert "CREATE ROLE" not in s
    assert "send_email" not in s
    assert "systemctl" not in s
    assert "uvicorn" not in s
