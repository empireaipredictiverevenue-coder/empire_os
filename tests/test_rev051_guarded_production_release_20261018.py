"""Exact founder-approved REV051 release: preflight/rollback/privilege invariants.

No test runs the production deployment or requires protected credentials.
The actual prepared migration is separately executed on disposable PostgreSQL.
"""
from pathlib import Path
import subprocess
import hashlib

ROOT=Path(__file__).resolve().parents[1]
GUARD=ROOT/"scripts/deploy_approved_rev051_guarded_20261018.sh"
DDL=ROOT/"migrations/empiredb/051_predictive_revenue_event_reader_held.sql"
PIN="b8509150662512c1e9fae9c8dfb1e288bb68ce0fbf95c3cb98a43125bfeb6bc7"


def test_released_ddl_is_exact_immutable_tested_artifact():
    assert hashlib.sha256(DDL.read_bytes()).hexdigest()==PIN
    assert PIN in GUARD.read_text()
    result=subprocess.run(["bash","-n",str(GUARD)],
                          capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_unapproved_flags_never_activate_ddl():
    source=GUARD.read_text()
    assert 'if [[ "${1:-}" != "--apply-approved-role-function-only" || "$#" != 1 ]]' in source
    assert '[[ ${EUID} == 0 ]] || hold "ROOT_SESSION_REQUIRED"' in source
    assert "MIGRATION_SOURCE_HASH_MISMATCH" in source
    assert "CATALOG_SOURCE_SCOPE_CHANGED" in source
    assert "BACKUP_REPOSITORY_NOT_ACCESSIBLE" in source
    assert "RECENT_VERIFIED_BACKUP_NOT_PROVEN" in source
    assert "PRIMARY_ARCHIVE_NOT_PROVEN" in source


def test_privileged_release_only_allows_one_existing_ddl_artifact():
    source=GUARD.read_text()
    assert 'if ! pg -f "$SQL"' in source
    assert source.count('pg -f "$SQL"')==1
    assert source.count('pg -f "$CATALOG"')==2
    assert source.count('pgbackrest info --output=json')==1
    assert "runuser -u postgres -- psql" in source
    assert "BEGIN" in DDL.read_text()
    assert DDL.read_text().rstrip().endswith("COMMIT;")
    executable="\n".join(line for line in source.splitlines()
                         if not line.lstrip().startswith("#"))
    for value in ("pgbackrest backup","pgbackrest restore",
                  "systemctl restart","CREATE USER",
                  "grant login", "initdb", "DROP DATABASE",
                  "ALTER SYSTEM","pg_switch_wal"):
        assert value.lower() not in executable.lower()


def test_after_commit_catalog_enforces_role_only_and_no_login():
    source=GUARD.read_text()
    for field in (
        "'function_exists':True",
        "'capability_exists':True",
        "'capability_no_login_no_admin':True",
        "'capability_can_execute':True",
        "'function_owned_by_migrator':True",
        "'function_security_definer_stable_locked_path':True",
        "'public_execute_denied':True",
        "'role_has_no_direct_source_table_grants':True",
        "'dedicated_login_member_exists':False",
        "'canonical_event_fetched':False",
        "'customer_report_release_authorized':False",
    ):
        assert field in source
    assert "REV051_DEPLOYMENT_DONE=ROLE_FUNCTION_ONLY_LOGIN_AND_PAYMENTS_UNCHANGED" in source
