#!/usr/bin/env bash
# EmpireOS V4.10: ephemeral PG18 research; NO production migrations.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?PGHOST required}" "${PGPORT:?PGPORT required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c "
 CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
 CREATE ROLE empire_predictive_rights_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
 CREATE ROLE empire_predictive_rights_login LOGIN INHERIT;
 CREATE ROLE untrusted_rights_fixture_login LOGIN INHERIT;
 GRANT empire_predictive_rights_reader TO empire_predictive_rights_login;"
createdb -E UTF8 -T template0 empire_v4_outbox_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c \
 'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f \
 migrations/empiredb/066_predictive_source_rights_inventory_held.sql
V410_PG_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
export V410_PG_PASSWORD
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c \
 "ALTER ROLE empire_predictive_rights_login PASSWORD '$V410_PG_PASSWORD'"
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/rehearse_predictive_cloud_v410_source_rights_20261025.py
echo 'V410_EPHEMERAL_HELD_RIGHTS_ONLY production_empiredb_modified=false'
