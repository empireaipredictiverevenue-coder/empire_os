#!/usr/bin/env bash
# PostgreSQL 18 integration tests in a disposable local-only fixture.
# No production DB, service, socket, migrations or customer data.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
PG_BIN=/usr/lib/postgresql/18/bin
PYTHON=/srv/empire_os/.venv/bin/python
for binary in initdb pg_ctl createdb psql; do
  test -x "$PG_BIN/$binary" || { echo "MISSING_TEST_TOOL:$binary"; exit 2; }
done
test -x "$PYTHON" || { echo "MISSING_TEST_PYTHON"; exit 2; }
test -f "$ROOT/docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql"
test -f "$ROOT/tests/fixtures/mautic_crm_pg_runtime_fixture.sql"
test "$(id -u)" -ne 0 || { echo "REFUSE_ROOT_EXECUTION"; exit 2; }

TMP="$(mktemp -d /tmp/empire_mautic_pg_fixture.XXXXXXXX)"
chmod 700 "$TMP"
started=0
cleanup() {
  code=$?
  trap - EXIT HUP INT TERM
  if [ "$started" -eq 1 ]; then
    "$PG_BIN/pg_ctl" -D "$TMP/data" -m immediate -w stop >/dev/null 2>&1 || true
  fi
  case "$TMP" in
    /tmp/empire_mautic_pg_fixture.*) rm -rf -- "$TMP" ;;
    *) echo "UNEXPECTED_TEST_PATH_NOT_REMOVED";;
  esac
  exit "$code"
}
trap cleanup EXIT HUP INT TERM

mkdir -m 700 "$TMP/sock"
"$PG_BIN/initdb" --no-instructions --encoding=UTF8 --locale=C.utf8 --auth-local=trust --auth-host=reject \
  -U fixture_owner -D "$TMP/data" > "$TMP/init.log" 2>&1

# No TCP listener; Unix socket inside an owner-only temporary folder.
"$PG_BIN/pg_ctl" -D "$TMP/data" -l "$TMP/postgres.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$TMP/sock' -p 55488" \
  -w start > "$TMP/start.log" 2>&1
started=1

export PGHOST="$TMP/sock"
export PGPORT=55488
export PGUSER=fixture_owner
export PGDATABASE=mautic_crm_inbox_fixture

"$PG_BIN/createdb" "$PGDATABASE"
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/tests/fixtures/mautic_crm_pg_runtime_fixture.sql" > "$TMP/fixture.log"

# Exact proposed DBA role preparation, tested against the true synthetic
# tenant resolver and actual private public-schema ownership.
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/docs/integrations/sql/MAUTIC_CRM_INBOX_WRITER_ROLE_PREPARED_ONLY_20261119.sql" \
  > "$TMP/role-prep.log"

# Deliberately refuse a second role-prep invocation; a release must
# reconcile collisions, not silently reuse a role with uncertain grants.
if "$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/docs/integrations/sql/MAUTIC_CRM_INBOX_WRITER_ROLE_PREPARED_ONLY_20261119.sql" \
  > "$TMP/role-collision.log" 2>&1; then
  echo "MAUTIC_ROLE_COLLISION_NOT_REJECTED" >&2
  exit 3
fi

# Only the fixture's synthetic login roles receive membership. No live
# tenant login, tenant ID, account, or permission is provisioned here.
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -c \
  "GRANT empire_mautic_crm_inbox_writer TO mautic_fixture_writer_a,mautic_fixture_writer_b,empire_mautic_tenant_aabbccddeeff" \
  > "$TMP/fixture-membership.log"
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql" \
  > "$TMP/migration.log"

"$PG_BIN/psql" -X -At -c \
  "SELECT relrowsecurity::text || ',' || relforcerowsecurity::text
   FROM pg_class
   WHERE oid='public.empire_crm_mautic_event_inbox'::regclass" |
  grep -Fx 'true,true' >/dev/null

cd "$ROOT"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -B -m pytest \
  -q -p no:cacheprovider tests/test_mautic_crm_pg_runtime.py

# The rollback MUST refuse a populated or member-bound inbox. Both
# negative cases execute only inside this disposable fixture database.
if "$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/docs/integrations/sql/MAUTIC_CRM_INBOX_ROLLBACK_DBA_ONLY_20261119.sql" \
  > "$TMP/rollback-active-writer.log" 2>&1; then
  echo "MAUTIC_ROLLBACK_UNEXPECTEDLY_REMOVED_MEMBER_BOUND_WRITER" >&2
  exit 4
fi
grep -F "writer has member logins" "$TMP/rollback-active-writer.log" >/dev/null
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -c \
  "REVOKE empire_mautic_crm_inbox_writer FROM mautic_fixture_writer_a,mautic_fixture_writer_b,empire_mautic_tenant_aabbccddeeff" \
  > "$TMP/fixture-membership-revoked.log"
if "$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/docs/integrations/sql/MAUTIC_CRM_INBOX_ROLLBACK_DBA_ONLY_20261119.sql" \
  > "$TMP/rollback-populated.log" 2>&1; then
  echo "MAUTIC_ROLLBACK_UNEXPECTEDLY_REMOVED_EVIDENCE" >&2
  exit 4
fi
grep -F "inbox contains evidence" "$TMP/rollback-populated.log" >/dev/null

# Data deletion is fixture-only, after tests, never production. A real
# populated Mautic inbox must preserve its evidence instead of rollback.
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -c \
  "DELETE FROM public.empire_crm_mautic_event_inbox" > "$TMP/fixture-data-cleared.log"
"$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -f \
  "$ROOT/docs/integrations/sql/MAUTIC_CRM_INBOX_ROLLBACK_DBA_ONLY_20261119.sql" \
  > "$TMP/rollback-empty.log"
"$PG_BIN/psql" -X -At -v ON_ERROR_STOP=1 -c \
  "SELECT (pg_catalog.to_regclass('public.empire_crm_mautic_event_inbox') IS NULL)::text || ',' || (NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_mautic_crm_inbox_writer'))::text" | \
  grep -Fx 'true,true' >/dev/null

echo "MAUTIC_ISOLATED_ROLE_MIGRATION_AND_FAIL_CLOSED_ROLLBACK_VERIFIED"
echo "ISOLATED_POSTGRESQL_RUNTIME_VERIFIED_AND_CLEANUP_REQUESTED"
