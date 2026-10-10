"""Passive TAM catalog proof from the existing protected Market GPS unit."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path

import pytest

from empire_os.revenue_completion_supervisor import (
    tam_reader_prerequisites, tam_restricted_reader_catalog_status,
)


def wrapper():
    path=Path(__file__).resolve().parents[1]/"scripts/run_market_gps_credentialed.py"
    spec=importlib.util.spec_from_file_location("tam_gps_wrapper_test",path)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def safe_proof(**changes):
    x={
        "schema_version":"empire.tam_restricted_reader_capability_preflight.v1",
        "source":"existing_market_gps_protected_systemd_credential",
        "mode":"OBSERVE","observed_at":datetime.now(timezone.utc).isoformat(),
        "status":"PASS","migration_028_contract_verified":True,
        "restricted_login_verified":True,"capability_role_verified":True,
        "function_exists":True,"security_definer_verified":True,
        "capability_execute_verified":True,"source_tables_present":True,
        "source_table_direct_read_grants":False,"no_data_rows_read":True,
        "no_migration_applied":True,"no_credential_exported":True,
        "execution_authority":"none",
    }
    x.update(changes)
    return x


def test_systemd_gps_attestation_requires_real_unit_context(monkeypatch,tmp_path):
    m=wrapper()
    monkeypatch.setenv("INVOCATION_ID","f"*32)
    assert not m._real_protected_market_gps_execution(str(tmp_path))
    assert m._real_protected_market_gps_execution(
        "/run/credentials/empire-market-gps.service"
    )
    assert not m._real_protected_market_gps_execution(None)
    monkeypatch.delenv("INVOCATION_ID",raising=False)
    assert not m._real_protected_market_gps_execution(
        "/run/credentials/empire-market-gps.service"
    )


def test_passive_probe_response_is_safe_whitelist_and_no_password(monkeypatch):
    m=wrapper()
    from empire_os import tam_market_runtime
    def mock_probe(dsn):
        assert "private-password" in dsn
        return {
            "status":"PASS","migration_028_contract_verified":True,
            "restricted_login_verified":True,"capability_role_verified":True,
            "function_exists":True,"security_definer_verified":True,
            "capability_execute_verified":True,"source_tables_present":True,
            "source_table_direct_read_grants":False,
            "password":"private-password","query_results":["private-record"],
        }
    monkeypatch.setattr(tam_market_runtime,"probe_tam_reader_capability",mock_probe)
    output=m._safe_probe_tam_catalog("private-password")
    assert output["migration_028_contract_verified"] is True
    assert output["no_data_rows_read"] is True
    assert output["no_migration_applied"] is True
    assert "password" not in str(output)
    assert "private-record" not in str(output)


def test_passive_probe_missing_grants_cannot_report_success(monkeypatch):
    m=wrapper()
    from empire_os import tam_market_runtime
    def mock_probe(_):
        return {"status":"PASS","migration_028_contract_verified":True,
                "restricted_login_verified":True,"capability_role_verified":True,
                "function_exists":True,"security_definer_verified":True,
                "capability_execute_verified":True,"source_tables_present":True,
                "source_table_direct_read_grants":True}
    monkeypatch.setattr(tam_market_runtime,"probe_tam_reader_capability",mock_probe)
    output=m._safe_probe_tam_catalog("any-string")
    assert output["migration_028_contract_verified"] is False
    assert output["source_table_direct_read_grants"] is True


def test_probe_failure_is_nonfatal_and_redacted(monkeypatch):
    m=wrapper()
    from empire_os import tam_market_runtime
    def fail(_):
        raise RuntimeError("secret-password")
    monkeypatch.setattr(tam_market_runtime,"probe_tam_reader_capability",fail)
    x=m._safe_probe_tam_catalog("secret-password")
    assert x["status"]=="RESTRICTED_CATALOG_PROBE_UNAVAILABLE"
    assert not x["migration_028_contract_verified"]
    assert "secret" not in str(x)


def test_private_atomic_catalog_artifact_and_supervisor_readback(tmp_path,monkeypatch):
    m=wrapper()
    output=tmp_path/"reader.json"
    monkeypatch.setattr(m,"TAM_PROBE_PATH",output)
    proof=safe_proof()
    m._persist_tam_probe(proof)
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(output.read_text())==proof
    state=tam_restricted_reader_catalog_status(output)
    assert state["restricted_catalog_verified"] is True
    assert state["fresh"] is True
    ready=tam_reader_prerequisites({},catalog_probe_path=output)
    assert ready["restricted_empiredb_sql_reader_live_verified"] is True
    assert ready["runtime_environment_configured"] is False
    assert not ready["auto_planner_retry_authorized"]
    assert not ready["service_restart_authorized"]
    assert "NO_DDL_AUTHORITY" in ready["migration_028_live_authority"]
    assert "password" not in str(ready)


@pytest.mark.parametrize("change",[
    {"status":"PASS","capability_execute_verified":False},
    {"status":"PASS","source_tables_present":False},
    {"status":"PASS","source_table_direct_read_grants":True},
    {"status":"RESTRICTED_CATALOG_PROBE_UNAVAILABLE"},
    {"source":"fake_operator"},
    {"no_data_rows_read":False},
    {"no_migration_applied":False},
    {"mode":"EXECUTE"},
    {"execution_authority":"write"},
    {"status":{"nested":"malformed"}},
])
def test_invalid_private_preflight_never_promotes_migration_capability(tmp_path,change):
    p=tmp_path/"status.json"
    p.write_text(json.dumps(safe_proof(**change)))
    p.chmod(0o600)
    s=tam_restricted_reader_catalog_status(p)
    assert s["restricted_catalog_verified"] is False
    assert s["execution_authority"]=="none"


def test_stale_future_public_and_symlink_preflight_fail_closed(tmp_path):
    p=tmp_path/"status.json"
    p.write_text(json.dumps(safe_proof(
        observed_at=(datetime.now(timezone.utc)-timedelta(hours=5)).isoformat()
    )))
    p.chmod(0o600)
    assert not tam_restricted_reader_catalog_status(p)["restricted_catalog_verified"]
    p.write_text(json.dumps(safe_proof(
        observed_at=(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat()
    )))
    assert not tam_restricted_reader_catalog_status(p)["restricted_catalog_verified"]
    p.write_text(json.dumps(safe_proof()))
    p.chmod(0o644)
    assert not tam_restricted_reader_catalog_status(p)["restricted_catalog_verified"]
    p.chmod(0o600)
    link=tmp_path/"alias.json"
    link.symlink_to(p)
    assert not tam_restricted_reader_catalog_status(link)["restricted_catalog_verified"]


def test_catalog_output_refuses_symlink(tmp_path,monkeypatch):
    m=wrapper()
    target=tmp_path/"do_not_touch.txt"
    target.write_text("keep")
    out=tmp_path/"linked.json"
    out.symlink_to(target)
    monkeypatch.setattr(m,"TAM_PROBE_PATH",out)
    with pytest.raises(ValueError,match="unsafe TAM preflight"):
        m._persist_tam_probe(safe_proof())
    assert target.read_text()=="keep"


def test_mocked_gps_does_not_create_fake_production_attestation(
    tmp_path,monkeypatch,
):
    m=wrapper()
    from scripts import build_market_sweep_snapshot
    d=tmp_path/"market-gps.dsn"
    d.write_text(
        "postgresql://empire_intelligence_materializer_login:dummy@127.0.0.1/empiredb"
    )
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(tmp_path))
    monkeypatch.setenv("INVOCATION_ID","fake-invocation")
    monkeypatch.setattr(build_market_sweep_snapshot,"main",lambda:0)
    def reject_production_probe(*_):
        raise AssertionError("fake service credential must never issue catalog probe")
    monkeypatch.setattr(m,"_safe_probe_tam_catalog",reject_production_probe)
    assert m.main()==0
    assert not (tmp_path/"tam_reader_capability_latest.json").exists()


def test_real_unit_probe_failure_does_not_change_market_gps_success(
    tmp_path, monkeypatch, capsys,
):
    m=wrapper()
    from scripts import build_market_sweep_snapshot
    credential=tmp_path/"market-gps.dsn"
    credential.write_text(
        "postgresql://empire_intelligence_materializer_login:fake-secret@127.0.0.1/empiredb"
    )
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(tmp_path))
    monkeypatch.setattr(build_market_sweep_snapshot,"main",lambda:0)
    monkeypatch.setattr(m,"_real_protected_market_gps_execution",lambda _:True)
    def fail(_):
        raise RuntimeError("private secret must not leak")
    monkeypatch.setattr(m,"_safe_probe_tam_catalog",fail)
    assert m.main()==0
    output=capsys.readouterr().out
    assert "private secret" not in output
    assert "NONBLOCKING_PROBE_NOT_PERSISTED" in output


def test_failed_market_gps_never_requests_tam_probe(
    tmp_path,monkeypatch,
):
    m=wrapper()
    from scripts import build_market_sweep_snapshot
    (tmp_path/"market-gps.dsn").write_text(
        "postgresql://empire_intelligence_materializer_login:test@127.0.0.1/empiredb"
    )
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(tmp_path))
    monkeypatch.setattr(build_market_sweep_snapshot,"main",lambda:4)
    monkeypatch.setattr(m,"_real_protected_market_gps_execution",lambda _:True)
    monkeypatch.setattr(m,"_safe_probe_tam_catalog",
                        lambda _: (_ for _ in ()).throw(
                            AssertionError("must not probe if GPS failed")
                        ))
    assert m.main()==4
