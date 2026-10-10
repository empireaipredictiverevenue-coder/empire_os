"""CRM042 release guard: schema only; no implicit authority or unapproved DB writes."""
from __future__ import annotations

import subprocess
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "scripts/deploy_empiredb_crm042.sh"
SQL = Path(__file__).resolve().parents[1] / "migrations/empiredb/042_crm_first_party_login.sql"


def test_crm042_shell_syntax_and_pinned_existing_migration():
    script = DEPLOY.read_text()
    assert subprocess.run(["bash", "-n", str(DEPLOY)], capture_output=True).returncode == 0
    assert "810d1dfb" in script
    assert "5ecee3b24d886e6664d2189a94da95695a71c2825820ab74388443c909893f43" in script
    assert "git rev-parse" in script
    assert "MIGRATION_COMMIT_DRIFT" in script
    assert "MIGRATION_SHA256_DRIFT" in script
    assert "migrations/empiredb/042_crm_first_party_login.sql" in script
    assert "NOT_PERFORMED" in script
    assert SQL.is_file()


def test_schema_deploy_rejects_execution_without_explicit_flag_and_root_authority():
    for args in ([], ["--apply"], ["--preflight"], ["--help"], ["--apply", "--approval-pending"]):
        result = subprocess.run(
            ["bash", str(DEPLOY), *args],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 3
        assert "EXPLICIT_FOUNDER_APPROVAL_REQUIRED" in result.stderr


def test_schema_migration_does_not_create_accounts_roles_or_outbound_authority():
    schema = SQL.read_text()
    assert "CREATE TABLE public.empire_crm_login_credentials" in schema
    assert "ENABLE ROW LEVEL SECURITY" in schema
    assert "CREATE ROLE " not in schema
    assert "GRANT SELECT" not in schema
    assert "INSERT INTO " not in schema
    assert "PREPARED ONLY" in schema
    script = DEPLOY.read_text()
    assert "CRM042_CREDENTIAL_ROWS=0" in script
    assert "CRM042_ROLE_GRANTS_PERFORMED=NO" in script
    assert "CRM042_PUBLIC_API_ACTIVATED=NO" in script
    assert "CRM042_OUTBOUND_PAYMENT_AUTHORITY=NONE" in script
    assert "pg_dump -w -Fc" in script
    assert "pg_dumpall -w --globals-only" in script
    assert "sha256sum -c SHA256SUMS" in script
    assert "POST_COMMIT_CATALOG_UNSAFE_NO_RETRY" in script
