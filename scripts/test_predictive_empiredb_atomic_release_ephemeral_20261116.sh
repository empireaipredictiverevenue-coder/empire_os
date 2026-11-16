#!/usr/bin/env bash
# Atomic original three-migration release verification, isolated PostgreSQL 18.
# Disposes its small test cluster; no production connection or backup.
set -euo pipefail
export PATH=/usr/lib/postgresql/18/bin:/usr/bin:/bin
test "$(id -u)" != 0 || { echo REFUSE_ROOT_TEST_CLUSTER; exit 2; }
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d /tmp/empire-native-atomic-XXXXXXXX)"
trap 'pg_ctl -D "$tmp/data" -m immediate stop >/dev/null 2>&1 || :; rm -rf "$tmp"' EXIT
initdb -D "$tmp/data" -U ubuntu -A trust -E UTF8 --no-sync >/dev/null
mkdir "$tmp/socket"
pg_ctl -D "$tmp/data" -l "$tmp/log" \
  -o "-c listen_addresses= -c unix_socket_directories=$tmp/socket" start >/dev/null
export PGHOST="$tmp/socket" PGUSER=ubuntu
createdb empiredb
PYTHONPATH="$root" /srv/empire_os/.venv/bin/python - <<'PY'
import os
from pathlib import Path
import subprocess
from scripts.release_predictive_empiredb_native_once_20261116 import (
    load_pinned_migrations, build_atomic_sql, check_catalogue,
    READBACK_SQL, ReleaseHold,
)
root=Path(os.environ["PYTHONPATH"])
fixture=(root/"scripts/test_empiredb_rev077_ephemeral_20261115.sh").read_text()
assert fixture.count("<<'SQL'") >= 1
setup=fixture.split("<<'SQL'\n",1)[1].split("\nSQL\n",1)[0]
env=os.environ.copy()
def psql(sql):
    return subprocess.run(["psql","-X","-qAt","-v","ON_ERROR_STOP=1",
      "-d","empiredb"],input=sql,text=True,capture_output=True,env=env,timeout=18)
assert psql(setup).returncode==0,"DISPOSABLE_FIXTURE_SETUP_FAILED"
parts=load_pinned_migrations(root=root)
assert len(parts)==3
atomic=build_atomic_sql(parts)
assert atomic.startswith("BEGIN;")
assert atomic.endswith("COMMIT;\n")
assert atomic.count("RESET ROLE;")>=3
assert atomic.count("CREATE ROLE empire_predictive_")==2
# Simulate failure AFTER REV076 table/role creation, BEFORE REV077.
bad=build_atomic_sql((parts[0],
    "DO $$BEGIN RAISE EXCEPTION 'SIMULATED_ABORT'; END$$;\n"+parts[1],
    parts[2]))
failed=psql(bad)
assert failed.returncode!=0,"SIMULATED_ABORT_WAS_NOT_REJECTED"
rollback=psql("""SELECT (to_regclass('public.predictive_forecasts') IS NULL)
  AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_predictive_registry_reader')
  AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_predictive_forecast_registrar')
  AND to_regprocedure('public.read_predictive_revenue_day_v1(date,text)') IS NULL;""")
assert rollback.returncode==0 and rollback.stdout.strip()=="t",rollback.stdout
print("MID_RELEASE_FAILURE_ATOMIC_ROLLBACK=PASS")
result=psql(atomic)
assert result.returncode==0,result.stderr[-1000:]
assert "NATIVE_PREDICTIVE_RELEASE_COMMITTED_SCHEMA_ONLY" in result.stdout,result.stdout
catalog=psql("""SELECT (SELECT relrowsecurity AND relforcerowsecurity
 FROM pg_class WHERE oid='public.predictive_forecasts'::regclass)
 AND (SELECT count(*)=0 FROM public.predictive_forecasts)
 AND to_regprocedure('public.read_predictive_revenue_day_v1(date,text)') IS NOT NULL
 AND to_regprocedure('public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)') IS NOT NULL;""")
assert catalog.returncode==0 and catalog.stdout.strip()=="t",catalog.stderr
readback=psql(READBACK_SQL)
assert readback.returncode==0 and readback.stdout.strip()=="t",readback.stderr
print("INDEPENDENT_POSTCOMMIT_RLS_ROLE_AND_EMPTY_REGISTRY=PASS")
print("ALL_THREE_ORIGINAL_DDL_ATOMIC_SCHEMA_AND_RLS=PASS")
reapply=psql(atomic)
assert reapply.returncode!=0,"REPEAT_RELEASE_DID_NOT_FAIL_CLOSED"
again=psql("SELECT count(*) FROM public.predictive_forecasts;")
assert again.returncode==0 and again.stdout.strip()=="0"
print("RELEASE_REAPPLY_FAILS_WITHOUT_DATA_CHANGES=PASS")
try:
    check_catalogue('{"canonical":true}')
except ReleaseHold:
    print("INCOMPLETE_LIVE_CATALOGUE_FAIL_CLOSED=PASS")
else:
    raise AssertionError("CATALOGUE_BYPASS")
print("DISPOSABLE_PRODUCTION_RELEASE_OPERATOR_TEST=PASS")
PY
