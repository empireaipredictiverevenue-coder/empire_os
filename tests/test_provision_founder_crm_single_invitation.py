"""One-time CRM invitation release protections."""
from pathlib import Path
import importlib.util
import json
import stat
import pytest

SRC=Path(__file__).resolve().parents[1]/"scripts/provision_founder_crm_single_invitation.py"
spec=importlib.util.spec_from_file_location("founder_single_invitation",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_canonical_founder_scope():
    assert m.SUBJECT=="founder:phil_livesley"
    assert m.EMAIL=="flavag83@gmail.com"
    assert m.TENANT=="708efd4b-53b2-43d7-961d-1cecab67f17a"
    assert m.FOUNDER_PROOF.startswith("founder:")
    assert m.RECIPIENT_PROOF.startswith("verified-email:")

def test_invitation_packet_and_private_file(tmp_path,monkeypatch):
    parent=tmp_path/"private"
    parent.mkdir(mode=0o700)
    monkeypatch.setattr(m,"STORE",parent)
    monkeypatch.setattr(m,"INVITE_DIR",parent/"founder_invitation")
    monkeypatch.setattr(m,"TOKEN_FILE",parent/"founder_invitation"/"pending_invitation.json")
    packet=m.prepare_crm_invitation(subject=m.SUBJECT,email=m.EMAIL,
              tenant_id=m.TENANT,evidence_ref=m.IDENTITY_PROOF)
    assert packet.token not in repr(packet)
    assert len(packet.invitation_token_hash)==32
    m._store_token(packet)
    stored=json.loads(m.TOKEN_FILE.read_text())
    assert stored["status"]=="PENDING_NOT_SENT"
    assert stored["token"]==packet.token
    assert stat.S_IMODE(m.TOKEN_FILE.stat().st_mode)==0o600
    assert stat.S_IMODE(m.INVITE_DIR.stat().st_mode)==0o700
    with pytest.raises(FileExistsError):
        m._store_token(packet)

def test_existing_operator_and_safety_contract():
    src=SRC.read_text()
    assert "PostgresCrmInviteOperator(DB_DSN)" in src
    assert "prepare_crm_invitation(" in src
    assert "fcntl.flock" in src
    assert "SET TRANSACTION READ ONLY" in src
    assert "os.O_EXCL" in src
    assert "PENDING_NOT_SENT" in src
    assert "_release_guard()" in src
    assert "print(packet.token)" not in src
    assert "send_email" not in src
    assert "ALTER ROLE" not in src
    assert "CREATE TABLE" not in src


def test_single_invite_operator_forwards_canonical_scope(monkeypatch):
    invited=m.prepare_crm_invitation(subject=m.SUBJECT,email=m.EMAIL,
          tenant_id=m.TENANT,evidence_ref=m.IDENTITY_PROOF)
    calls=[]
    class FakeOperator:
        def __init__(self,dsn):
            assert dsn==m.DB_DSN
        def provision(self,invitation,**evidence):
            calls.append((invitation,evidence))
            return True
    monkeypatch.setattr(m,"PostgresCrmInviteOperator",FakeOperator)
    monkeypatch.setattr(m,"_catalog",lambda **kwargs:{"status":"READY"})
    assert m._insert_once(m._payload(invited))=={"status":"ONE_PENDING_ACCOUNT_INSERTED"}
    assert len(calls)==1
    assert calls[0][1]=={
      "founder_approval_ref":m.FOUNDER_PROOF,
      "verified_recipient_ref":m.RECIPIENT_PROOF,
    }
    bad=m._payload(invited)
    bad["email"]="not-the-approved-recipient@example.invalid"
    with pytest.raises(RuntimeError):
        m._insert_once(bad)
