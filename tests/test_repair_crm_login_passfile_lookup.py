"""Committed three-role CRM passfile recovery: exact, nonsecret operations."""
from __future__ import annotations
import importlib.util
import stat
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/repair_crm_login_passfile_lookup.py"
spec=importlib.util.spec_from_file_location("crm_pgpass_recovery",SCRIPT)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def original():
    return "".join(
        f"{m.SOCKET}:5432:empiredb:{role}:synthetic-only-long-credential-123456789\n"
        for role in m.ROLES
    ).encode()

def isolated(monkeypatch,tmp_path):
    root=tmp_path/"private-vault"
    root.mkdir(mode=0o700)
    src=root/"pgpass"
    src.write_bytes(original())
    src.chmod(0o600)
    monkeypatch.setattr(m,"DIR",root)
    monkeypatch.setattr(m,"PASSFILE",src)
    monkeypatch.setattr(m,"BACKUP",root/".pgpass.before-localhost-repair")
    monkeypatch.setattr(m,"LOCK",root/".pgpass-repair.lock")
    return root,src

def test_exact_orig_to_both_hosts_preserves_password_bytes():
    o=original()
    assert m.inspect(o)=="ORIGINAL_THREE_ROWS"
    updated=m.patched(o)
    assert m.inspect(updated)=="REPAIRED_SIX_ROWS"
    assert updated.startswith(o)
    assert len(updated.splitlines())==6
    assert updated.count(b"localhost:5432:empiredb:")==3
    assert updated.count(m.SOCKET.encode()+b":5432:empiredb:")==3
    assert o.splitlines()[0].split(b":",4)[4] in updated
    with pytest.raises(ValueError):
        m.patched(updated)

def test_corrupt_unknown_or_duplicate_passfiles_blocked():
    o=original()
    for v in (b"",o.replace(b"empiredb",b"otherdb",1),
              o.replace(b"\n",b"\r\n",1),
              o.replace(b"\n",b"\n"+o.splitlines()[0]+b"\n",1),
              o.replace(b"synthetic-only-long-credential-123456789",b"short",1),
              o.replace(b":5432:",b":5433:",1),o[:-1]):
        assert m.inspect(v)=="INVALID"

def test_end_to_end_metadata_only_repair_and_idempotence(tmp_path,monkeypatch,capsys):
    root,src=isolated(monkeypatch,tmp_path)
    monkeypatch.setattr(m,"_reviewed_source",lambda:True)
    monkeypatch.setattr(m,"_verify",lambda:True)
    monkeypatch.setattr(m.sys,"argv",["program","--apply","--approved-passfile-lookup-only"])
    assert m.main()==0
    result=capsys.readouterr().out
    assert "THREE_LOGINS_AND_TENANT_PROOF_VERIFIED" in result
    assert "synthetic-only" not in result
    assert m.inspect(src.read_bytes())=="REPAIRED_SIX_ROWS"
    assert m.BACKUP.read_bytes()==original()
    assert stat.S_IMODE(src.stat().st_mode)==0o600
    assert stat.S_IMODE(m.BACKUP.stat().st_mode)==0o600
    assert m.main()==0
    assert "ALREADY_REPAIRED_NO_CHANGES" in capsys.readouterr().out

def test_login_proof_failure_restores_original(tmp_path,monkeypatch,capsys):
    root,src=isolated(monkeypatch,tmp_path)
    monkeypatch.setattr(m,"_reviewed_source",lambda:True)
    monkeypatch.setattr(m,"_verify",lambda:False)
    monkeypatch.setattr(m.sys,"argv",["program","--apply","--approved-passfile-lookup-only"])
    assert m.main()==4
    assert src.read_bytes()==original()
    out=capsys.readouterr().out
    assert "ROLLBACK=ORIGINAL_RESTORED" in out
    assert "BLOCKED_OR_UNVERIFIED" in out

def test_preflight_does_not_edit_file(tmp_path,monkeypatch,capsys):
    _,src=isolated(monkeypatch,tmp_path)
    monkeypatch.setattr(m.sys,"argv",["program","--preflight"])
    assert m.main()==0
    assert src.read_bytes()==original()
    assert "PREFLIGHT_NO_CHANGES" in capsys.readouterr().out

def test_psql_principal_and_tenant_guard(monkeypatch):
    calls=[]
    def good(role,sql):
        calls.append((role,sql))
        if "empire_current_tenant_id()" in sql:
            return 0,m.TENANT
        if "empire_tenant_role_bindings" in sql:
            return 1,""
        return 0,role
    monkeypatch.setattr(m,"_psql",good)
    assert m._verify() is True
    assert len(calls)==5
    assert "BEGIN READ ONLY" in calls[0][1]
    monkeypatch.setattr(m,"_psql",lambda role,sql:(0,role))
    assert m._verify() is False

def test_security_controls_static():
    s=SCRIPT.read_text()
    assert "O_NOFOLLOW" in s
    assert "os.O_EXCL" in s
    assert "os.replace(" in s
    assert "0o600" in s
    assert "0o700" in s
    assert "fcntl.flock" in s
    assert "PGPASSFILE" in s
    assert "env.pop(\"PGPASSWORD\", None)" in s
    assert "capture_output=True" in s
    assert "--approved-passfile-lookup-only" in s
    assert "git(\"hash-object\"" in s
    assert "ALTER ROLE" not in s and "CREATE ROLE" not in s
    assert "INSERT INTO" not in s and "UPDATE " not in s
    assert "pg_reload_conf(" not in s
