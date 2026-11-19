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

echo "ISOLATED_POSTGRESQL_RUNTIME_VERIFIED_AND_CLEANUP_REQUESTED"
