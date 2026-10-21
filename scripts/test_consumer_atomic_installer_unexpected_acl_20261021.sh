#!/usr/bin/env bash
# Negative fixture: an unknown broad default grant must fail with no writes.
set -euo pipefail
[[ "${PGHOST:-}" == localhost && "${PGPORT:-}" =~ ^[0-9]+$ ]] || exit 3
[[ "$PGPORT" -gt 5432 ]] || exit 3
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_app NOLOGIN" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_readonly NOLOGIN" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE other_runtime NOLOGIN" >/dev/null
createdb -O empiredb_migrator -E UTF8 -T template0 empire_consumer_optin_fixture
psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture <<'SQL' >/dev/null
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO empiredb_app;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO empiredb_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO other_runtime;
SQL
if PYTHONPATH="$W" /srv/empire_os/.venv/bin/python -B \
    "$W/scripts/guarded_install_consumer_schema_20261021.py" --test-ephemeral;then
    echo "UNKNOWN_DEFAULT_TABLE_ROLE_UNSAFELY_ACCEPTED"
    exit 3
fi
readback=$(psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -tAc \
  "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname LIKE 'empire_consumer_%' AND c.relkind='r'")
[[ "$readback" == 0 ]] || { echo "UNEXPECTED_PARTIAL_SCHEMA";exit 3; }
role=$(psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -tAc \
  "SELECT count(*) FROM pg_roles WHERE rolname='empire_consumer_optin_writer'")
[[ "$role" == 0 ]] || { echo "UNEXPECTED_PARTIAL_WRITER";exit 3; }
echo "UNKNOWN_DEFAULT_GRANTEE_REJECTED_WITH_ZERO_DB_WRITES=true"
