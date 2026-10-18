#!/usr/bin/env bash
# Founder-approved, SINGLE-SCOPE EmpireDB REV051 role+function deployment.
# This does not create logins, memberships, customer reports or payments.
# Run from the existing EmpireOS host using sudo after source review.
set -euo pipefail
umask 077

ROOT=/srv/empire_os
SQL="$ROOT/migrations/empiredb/051_predictive_revenue_event_reader_held.sql"
CATALOG="$ROOT/scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql"
EXPECTED_SHA=b8509150662512c1e9fae9c8dfb1e288bb68ce0fbf95c3cb98a43125bfeb6bc7

hold() {
  printf 'REV051_DEPLOYMENT_HOLD=%s\n' "$1" >&2
  exit 2
}

if [[ "${1:-}" != "--apply-approved-role-function-only" || "$#" != 1 ]]; then
  hold "EXACT_FOUNDER_APPROVED_SCOPE_REQUIRED"
fi
[[ ${EUID} == 0 ]] || hold "ROOT_SESSION_REQUIRED"
[[ -d "$ROOT/.git" || -f "$ROOT/.git" ]] || hold "CANONICAL_REPOSITORY_NOT_FOUND"
[[ -f "$SQL" && ! -L "$SQL" && -f "$CATALOG" && ! -L "$CATALOG" ]] ||
  hold "REVIEWED_FILES_MISSING"
# Strict immutable release image, independent of other agents' source files.
echo "$EXPECTED_SHA  $SQL" | sha256sum -c --status ||
  hold "MIGRATION_SOURCE_HASH_MISMATCH"
command -v runuser >/dev/null || hold "LOCAL_POSTGRES_IDENTITY_NOT_AVAILABLE"
command -v pgbackrest >/dev/null || hold "PGBACKREST_MISSING"

# Deny accidental PGPASSWORD, PGHOST, etc overrides; use only the local peer
# administrator and existing production PostgreSQL socket.
unset PGHOST PGHOSTADDR PGUSER PGPASSWORD PGPASSFILE PGDATABASE PGPORT PGOPTIONS PGSERVICE PGSERVICEFILE
tmp="$(mktemp -d /tmp/empire-rev051-release-XXXXXXXX)"
chmod 0700 "$tmp"
trap 'rm -rf "$tmp"' EXIT

pg() {
  runuser -u postgres -- psql -X -q -w -A -t -v ON_ERROR_STOP=1 \
    -h /var/run/postgresql -p 5432 -U postgres -d empiredb "$@"
}

# Read-only recovery metadata: do not initiate a new backup, WAL switch, or
# restore. A current physical pgBackRest backup is required to proceed.
if ! runuser -u postgres -- pgbackrest info --output=json \
    > "$tmp/backups.json" 2> "$tmp/backup.stderr"; then
  hold "BACKUP_REPOSITORY_NOT_ACCESSIBLE"
fi
python3 - "$tmp/backups.json" <<'PYBACKUP' || exit 2
import json,sys
from pathlib import Path
sys.path.insert(0,'/srv/empire_os')
from empire_os.rev051_pgbackrest_readiness import review_pgbackrest_info
try:
    metadata=json.loads(Path(sys.argv[1]).read_text())
    review=review_pgbackrest_info(metadata)
    if review['status']!='PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED':
        print('REV051_DEPLOYMENT_HOLD=RECENT_VERIFIED_BACKUP_NOT_PROVEN',
              'reason='+review.get('reason','UNKNOWN'),file=sys.stderr)
        raise SystemExit(2)
    print('REV051_LOCAL_RECOVERY_PREFLIGHT_PASS',
          'latest_backup_age_hours='+str(review['newest_backup_age_hours']),
          'healthy_stanzas='+str(review['healthy_stanza_count']))
except (ValueError,TypeError,KeyError,OSError):
    print('REV051_DEPLOYMENT_HOLD=RECENT_VERIFIED_BACKUP_NOT_PROVEN',
          'reason=INVALID_METADATA',file=sys.stderr)
    raise SystemExit(2)
PYBACKUP

# Confirm primary is active, archive mode is on and there is evidence of at
# least one successful WAL archive. The SQL introspection itself is read-only.
if ! pg -c "SELECT pg_catalog.jsonb_build_object(
  'correct_database',current_database()='empiredb',
  'postgres_18',current_setting('server_version_num')::int>=180000,
  'primary',NOT pg_catalog.pg_is_in_recovery(),
  'archive_on',current_setting('archive_mode')='on',
  'archive_command_present',length(trim(current_setting('archive_command')))>0,
  'successful_archives',(SELECT archived_count>0 FROM pg_catalog.pg_stat_archiver)
)::text" > "$tmp/primary.json"; then
  hold "PRIMARY_ARCHIVE_PREFLIGHT_READ_FAILED"
fi
python3 - "$tmp/primary.json" <<'PYPRIMARY' || exit 2
import json,sys
from pathlib import Path
try:
    d=json.loads(Path(sys.argv[1]).read_text().strip())
    assert all(v is True for v in d.values()),d
    print('REV051_PRIMARY_AND_ARCHIVE_PREFLIGHT_PASS')
except (ValueError,TypeError,AssertionError,OSError):
    print('REV051_DEPLOYMENT_HOLD=PRIMARY_ARCHIVE_NOT_PROVEN',file=sys.stderr)
    raise SystemExit(2)
PYPRIMARY

# No tenant rows, commercial events or customer identity are retrieved.
if ! pg -f "$CATALOG" > "$tmp/before.json"; then
  hold "CATALOG_PRECHECK_FAILED"
fi
python3 - "$tmp/before.json" <<'PYBEFORE' || exit 2
import json,sys
from pathlib import Path
try:
    x=json.loads(Path(sys.argv[1]).read_text().strip())
    expected={'correct_database':True,
              'all_three_source_tables_exist':True,
              'canonical_session_tenant_resolver_exists':True,
              'capability_exists':False,
              'function_exists':False,
              'dedicated_login_member_exists':False}
    assert x['status']=='HOLD_EVENT_READER_CATALOG_NOT_PROVEN'
    assert all(x.get(k) is v for k,v in expected.items()),x
    print('REV051_EXACT_ABSENT_OBJECTS_AND_EXISTING_TENANT_FOUNDATION_PASS')
except (ValueError,KeyError,TypeError,AssertionError,OSError):
    print('REV051_DEPLOYMENT_HOLD=CATALOG_SOURCE_SCOPE_CHANGED',file=sys.stderr)
    raise SystemExit(2)
PYBEFORE

# The file starts BEGIN, applies role+function in one transaction, and ends
# COMMIT. If any precondition fails, PostgreSQL will roll back the changes.
echo 'REV051_DATABASE_MIGRATION_START=APPROVED_ROLE_AND_FUNCTION_ONLY'
if ! pg -f "$SQL" > "$tmp/migration.stdout" 2> "$tmp/migration.stderr"; then
  echo 'REV051_DEPLOYMENT_HOLD=DDL_ABORTED_CHECK_POSTGRES_ERROR_LOG' >&2
  # Printing the last one or two error lines does not expose row content.
  tail -n 3 "$tmp/migration.stderr" >&2 || true
  exit 2
fi
echo 'REV051_DATABASE_MIGRATION_TRANSACTION_COMMITTED'

if ! pg -f "$CATALOG" > "$tmp/after.json"; then
  hold "POST_DEPLOYMENT_CATALOG_QUERY_FAILED"
fi
python3 - "$tmp/after.json" <<'PYAFTER' || exit 2
import json,sys
from pathlib import Path
try:
    x=json.loads(Path(sys.argv[1]).read_text().strip())
    expected={
        'correct_database':True,
        'capability_exists':True,
        'capability_no_login_no_admin':True,
        'function_exists':True,
        'function_security_definer_stable_locked_path':True,
        'function_owned_by_migrator':True,
        'capability_can_execute':True,
        'public_execute_denied':True,
        'all_three_source_tables_exist':True,
        'role_has_no_direct_source_table_grants':True,
        'canonical_session_tenant_resolver_exists':True,
        'dedicated_login_member_exists':False,
        'canonical_event_fetched':False,
        'daily_revenue_census_verified':False,
        'customer_report_release_authorized':False,
    }
    assert x['status']=='HOLD_EVENT_READER_CATALOG_NOT_PROVEN'
    assert all(x.get(k) is v for k,v in expected.items()),x
    print('REV051_ROLE_FUNCTION_LIVE_CATALOG_VERIFIED')
    print('REV051_DEDICATED_LOGIN_STILL_NOT_INSTALLED')
    print('REV051_CUSTOMER_FINANCE_AND_DELIVERY_NOT_VERIFIED')
except (ValueError,TypeError,KeyError,AssertionError,OSError):
    print('REV051_DEPLOYMENT_HOLD=POST_COMMIT_CATALOG_INCONSISTENT',
          file=sys.stderr)
    raise SystemExit(2)
PYAFTER

echo 'REV051_DEPLOYMENT_DONE=ROLE_FUNCTION_ONLY_LOGIN_AND_PAYMENTS_UNCHANGED'
