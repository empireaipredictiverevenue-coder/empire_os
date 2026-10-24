#!/usr/bin/env bash
# ORIGINAL EMPIREOS: isolated test-only ASTRA signed gateway -> held 059 ledger.
# NEVER run against original production EmpireDB or an unverified PostgreSQL.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?pg_virtualenv disposable port required}"
: "${PGHOST:?pg_virtualenv host required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && ((PGPORT >= 5433)) || {
 echo "REFUSED_NON_EPHEMERAL_PGPORT"; exit 9;
}
[[ "$PGHOST" == localhost || "$PGHOST" == 127.0.0.1 || "$PGHOST" == "::1" ]] || {
 echo "REFUSED_UNEXPECTED_POSTGRES_HOST"; exit 9;
}
export PGDATABASE=postgres
directory="$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'SHOW data_directory')"
[[ "$directory" == /tmp/pg_virtualenv.*/data/18/regress ]] || {
 echo "REFUSED_NON_TEMPORARY_POSTGRES_DATA_DIR"; exit 9;
}
[[ "$(psql -X -Atq -c 'select inet_server_port()')" == "$PGPORT" ]] || {
 echo "REFUSED_MISMATCHED_POSTGRES_SERVER"; exit 9;
}
createdb empire_timer_fixture
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;"
for part in \
  057_flagship_voice_timer_ledger_held \
  058_flagship_timer_atomic_transition_held \
  059_flagship_timer_provider_receipt_custody_held; do
  psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "migrations/empiredb/${part}.sql" >/dev/null
done
export PGDATABASE=empire_timer_fixture
export EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED=ephemeral
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
    scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py
echo "SIGNED_GATEWAY_059_PG_FIXTURE_FINISHED production_touched=false provider_network_calls=0"
