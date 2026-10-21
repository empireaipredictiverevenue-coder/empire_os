#!/usr/bin/env bash
# Runs only under pg_virtualenv. Never targets EmpireDB.
set -euo pipefail
[[ "${PGHOST:-}" == localhost && "${PGPORT:-}" =~ ^[0-9]+$ ]] || exit 3
[[ "$PGPORT" -gt 5432 ]] || exit 3
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS" >/dev/null
createdb -O empiredb_migrator -E UTF8 -T template0 empire_consumer_optin_fixture
PYTHONPATH="$W" /srv/empire_os/.venv/bin/python -B \
    "$W/scripts/guarded_install_consumer_schema_20261021.py" --test-ephemeral
# Confirm the role has no login and the exact five tables, nothing else.
psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -tA <<'SQL'
SELECT 'LIVE_SUBSCRIBER_USER_ROLE_NOLOGIN=' || NOT rolcanlogin
 FROM pg_roles WHERE rolname='empire_consumer_optin_writer';
SELECT 'INSTALL_TABLE_COUNT=' || count(*) FROM pg_class c
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname LIKE 'empire_consumer_%'
 AND c.relkind='r';
SQL
