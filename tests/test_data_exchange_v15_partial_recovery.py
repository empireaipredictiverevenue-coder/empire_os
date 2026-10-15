"""One-shot partial deployment recovery: narrow permission and fail-close."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import recover_data_exchange_v15_partial as recovery


def test_default_and_unprivileged_never_write(capsys,monkeypatch):
    monkeypatch.setattr(recovery.os,"geteuid",lambda:1000)
    monkeypatch.setattr(recovery,"precheck",lambda: (_ for _ in ()).throw(AssertionError("no precheck")))
    assert recovery.main([])==2
    assert json.loads(capsys.readouterr().out)["reason_code"]=="EXPLICIT_EXISTING_FOUNDER_RELEASE_SCOPE_REQUIRED"
    assert recovery.main(["--apply",recovery.dep.APPROVAL])==2
    report=json.loads(capsys.readouterr().out)
    assert report["reason_code"]=="AUTHORISED_ROOT_REQUIRED"
    assert report["database_writes"] is False


def test_connect_grant_restricts_database_and_target_role(monkeypatch):
    commands=[]
    monkeypatch.setattr(recovery.dep,"postgresql",
                        lambda *,stdin_sql,silent: commands.append(stdin_sql))
    recovery.grant_login_connect_once()
    assert len(commands)==1
    sql=commands[0]
    assert sql.startswith("\nBEGIN;")
    assert "GRANT CONNECT ON DATABASE empiredb TO empire_data_exchange_custody_login;" in sql
    assert "GRANT CONNECT ON DATABASE empiredb TO PUBLIC" not in sql
    assert "ALTER ROLE" not in sql
    assert "ALTER SYSTEM" not in sql
    assert "pg_hba" not in sql
    assert "DELETE " not in sql
    assert sql.rstrip().endswith("COMMIT;")


def test_wrong_production_state_fails_without_grant(monkeypatch):
    monkeypatch.setattr(recovery.inspect,"inspect",lambda:{
       "production_state":"NO_V15_SCHEMA_OR_SERVICE_OBSERVED",
       "canonical_db_identity_verified":True})
    with pytest.raises(recovery.RecoveryHold,match="PREEXISTING_SCHEMA"):
        recovery.precheck()


def _fake_precheck(tmp_path, has_connect):
    backup=tmp_path/"backup"
    backup.mkdir()
    return {
        "custody_login_database_connect":has_connect,
        "backup_reference":backup,
    }


def _allow_root_operator(monkeypatch,tmp_path):
    monkeypatch.setattr(recovery.os,"geteuid",lambda:0)
    monkeypatch.setattr(recovery.dep,"ROOT",Path.cwd())
    monkeypatch.setattr(recovery,"LOCK",tmp_path/"lock")


def test_no_hba_workaround_or_service_start_after_auth_failure(monkeypatch,tmp_path,capsys):
    _allow_root_operator(monkeypatch,tmp_path)
    monkeypatch.setattr(recovery,"precheck",lambda:_fake_precheck(tmp_path,False))
    writes=[]
    monkeypatch.setattr(recovery,"grant_login_connect_once",lambda:writes.append("grant"))
    monkeypatch.setattr(recovery.inspect,"_probe_dedicated_connection",
                        lambda:{"dedicated_login_connection_status":"LOGIN_HBA_NO_MATCH"})
    monkeypatch.setattr(recovery.subprocess,"run",
        lambda *a,**k:(_ for _ in ()).throw(AssertionError("no service start")))
    assert recovery.main(["--apply",recovery.dep.APPROVAL])==2
    obj=json.loads(capsys.readouterr().out)
    assert obj["reason_code"]=="DEDICATED_LOGIN_AUTH_ROUTE_NOT_READY_NO_CAPTURE_ATTEMPT"
    assert obj["dedicated_login_status"]=="LOGIN_HBA_NO_MATCH"
    assert obj["hba_changes"] is False
    assert obj["database_writes"] is True
    assert obj["failed_phase"]=="VERIFY_DEDICATED_AUTH_AND_RLS_READ"
    assert writes==["grant"]


def test_successful_one_shot_capture_and_readback_only_once(monkeypatch,tmp_path,capsys):
    _allow_root_operator(monkeypatch,tmp_path)
    monkeypatch.setattr(recovery,"precheck",lambda:_fake_precheck(tmp_path,False))
    grants=[]
    monkeypatch.setattr(recovery,"grant_login_connect_once",lambda:grants.append("connect_only"))
    monkeypatch.setattr(recovery.inspect,"_probe_dedicated_connection",
                        lambda:{"dedicated_login_connection_status":"AUTHENTICATED_READ_ONLY",
                                "dedicated_login_row_count":0})
    monkeypatch.setattr(recovery.inspect,"protected_dsn",lambda:"opaque-fixture-only")
    starts=[]
    monkeypatch.setattr(recovery.subprocess,"run",
         lambda args,**kw:(starts.append(args),SimpleNamespace(returncode=0))[1])
    class FakeStore:
        def __init__(self,dsn):
            assert dsn=="opaque-fixture-only"
        def read_window(self):
            return [{"sequence":0,"chain_sha256":"f"*64,
                     "snapshot_json":{"records":[1,2,3]}}]
    monkeypatch.setattr(recovery,"EmpireDBConstructionCustody",FakeStore)
    monkeypatch.setattr(recovery,"verify_custody_window",
                        lambda rows:{"head_chain_sha256":"f"*64})
    assert recovery.main(["--apply",recovery.dep.APPROVAL])==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="PRODUCTION_OBSERVE_CUSTODY_ACTIVE"
    assert result["canonical_rows"]==1
    assert result["customer_delivery_enabled"] is False
    assert result["timer_installed"] is False
    assert starts==[["systemctl","start","empire-data-exchange-custody-capture.service"]]
    assert grants==["connect_only"]
    saved=(tmp_path/"backup"/"v15-production-recovery-receipt.json")
    assert saved.exists()
    assert json.loads(saved.read_text())["canonical_rows"]==1


def test_existing_connect_doesnt_generate_second_grant(monkeypatch,tmp_path,capsys):
    _allow_root_operator(monkeypatch,tmp_path)
    monkeypatch.setattr(recovery,"precheck",lambda:_fake_precheck(tmp_path,True))
    monkeypatch.setattr(recovery,"grant_login_connect_once",
                        lambda:(_ for _ in ()).throw(AssertionError("no grant")))
    monkeypatch.setattr(recovery.inspect,"_probe_dedicated_connection",
                        lambda:{"dedicated_login_connection_status":"LOGIN_PASSWORD_AUTH_FAILED"})
    assert recovery.main(["--apply",recovery.dep.APPROVAL])==2
    report=json.loads(capsys.readouterr().out)
    assert report["database_writes"] is False
    assert report["password_rotation"] is False
    assert report["dedicated_login_status"]=="LOGIN_PASSWORD_AUTH_FAILED"
