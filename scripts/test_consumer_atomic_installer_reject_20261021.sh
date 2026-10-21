#!/usr/bin/env bash
# Negative integration test: rejects unsafe role without partial DB setup.
set -euo pipefail
[[ "${PGHOST:-}" == localhost && "${PGPORT:-}" =~ ^[0-9]+$ ]] || exit 3
[[ "$PGPORT" -gt 5432 ]] || exit 3
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS" >/dev/null
# A role with LOGIN must be refused rather than silently downgraded.
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empire_consumer_optin_writer LOGIN" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_app NOLOGIN" >/dev/null
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_readonly NOLOGIN" >/dev/null
createdb -O empiredb_migrator -E UTF8 -T template0 empire_consumer_optin_fixture
if psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture <<'SQL' >/dev/null
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO empiredb_app;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO empiredb_readonly;
SQL
PYTHONPATH="$W" /srv/empire_os/.venv/bin/python -B \
    "$W/scripts/guarded_install_consumer_schema_20261021.py" --test-ephemeral;then
    echo "UNSAFE_ROLE_WAS_ACCEPTED"
    exit 3
fi
readback=$(psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -tAc \
  "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname LIKE 'empire_consumer_%' AND c.relkind='r'")
[[ "$readback" == 0 ]] || { echo "UNEXPECTED_PARTIAL_SCHEMA";exit 3; }
echo "NONCOMPLIANT_ROLE_REJECTED_WITH_ZERO_TABLE_WRITES=true"
