#!/usr/bin/env bash
# Executes ONLY inside pg_virtualenv PostgreSQL 18; no live db connection.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${PGPORT:-}" == "" || "${PGPORT}" == 5432 || "${PGHOST:-}" != "localhost" ]]; then
  echo "ORDER056_EPHEMERAL_ONLY_REQUIRED"; exit 8
fi

createdb empiredb
psql -X -q -v ON_ERROR_STOP=1 -d empiredb -f "$ROOT/tests/fixtures/verified_order_tenant_056_ephemeral.sql"
psql -X -q -v ON_ERROR_STOP=1 -d empiredb -f "$ROOT/migrations/empiredb/056_verified_order_tenant_reader_select_held.sql"

for role in order_fixture_a order_fixture_b; do
  # Connection must be as tenant LOGIN, not SET ROLE from the superuser.
  result="$(env PGUSER="$role" PGPASSWORD="synthetic-pg18-test-only" psql -X -qAt -v ON_ERROR_STOP=1 -d empiredb -c "
    BEGIN READ ONLY;
    SET LOCAL ROLE empiredb_tenant_reader;
    SELECT (public.empire_current_tenant_id() IS NOT NULL)::int,
      (SELECT count(*) FROM public.buyers),
      (SELECT count(*) FROM public.fulfilment_orders),
      (SELECT count(*) FROM public.commercial_outcomes),
      (SELECT count(*) FROM public.commercial_events),
      (SELECT count(*) FROM public.bsc_payment_requests),
      (SELECT count(*) FROM public.bsc_payment_evidence),
      (SELECT count(*) FROM public.bsc_escrow_agreements),
      (SELECT count(*) FROM public.bsc_escrow_evidence),
      pg_catalog.has_table_privilege(current_user,'public.commercial_outcomes','INSERT')::int;
    ROLLBACK;" | head -1)"
  if [[ "$result" != '1|1|1|1|0|1|1|1|1|0' ]]; then
    echo "ORDER056_TENANT_PARTITION_FAILURE"; exit 9
  fi
  echo "ORDER056_TENANT_ISOLATION_OK"
done

env PGUSER=order_fixture_a PGPASSWORD="synthetic-pg18-test-only" \
  ORDER056_EPHEMERAL_FIXTURE=YES PYTHONPATH="$ROOT" \
  /srv/empire_os/.venv/bin/python -B -m scripts.test_verified_order_tenant_python_ephemeral

# Disable tenant A's binding. Session_user must lose access immediately.
psql -X -q -v ON_ERROR_STOP=1 -d empiredb -c "
  UPDATE public.empire_tenant_role_bindings SET active=false
  WHERE role_name='order_fixture_a';"
disabled="$(env PGUSER=order_fixture_a PGPASSWORD="synthetic-pg18-test-only" psql -X -qAt -v ON_ERROR_STOP=1 -d empiredb -c "
  BEGIN READ ONLY;
  SET LOCAL ROLE empiredb_tenant_reader;
  SELECT (public.empire_current_tenant_id() IS NULL)::int,
         (SELECT count(*) FROM public.bsc_payment_evidence),
         (SELECT count(*) FROM public.commercial_outcomes),
         (SELECT count(*) FROM public.bsc_escrow_evidence);
  ROLLBACK;" | head -1)"
if [[ "$disabled" != '1|0|0|0' ]]; then
  echo "ORDER056_REVOKED_TENANT_VISIBLE_FAILURE"; exit 10
fi
echo "ORDER056_REVOKED_BINDING_HOLD_OK"
echo "ORDER056_EPHEMERAL_PASS"
