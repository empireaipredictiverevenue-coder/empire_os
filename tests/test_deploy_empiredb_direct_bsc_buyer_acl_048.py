"""Fail-closed, separately approved one-table ACL repair for EmpireDB 047."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/deploy_empiredb_direct_bsc_buyer_acl_048.sh"
SQL=ROOT/"migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql"


def test_exact_approval_required_before_any_database_write():
    code=SCRIPT.read_text()
    assert code.count("--approved-048-one-table-acl-seal-only")==1
    assert code.index("--approved-048-one-table-acl-seal-only") < code.index("exec 9>")
    assert "ROOT_OPERATOR_REQUIRED" not in code  # intentionally called PRIVILEGED_OPERATOR_REQUIRED
    assert "PRIVILEGED_OPERATOR_REQUIRED" in code
    for args in (
        (), ("--apply",), ("--preflight",), ("--apply","--approved-047-sealed-buyer-capability-only"),
        ("--apply","--approved-048-one-table-acl-seal-only","unexpected"),
    ):
        p=subprocess.run(["bash",str(SCRIPT),*args],capture_output=True,text=True,timeout=3)
        assert p.returncode==3
        assert "SEPARATE_EXACT_FOUNDER_APPROVAL_REQUIRED" in p.stderr


def test_exact_sql_only_revokes_new_table_and_preserves_default_privileges():
    sql=SQL.read_text()
    assert "BEGIN;" in sql and "COMMIT;" in sql
    assert "SET LOCAL ROLE empiredb_migrator" in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.direct_bsc_buyer_capabilities" in sql
    assert "FROM empiredb_app, empiredb_readonly;" in sql
    assert "DIRECT048_EXACT_EXISTING_GRANTS_DRIFT" in sql
    assert "DIRECT048_SEALED_ACL_POSTCHECK_FAIL" in sql
    assert "relforcerowsecurity" in sql
    assert "pg_catalog.pg_policy" in sql
    assert "'empiredb_readonly:SELECT'" in sql
    for bad in (
        "ALTER DEFAULT PRIVILEGES", "ALTER ROLE ", "CREATE ROLE ", "DROP TABLE ",
        "GRANT SELECT ON", "DELETE FROM public.", "INSERT INTO public.",
        "REVOKE ALL ON SCHEMA", "SET ROLE empiredb_app",
    ):
        assert bad not in sql.replace("all existing ALTER DEFAULT PRIVILEGES", "all existing default privileges")


def test_wrapper_pins_source_and_keeps_payment_and_public_service_off():
    code=SCRIPT.read_text()
    for required in (
        "git hash-object", "HEAD:$file", "APP_DB_AND_BACKUP_DB_DIVERGE",
        "DIRECT048_EXACT_047_ACL_HOLD=VERIFIED",
        "DIRECT048_BACKUP=VERIFIED",
        "DIRECT048_SQL_TRANSACTION=COMMITTED",
        "DIRECT048_ALL_NINE_POSTCOMMIT_SECURITY_CHECKS=PASS",
        "DIRECT048_APP_AND_READONLY_ROLE_DENIAL=VERIFIED",
        "DIRECT048_RUNTIME_FINANCIAL_GATES=STILL_OFF_VERIFIED",
        "DIRECT048_STATUS=ONE_TABLE_ACL_SEALED_NO_PAYMENT_ACTIVATION",
        "sha256sum -c SHA256SUMS", "pg_restore --list", "flock -n -x 9",
        "DIRECT048_FULL_RESTORE_REHEARSAL=NOT_PERFORMED",
        "POSTCOMMIT_CHECK_FAILED_DO_NOT_RETRY",
    ):
        assert required in code
    for forbidden in (
        "systemctl restart", "systemctl daemon-reload", "ALTER ROLE ",
        "CREATE ROLE ", "sendRawTransaction", "ALTER DEFAULT PRIVILEGES",
        "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON",
        "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON",
    ):
        assert forbidden not in code


def test_shell_syntax_and_source_integrity():
    for target in (SCRIPT,ROOT/"scripts/test_empiredb_direct_bsc_capability_acl_048_ephemeral.sh"):
        p=subprocess.run(["bash","-n",str(target)],capture_output=True,text=True,timeout=3)
        assert p.returncode==0,p.stderr
