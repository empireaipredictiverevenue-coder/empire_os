"""Guarded operator deployment contract; never run privileged production writes."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deploy_crm_founder_owner_pending.sh"
SQL = ROOT / "scripts/provision_crm_founder_owner_pending.sql"


def test_exact_one_row_sql_pinned_to_deploy_script():
    src = SCRIPT.read_text()
    sql_sha = hashlib.sha256(SQL.read_bytes()).hexdigest()
    assert f"sql_sha={sql_sha}" in src
    assert "git ls-files --error-unmatch" in src
    assert 'git rev-parse "HEAD:$sql"' in src
    assert "--approved-pending-owner" in src
    assert "ROOT_OPERATOR_REQUIRED" in src
    assert "CRM_IDENTITY_ROLES_NOT_DORMANT" in SQL.read_text()
    assert "UNEXPECTED_TENANT_ROLE_BINDINGS" in SQL.read_text()
    assert "tenant_business_entity_bindings" not in SQL.read_text()
    assert "tenant_business_entity_bindings" not in src
    assert "OR EXISTS (SELECT 1 FROM public.empire_crm_login_credentials)" in SQL.read_text()


def test_operator_release_safeguards_and_one_transaction():
    src=SCRIPT.read_text()
    for required in (
        "set -euo pipefail", "umask 077",
        "postgresql@18-main.service", "/var/lib/postgresql/18/main",
        "APP_AND_OPERATOR_DATABASE_INSTANCE_DIFFER", "flock -n -x",
        "pg_dump -w -Fc -d empiredb", "pg_dumpall -w --globals-only",
        "pg_restore --list", "sha256sum -c SHA256SUMS",
        "chmod 0600", "BACKUP_INTEGRITY_FAILED",
        "CRM_FOUNDER_MEMBER_TRANSACTION=COMMITTED",
        "CRM_FOUNDER_MEMBER_POSTCOMMIT=UNEXPECTED_STATE_DO_NOT_RETRY",
        "CRM_FOUNDER_MEMBER_STATUS=pending",
        "CRM_FOUNDER_MEMBER_ACTIVE=0",
        "CRM_FOUNDER_MEMBER_CREDENTIALS=0",
        "CRM_FOUNDER_MEMBER_LOGIN_ROLE_CHANGES=NO",
        "CRM_FOUNDER_MEMBER_EMAIL_SENT=NO",
        "CRM_FOUNDER_MEMBER_HTTP_CONFIG_CHANGED=NO",
    ):
        assert required in src, required
    assert src.count('  -f "$sql" >') == 1
    for forbidden in (
        "ALTER ROLE", "GRANT ", "systemctl restart",
        "systemctl enable", "DROP TABLE", "CREATE ROLE",
        "INSERT INTO public.empire_crm_login_credentials",
    ):
        assert forbidden not in src


def test_shell_parses_and_missing_flags_block():
    check=subprocess.run(["bash","-n",str(SCRIPT)],text=True,capture_output=True)
    assert check.returncode==0,check.stderr
    for flags in ([],["--apply"],["--approved-pending-owner"]):
        result=subprocess.run(["bash",str(SCRIPT),*flags],
                              capture_output=True,text=True,timeout=4)
        assert result.returncode!=0
        assert "EXPLICIT_SINGLE_ROW_FOUNDER_SCOPE_REQUIRED" in result.stderr


def test_nonroot_operator_block():
    import os
    if os.geteuid()==0:
        return
    result=subprocess.run(["bash",str(SCRIPT),"--apply","--approved-pending-owner"],
                          capture_output=True,text=True,timeout=4)
    assert result.returncode!=0
    assert "ROOT_OPERATOR_REQUIRED" in result.stderr
