"""Migration 052 operator gate is schema-only and never runs an import."""
from pathlib import Path
import subprocess

SCRIPT=Path("/srv/empire_os/scripts/activate_workspace_historical_receipts_migration_052_20261018.sh")
MIGRATION=Path("/srv/empire_os/migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql")


def test_restricted_migration_operator_syntax_and_explicit_modes():
    assert subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,timeout=5).returncode==0
    for args in ([],["--send"],["--apply-founder-approved-migration-052","extra"]):
        result=subprocess.run(["bash",str(SCRIPT),*args],
                              capture_output=True,text=True,timeout=5)
        assert result.returncode==2


def test_operator_migrates_only_frozen_exact_052_schema():
    script=SCRIPT.read_text()
    assert "1122ad3d77b05b204f37e244a2968b99ed902346b6c4b6e75c291f99e43d4693" in script
    assert "sha256sum -c --status" in script
    assert "MIGRATION_CHANGED_DURING_FREEZE" in script
    assert "SCHEMA_IS_NOT_IN_PRE_MIGRATION_STATE" in script
    assert "LIVE_EMPIREDB_ROLE_ARCHIVER_AND_SCHEMA_PREFLIGHT_PASS" in script
    assert "pg_is_in_recovery()" in script
    assert "pg_stat_archiver" in script
    assert "has_schema_privilege('empire_closer_observer','public','USAGE')" in script
    assert "env -i PATH=/usr/bin:/bin" in script
    assert "-h /var/run/postgresql -p 5432 -d empiredb" in script
    assert "flock -n" in script
    assert "SET LOCAL ROLE empiredb_migrator" in MIGRATION.read_text()
    assert "POST_MIGRATION_RLS_TRIGGER_GRANT_OR_EMPTY_TABLE" in script
    assert "SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS" in script
    assert "EMPIREDB_MIGRATION_052_SCHEMA_VERIFIED" in script
    assert "import_authorized=no" in script
    for disallowed in (
        "import_workspace_historical_sent_receipts_20261018.py",
        "INSERT INTO public.workspace_historical_sent_receipts",
        "UPDATE public.outbound_intents",
        "DELETE FROM public.outbound_intents",
        "DROP TABLE",
        "pg_restore",
        "systemctl restart",
        "git reset",
        "curl -X POST",
    ):
        assert disallowed not in script


def test_observe_only_new_evidence_table_guardrails():
    sql=MIGRATION.read_text()
    for marker in (
        "BEGIN;","COMMIT;","workspace_historical_sent_receipts",
        "FORCE ROW LEVEL SECURITY",
        "BEFORE UPDATE OR DELETE",
        "workspace_historical_no_retrospective_approval",
        "workspace_historical_no_unproven_crm",
        "workspace_historical_no_fake_revenue",
        "SELECT TO empire_closer_observer",
    ):
        assert marker in sql
    for disallowed in ("INSERT INTO public.outbound_intents","CREATE ROLE","DROP TABLE"):
        assert disallowed not in sql
