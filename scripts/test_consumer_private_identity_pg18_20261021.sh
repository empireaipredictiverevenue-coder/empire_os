#!/usr/bin/env bash
# Real PostgreSQL SCRAM verifier + narrowly scoped login, DISPOSABLE DB ONLY.
set -euo pipefail
[[ "${PGHOST:-}" == localhost && "${PGPORT:-}" =~ ^[0-9]+$ ]] || exit 3
[[ "$PGPORT" -gt 5432 ]] || exit 3
[[ -z "${EMPIREDB_DSN:-}" ]] || exit 3
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
psql -X -v ON_ERROR_STOP=1 -d postgres <<'SQL' >/dev/null
CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE empiredb_app NOLOGIN;
CREATE ROLE empiredb_readonly NOLOGIN;
SQL
createdb -O empiredb_migrator -E UTF8 -T template0 empiredb
psql -X -v ON_ERROR_STOP=1 -d empiredb <<'SQL' >/dev/null
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO empiredb_app;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO empiredb_readonly;
SQL
psql -X -v ON_ERROR_STOP=1 -d empiredb -f "$W/migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d empiredb -c "CREATE ROLE empire_consumer_optin_writer NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d empiredb -f "$W/migrations/empiredb/059_consumer_optin_default_acl_seal_20261021.sql" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d empiredb -f "$W/migrations/empiredb/058_consumer_optin_private_role_staged_20261020.sql" >/dev/null
PYTHONPATH="$W" /srv/empire_os/.venv/bin/python -B \
 "$W/scripts/probe_consumer_identity_scram_ephemeral_20261021.py"
