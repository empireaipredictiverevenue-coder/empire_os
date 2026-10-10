"""CRM046 one-off deployment safety; no live PostgreSQL mutation in tests."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "migrations/empiredb/046_crm_prospect_suppression_hit.sql"
RELEASE = ROOT / "scripts/deploy_empiredb_crm046_suppression_hit.sh"
FIXTURE = ROOT / "scripts/test_crm046_isolated_fixture.sh"


def test_minimal_production_migration_exact_authority_and_no_marketing_grants():
    text = SQL.read_text()
    assert text.startswith("-- EmpireDB 046")
    assert "CREATE FUNCTION public.empire_crm_prospect_suppression_hit(" in text
    assert "SECURITY DEFINER" in text
    assert "SET search_path = ''" in text
    assert "public.empire_crm_prospect_authorized(p_prospect_id)" in text
    assert "public.empire_current_tenant_id()" in text
    assert "session_user" in text
    assert "p_channel IS DISTINCT FROM 'sms'" in text
    assert "s.normalized_contact = v_phone" in text
    assert "RETURN 'SUPPRESSED';" in text
    assert text.count("RETURN 'UNKNOWN';") >= 2
    assert "REVOKE ALL ON FUNCTION" in text
    assert "TO empire_revenue_crm_reader;" in text
    assert "FROM PUBLIC;" in text
    assert "SET LOCAL ROLE empiredb_migrator;" in text
    assert "CREATE ROLE" not in text
    assert "ALTER ROLE" not in text
    assert "GRANT SELECT" not in text
    assert "GRANT INSERT" not in text
    assert "GRANT UPDATE" not in text
    assert "GRANT DELETE" not in text
    assert "TO empiredb_app" not in text
    assert "UPDATE public." not in text
    assert "DELETE FROM public." not in text
    assert "INSERT INTO public." not in text
    assert "ALTER TABLE" not in text
    assert text.count("BEGIN;") == 1 and text.count("COMMIT;") == 1


def test_operator_release_one_time_backup_hash_and_no_service_restart():
    text = RELEASE.read_text()
    assert "--approved-046-suppression-only" in text
    assert "TWO_EXACT_APPROVAL_FLAGS_REQUIRED" in text
    assert "REVIEWED_MIGRATION_DRIFT" in text
    assert "git status --porcelain" in text
    assert "postgresql@18-main.service" in text
    assert "BACKUP_SHA256_CHECK_FAILED" in text
    assert "pg_dump -w -Fc -d empiredb" in text
    assert "pg_dumpall -w --globals-only" in text
    assert "pg_restore --list" in text
    assert "FLock".lower() in text.lower()
    assert "SELECT public.empire_crm_prospect_suppression_hit(NULL::uuid,'sms')" in text
    assert "UNKNOWN" in text
    assert "CRM046_STATUS=FUNCTION_DEPLOYED_NOT_MARKETING_ELIGIBILITY" in text
    assert "systemctl restart" not in text
    assert "\nGRANT " not in text  # audit-status label is not a grant statement
    for p in (RELEASE, FIXTURE):
        check = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert check.returncode == 0, check.stderr


def test_apply_script_requires_both_exact_flags_without_db_access():
    result = subprocess.run(["bash", str(RELEASE)], capture_output=True, text=True)
    assert result.returncode == 3
    assert "TWO_EXACT_APPROVAL_FLAGS_REQUIRED" in result.stderr
