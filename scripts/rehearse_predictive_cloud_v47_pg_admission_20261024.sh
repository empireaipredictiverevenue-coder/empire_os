#!/usr/bin/env bash
# Original Predictive Cloud V4.7: disposable PostgreSQL 18 dual-owner signing drill.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?isolated PGHOST required}" "${PGPORT:?isolated PGPORT required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c \
 'CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS'
createdb empire_v4_outbox_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c \
 'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f \
 migrations/empiredb/064_predictive_v4_projection_outbox_held.sql
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/rehearse_predictive_cloud_v47_pg_admission_20261024.py
echo 'V47_EPHEMERAL_DUAL_SIGNATURE_GAUNTLET_COMPLETE production_empiredb_writes=false new_production_roles=false'
