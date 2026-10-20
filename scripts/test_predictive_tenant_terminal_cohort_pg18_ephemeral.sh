#!/usr/bin/env bash
# Run ONLY under pg_virtualenv PostgreSQL 18. No canonical DB connections.
set -euo pipefail

OWNER="/home/ubuntu/empire_agents/predictive_decision_control_20261018"
ORIGINAL="/srv/empire_os"
if [[ "${PGHOST:-}" != "localhost" || -z "${PGPORT:-}" || "${PGPORT:-}" == "5432" ]]; then
    echo "TENANT_COHORT_EPHEMERAL_ONLY_REQUIRED"
    exit 8
fi

createdb empiredb
psql -X -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$ORIGINAL/tests/fixtures/verified_order_tenant_056_ephemeral.sql"
psql -X -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$ORIGINAL/migrations/empiredb/056_verified_order_tenant_reader_select_held.sql"
psql -X -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$OWNER/tests/fixtures/predictive_tenant_terminal_cohort_ephemeral.sql"

for role in order_fixture_a order_fixture_b; do
  env PGUSER="$role" PGPASSWORD="synthetic-pg18-test-only" \
    PYTHONPATH="$OWNER" PGCOHORT_FIXTURE=YES \
    /srv/empire_os/.venv/bin/python -B - <<'PY'
import os
from empire_os.predictive_tenant_terminal_cohort_reader import (
    read_tenant_terminal_candidates,
)
assert os.environ.get("PGCOHORT_FIXTURE") == "YES"
assert os.environ.get("PGHOST") == "localhost"
assert os.environ.get("PGPORT") != "5432"
role = os.environ["PGUSER"]
assert role in ("order_fixture_a","order_fixture_b")
dsn = ("dbname=empiredb host=localhost port=" + os.environ["PGPORT"] +
       " user=" + role)
r = read_tenant_terminal_candidates(dsn=dsn)
assert r["status"] == "AUTHENTICATED_TENANT_TERMINAL_CANDIDATES_UNVERIFIED", r
assert r["candidate_rows_observed"] == 1, r
assert r["candidate_terminal_wins"] == int(role=="order_fixture_b")
assert r["candidate_terminal_losses"] == int(role=="order_fixture_a")
assert r["candidate_revenue_events_present"] == int(role=="order_fixture_b")
assert r["source_rows_exported_to_scientific_training"] is False
assert r["database_writes"] is False
assert r["customer_forecast_eligible"] is False
print("PREDICTIVE_TENANT_COHORT_PG18_ISOLATION_PASS")
PY
done

psql -X -q -v ON_ERROR_STOP=1 -d empiredb -c "
  UPDATE public.empire_tenant_role_bindings SET active=false
  WHERE role_name='order_fixture_a';"
env PGUSER=order_fixture_a PGPASSWORD="synthetic-pg18-test-only" \
  PYTHONPATH="$OWNER" /srv/empire_os/.venv/bin/python -B - <<'PY'
import os
from empire_os.predictive_tenant_terminal_cohort_reader import (
    read_tenant_terminal_candidates,TenantCohortSourceHold
)
dsn=("dbname=empiredb host=localhost port="+os.environ["PGPORT"]+
     " user=order_fixture_a")
try:
    read_tenant_terminal_candidates(dsn=dsn)
except TenantCohortSourceHold:
    print("PREDICTIVE_TENANT_COHORT_REVOKED_BINDING_PASS")
else:
    raise AssertionError("revoked tenant was improperly admitted")
PY
echo "PREDICTIVE_TENANT_COHORT_PG18_EPHEMERAL_PASS"
