"""CRM role bootstrap guard; no production database mutation during tests."""
from pathlib import Path
import hashlib
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "scripts/prepare_crm_pilot_identity_roles.sql"
DEPLOY = ROOT / "scripts/deploy_empiredb_crm_identity_roles.sh"


def test_exact_sql_pin_and_safety_contract():
    script = DEPLOY.read_text()
    sql = SQL.read_text()
    assert 'commit=f92cffbd' in script
    assert hashlib.sha256(SQL.read_bytes()).hexdigest() in script
    for guard in (
        "EXPLICIT_FOUNDER_APPROVAL_REQUIRED",
        "ROOT_OPERATOR_REQUIRED",
        "SQL_NOT_COMMITTED",
        "SQL_HASH_DRIFT",
        "APP_AND_DBA_INSTANCES_DIFFER",
        "PREEXISTING_ROLE_OR_ACCOUNT_RECONCILE_FIRST",
        "flock -n -x 9",
        "pg_dump -w -Fc -d empiredb",
        "pg_dumpall -w --globals-only",
        "pg_restore --list",
        "sha256sum -c SHA256SUMS",
        "POSTCOMMIT=UNEXPECTED_PERMISSION_NO_RETRY",
        "CRM_ROLES_USABLE_LOGINS=0",
        "CRM_ROLES_PASSWORDS_CONFIGURED=0",
        "CRM_ROLES_CREDENTIAL_ROWS=0",
        "CRM_ROLES_TENANT_READER_GRANTS=NONE",
        "CRM_ROLES_PUBLIC_API_ACTIVATED=NO",
        "CRM_ROLES_RESULT=NOLOGIN_IDENTITIES_PREPARED_PILOT_HELD",
    ):
        assert guard in script
    assert "PREPARED / NOT APPROVED" in sql
    assert sql.count("NOLOGIN NOINHERIT") == 2
    assert sql.count("PASSWORD NULL") == 2
    for forbidden in ("ALTER ROLE", "INSERT INTO", "GRANT empire_revenue_crm_reader", "CREATE ROLE empire_crm_tenant"):
        assert forbidden not in sql
    for forbidden in ("systemctl restart", "CREATE USER", "password_hash="):
        assert forbidden not in script


def test_bash_syntax():
    result = subprocess.run(["bash", "-n", str(DEPLOY)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_requires_intent_and_root_operator():
    for arguments in ([], ["--apply"], ["--help"], ["--apply", "--not-approved"]):
        result = subprocess.run(
            ["bash", str(DEPLOY), *arguments],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 3
        assert "EXPLICIT_FOUNDER_APPROVAL_REQUIRED" in result.stderr
    if os.geteuid() != 0:
        result = subprocess.run(
            ["bash", str(DEPLOY), "--apply", "--approved-release"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 3
        assert "ROOT_OPERATOR_REQUIRED" in result.stderr
