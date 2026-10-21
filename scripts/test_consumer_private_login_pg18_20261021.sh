#!/usr/bin/env bash
# Real private login on a throwaway pg_virtualenv fixture only.
set -euo pipefail
[[ "${PGHOST:-}" == localhost && "${PGPORT:-}" =~ ^[0-9]+$ ]] || exit 3
[[ "$PGPORT" -gt 5432 ]] || exit 3
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
pg() { psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture "$@"; }
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_app NOLOGIN" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_readonly NOLOGIN" >/dev/null
createdb -O empiredb_migrator -E UTF8 -T template0 empire_consumer_optin_fixture
pg <<'SQL' >/dev/null
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO empiredb_app;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO empiredb_readonly;
SQL
PYTHONPATH="$W" /srv/empire_os/.venv/bin/python -B \
  "$W/scripts/guarded_install_consumer_schema_20261021.py" --test-ephemeral
pg <<'SQL' >/dev/null
CREATE ROLE empire_consumer_optin_login
 LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
 NOCREATEDB NOCREATEROLE NOREPLICATION
 PASSWORD 'synthetic_fake_secret_for_fixture_only_2026';
GRANT empire_consumer_optin_writer TO empire_consumer_optin_login
 WITH INHERIT FALSE, SET TRUE;
SQL
PYTHONPATH="$W" /srv/empire_os/.venv/bin/python -B \
  "$W/scripts/probe_consumer_private_login_ephemeral_20261021.py"
