"""Zero-write failure diagnostics for direct BSC buyer status release."""
from pathlib import Path
import json

import pytest

from scripts import diagnose_direct_bsc_status_failed_release_readonly as diag


def test_no_apply_no_retry_flag(capsys,monkeypatch):
    monkeypatch.setattr(diag,"diagnose",lambda:pytest.fail("would access secrets"))
    for args in ([],["--apply"],["--read-only","--apply"]):
        assert diag.main(args)==3
    assert "HELD_EXACT_READONLY_FLAG_REQUIRED" in capsys.readouterr().out


def test_root_only_readback(monkeypatch):
    monkeypatch.setattr(diag.os,"geteuid",lambda:1000)
    with pytest.raises(ValueError,match="root"):
        diag.diagnose()


def test_full_diagnostic_redacts_details_and_never_issues(monkeypatch):
    monkeypatch.setattr(diag.os,"geteuid",lambda:0)
    simple={
        "_reviewed":lambda:None,
        "_published_checkout_verified":lambda:None,
        "_verify_unit_targets":lambda:None,
        "_verify_login_file":lambda:None,
        "checkout_financial_execution_held":lambda:None,
        "_snapshot":lambda:("online","direct",True,True,False,False),
        "_chain_verified":lambda:{"chain_verified":True},
    }
    for name,fn in simple.items():
        monkeypatch.setattr(diag.release,name,fn)
    monkeypatch.setattr(diag,"read_key",lambda:b"0"*32)
    monkeypatch.setattr(diag,"_systemd_bsc_env",lambda:{
      "BSC_RPC_URL":"https://private-upstream.example",
      "BSC_TREASURY_ADDRESS":"0x"+"a"*40,
    })
    monkeypatch.setattr(diag.checkout,"_config",
                        lambda:("reader-dsn", "issuer-dsn",b"0"*32,"0x"+"a"*40))
    monkeypatch.setattr(diag.checkout,"_chain_verified",lambda:True)
    observed=[]
    class Reader:
        def __init__(self,dsn):observed.append("reader")
        def __call__(self,digest):
            assert digest=="0"*64
            return None
    monkeypatch.setattr(diag,"PrivateBuyerStatusPostgresReader",Reader)
    class FakeResponse:
        status_code=404
        def json(self):return {"error":"payment_status_unavailable"}
    class Client:
        def __init__(self,app):pass
        def post(self,*a,**kw):
            assert kw["json"]["token"].startswith("ecs1_")
            return FakeResponse()
    monkeypatch.setattr(diag,"create_staged_private_status_app",lambda **k:object())
    monkeypatch.setattr(diag,"TestClient",Client)
    state=diag.diagnose()
    assert set(state["stages"].values())=={"PASS"}
    assert state["secrets_disclosed"] is False
    assert state["service_changes"] is False
    assert state["key_rotated"] is False
    assert "private-upstream" not in str(state)
    assert observed==["reader"]


def test_any_failure_is_redacted_and_heard_without_side_effects(monkeypatch):
    monkeypatch.setattr(diag.os,"geteuid",lambda:0)
    monkeypatch.setattr(diag.release,"_reviewed",
        lambda:(_ for _ in ()).throw(RuntimeError("secret=private")))
    for key in ("_published_checkout_verified","_verify_unit_targets",
                "_verify_login_file","checkout_financial_execution_held",
                "_snapshot","_chain_verified"):
        monkeypatch.setattr(diag.release,key,lambda:None)
    monkeypatch.setattr(diag,"read_key",lambda:None)
    monkeypatch.setattr(diag,"_systemd_bsc_env",lambda:{})
    state=diag.diagnose()
    assert state["stages"]["committed_sources"]=="HELD_RuntimeError"
    assert "secret=private" not in str(state)
    assert state["secrets_disclosed"] is False
    assert state["service_changes"] is False




def test_bsc_settings_are_from_active_root_owned_dropin_not_env_files(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import subprocess
    original=Path.stat
    p=tmp_path/"30-direct-bsc-readonly.conf"
    p.write_text(
        "[Service]\n"
        "# staged direct checkout baseline\n"
        'Environment="BSC_RPC_URL=https://bsc-dataseed.bnbchain.org"\n'
        'Environment="BSC_TREASURY_ADDRESS=0x1339b487046B0ad924a10c20b1791608EA8595a8"\n'
        'Environment="BSC_MIN_CONFIRMATIONS=12"\n'
        "Environment=EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF\n"
    )
    p.chmod(0o644)
    monkeypatch.setattr(diag,"BSC_DROPIN",p)
    def safe_stat(self,*a,**k):
        result=original(self,*a,**k)
        if self==p:return SimpleNamespace(st_uid=0,st_mode=result.st_mode)
        return result
    monkeypatch.setattr(Path,"stat",safe_stat)
    class Result:
        returncode=0
        stdout=str(p)+"\n"
    monkeypatch.setattr(subprocess,"run",lambda *a,**k:Result())
    data=diag._systemd_bsc_env()
    assert data["BSC_MIN_CONFIRMATIONS"]=="12"
    assert data["BSC_TREASURY_ADDRESS"].startswith("0x1339")
    assert set(data)=={
        "BSC_RPC_URL","BSC_TREASURY_ADDRESS","BSC_MIN_CONFIRMATIONS"
    }
    p.write_text(p.read_text()+"Environment=BSC_MIN_CONFIRMATIONS=9\n")
    with pytest.raises(ValueError,match="duplicate"):
        diag._systemd_bsc_env()
    p.write_text("[Service]\nEnvironment=BSC_MIN_CONFIRMATIONS=12\n")
    with pytest.raises(ValueError,match="missing"):
        diag._systemd_bsc_env()
    p.unlink()
    p.symlink_to(tmp_path/"elsewhere")
    with pytest.raises(ValueError):
        diag._systemd_bsc_env()


def test_inactive_or_changed_systemd_dropin_fail_closed(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import subprocess
    p=tmp_path/"30-direct-bsc-readonly.conf"
    p.write_text('[Service]\nEnvironment="BSC_RPC_URL=https://rpc.example"\n'
                 'Environment="BSC_TREASURY_ADDRESS=0x1339b487046B0ad924a10c20b1791608EA8595a8"\n'
                 'Environment="BSC_MIN_CONFIRMATIONS=12"\n')
    monkeypatch.setattr(diag,"BSC_DROPIN",p)
    original=Path.stat
    def root_stat(self,*a,**k):
        result=original(self,*a,**k)
        if self==p:return SimpleNamespace(st_uid=0,st_mode=result.st_mode)
        return result
    monkeypatch.setattr(Path,"stat",root_stat)
    class R:
        returncode=0
        stdout="/etc/systemd/system/other.conf\n"
    monkeypatch.setattr(subprocess,"run",lambda *a,**k:R())
    with pytest.raises(ValueError,match="not the active"):
        diag._systemd_bsc_env()

def test_code_contains_no_write_or_restart_or_mail_paths():
    text=Path(diag.__file__).read_text()
    for forbidden in ("systemctl restart","CREATE ROLE ",
                      "UPDATE public.","INSERT INTO public.",
                      "write_bytes(", "write_text(","install_key(",
                      "issue_direct_bsc_buyer_status(",
                      "smtp.send","send_message("):
        assert forbidden not in text
    assert "READ_ONLY" in text
    assert "_status_probe" not in text
