"""Approved CRM041 deployment contract: fail closed without root, exact SQL."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deploy_empiredb_crm041.sh"
SQL = ROOT / "migrations/empiredb/041_crm_membership_authority.sql"


def test_guarded_crm041_release_contract():
    import hashlib
    source = SCRIPT.read_text()
    assert 'approved_commit="19350a99"' in source
    assert hashlib.sha256(SQL.read_bytes()).hexdigest() in source
    for required in (
        "AUTHORIZED_ROOT_REQUIRED",
        "EXPLICIT_APPLY_FLAG_REQUIRED",
        "COMMITTED_SQL_DRIFT",
        "APP_DATABASE_INSTANCE_MISMATCH",
        "MIGRATION_041_DEPENDENCIES_OR_ALREADY_INSTALLED",
        "postgresql@18-main.service",
        "CRM041_FULL_RESTORE_REHEARSAL=NOT_PERFORMED",
        "pg_dump -w -Fc -d empiredb",
        "pg_dumpall -w --globals-only",
        "pg_restore --list",
        "sha256sum -c SHA256SUMS",
        "flock -n -x 9",
        "ON_ERROR_STOP=1",
        "CRM041_TRANSACTION=COMMITTED",
        "CRM041_POSTCOMMIT=UNEXPECTED_PERMISSIONS_NO_RETRY",
        "CRM041_PUBLIC_API_ACTIVATED=NO",
        "CRM041_MEMBERSHIP_ROWS=0",
        "CRM041_OUTBOUND_PAYMENT_AUTHORITY=NONE",
        "CRM041_RESULT=SCHEMA_INSTALLED_APPLICATION_ACTIVATION_HELD",
    ):
        assert required in source
    assert chr(92) + chr(36) + "{" not in source
    for forbidden in (
        "systemctl restart",
        "GRANT empire_revenue_crm_reader TO",
        "INSERT INTO public.empire_crm_tenant_memberships",
        "migrations/empiredb/040_",
    ):
        assert forbidden not in source


def test_crm041_script_shell_syntax():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_crm041_needs_explicit_apply():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 3
    assert "EXPLICIT_APPLY_FLAG_REQUIRED" in result.stderr


def test_crm041_refuses_unprivileged_apply():
    import os
    if os.geteuid() == 0:
        import pytest
        pytest.skip("This safety test runs as the unprivileged operator")
    result = subprocess.run(["bash", str(SCRIPT), "--apply"], capture_output=True, text=True)
    assert result.returncode == 3
    assert "AUTHORIZED_ROOT_REQUIRED" in result.stderr
