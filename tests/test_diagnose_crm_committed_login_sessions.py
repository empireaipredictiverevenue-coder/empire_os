"""Production read-only CRM session diagnostic contract."""
from pathlib import Path
import importlib.util

PATH=Path(__file__).resolve().parents[1]/"scripts/diagnose_crm_committed_login_sessions.py"
spec=importlib.util.spec_from_file_location("crm_diag",PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_classifies_errors_without_leaking_details():
    assert m.classify("fe_sendauth: no password supplied")=="PASSWORD_LOOKUP_MISSING"
    assert m.classify("password authentication failed for user abc")=="PASSWORD_REJECTED"
    assert m.classify("role abc is not permitted to log in")=="ROLE_NOT_LOGIN"
    assert m.classify("permission denied for database empiredb")=="DATABASE_CONNECT_DENIED"
    assert m.classify("permission denied for table abc")=="TABLE_PRIVILEGE_DENIED"
    assert m.classify("permission denied for schema public")=="SCHEMA_USAGE_DENIED"
    assert m.classify("some secret possibly present")=="UNCLASSIFIED_DATABASE_ERROR"

def test_exact_read_only_session_checks(monkeypatch,tmp_path):
    calls=[]
    def fake(role,statement,path):
        calls.append((role,statement))
        if "empire_current_tenant_id()" in statement:
            return 0,m.TENANT,""
        if "empire_tenant_role_bindings" in statement:
            return 1,"","TABLE_PRIVILEGE_DENIED"
        return 0,role,""
    monkeypatch.setattr(m,"psql",fake)
    status=m.report(tmp_path/"dummy")
    assert len(calls)==5
    assert all(v=="PASS" for v in status.values())
    assert all("BEGIN READ ONLY" in query for _,query in calls)

def test_bad_reader_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setattr(m,"psql",lambda *args:(1,"","PASSWORD_REJECTED"))
    state=m.report(tmp_path/"dummy")
    assert state[m.ROLES[2]]=="PASSWORD_REJECTED"
    assert state["founder_tenant"]=="BLOCKED_ON_READER_LOGIN"

def test_source_restricted_to_temporary_file_and_queries():
    source=PATH.read_text()
    assert "tempfile.mkstemp" in source
    assert "os.unlink(temp_name)" in source
    assert "PGPASSFILE" in source
    assert "BEGIN READ ONLY" in source
    assert "capture_output=True" in source
    assert "role in ROLES" in source
    assert "os.fchmod(output.fileno(),0o600)" in source
    assert "os.replace(" not in source
    for mutation in ("ALTER ROLE", "CREATE ROLE", "GRANT ", "INSERT INTO", "DELETE FROM", "pg_reload_conf("):
        assert mutation not in source
