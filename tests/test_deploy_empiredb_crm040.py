"""Safety contracts for founder-approved CRM040 root operator handoff.

No production SQL, backup or sudo calls are made by these tests.
"""
from pathlib import Path
import os
import subprocess

P = (
    Path(__file__).resolve().parents[1]
    / "scripts/deploy_empiredb_crm040.sh"
)


def test_script_has_valid_shell_syntax_and_needs_explicit_root():
    result = subprocess.run(
        ["bash", "-n", str(P)], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    source = P.read_text()
    assert "EXPLICIT_APPLY_REQUIRED" in source
    assert "AUTHORIZED_ROOT_OPERATOR_REQUIRED" in source
    assert "MIGRATION_DRIFT_FROM_APPROVED_COMMIT" in source
    assert "04379446bcbbeb282051cc79b96e628f9c17457ea9db875b5fba32952f31d22c" in source
    assert "25680327" in source


def test_unprivileged_cli_denied_before_db_or_disk_access():
    if os.geteuid() == 0:
        return
    result = subprocess.run(
        ["bash", str(P), "--apply"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 3
    assert "AUTHORIZED_ROOT_OPERATOR_REQUIRED" in result.stderr
    assert "CRM040_MIGRATION_APPLY=STARTING" not in result.stdout


def test_wrong_action_blocked_even_without_privilege():
    result = subprocess.run(
        ["bash", str(P), "--other"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 3
    assert "EXPLICIT_APPLY_REQUIRED" in result.stderr


def test_live_system_and_database_cannot_be_stopped_by_script():
    s = P.read_text()
    for forbidden in (
        "systemctl stop", "systemctl restart", "pg_ctlcluster",
        "pgbackrest", "DROP DATABASE", "DROP TABLE", "DROP ROLE",
        "GRANT empire_revenue_crm_reader TO", "pg_dump -h",
        "wget ", "curl ", "rm -rf",
    ):
        assert forbidden not in s
    assert "pg_dump -w -Fc" in s
    assert "pg_dumpall -w --globals-only" in s
    assert "pg_restore --list" in s
    assert "sha256sum -c SHA256SUMS" in s
    assert "pg_dump" in s and "CRM040_BACKUP" in s
    assert "CRM040_FULL_RESTORE_REHEARSAL=NOT_PERFORMED" in s
    assert "CRM040_PUBLIC_API_ACTIVATED=NO" in s
    assert "CRM040_OUTBOUND_PAYMENT_AUTHORITY=NONE" in s


def test_backup_must_verify_before_transaction_and_post_check():
    s = P.read_text()
    assert s.index("CRM040_BACKUP_ARCHIVE=VERIFIED_FORMAT_AND_SHA256") < s.index(
        "CRM040_MIGRATION_APPLY=STARTING"
    )
    assert s.index("CRM040_MIGRATION_APPLY=STARTING") < s.index(
        "CRM040_POST_DEPLOYMENT_CATALOG=PASS"
    )
    assert "MIGRATION_STATUS=FAILED_TRANSACTION_ROLLED_BACK" in s
    assert "CRM040_TRANSACTION_ALREADY_COMMITTED=YES" in s
    assert "source /etc/empiredb.env" in s
    assert "EMPIREDB_DSN" in s
    assert "PUBLIC_PERMISSIVE_RLS_POLICY_REQUIRES_REVIEW" in s
    assert "BACKUP_AND_APPLICATION_DATABASE_NOT_SAME_INSTANCE" in s
    assert "CRM_ROLE_ALREADY_REACHABLE_FROM_LOGIN" in s
    assert "POST_COMMIT_CRM_ROLE_LOGIN_MEMBERSHIP_FOUND" in s
    assert s.count("account.rolcanlogin AND NOT account.rolsuper") == 2
    assert "current_setting('data_directory')" in s
