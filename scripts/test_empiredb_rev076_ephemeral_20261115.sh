#!/usr/bin/env bash
# Disposable PostgreSQL 18 fixture only. Never touches production EmpireDB.
set -euo pipefail
export PATH=/usr/lib/postgresql/18/bin:/usr/bin:/bin
test "$(id -u)" != 0 || { echo REFUSE_ROOT_FIXTURE; exit 2; }
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d /tmp/empiredb-rev076-XXXXXXXX)"
trap 'pg_ctl -D "$tmp/data" -m immediate stop >/dev/null 2>&1 || :; rm -rf "$tmp"' EXIT
initdb -D "$tmp/data" -U ubuntu -A trust --no-sync >/dev/null
mkdir "$tmp/socket"
pg_ctl -D "$tmp/data" -l "$tmp/log" -o "-c listen_addresses= -c unix_socket_directories=$tmp/socket" start >/dev/null
export PGHOST="$tmp/socket" PGUSER=ubuntu
createdb empiredb
psql -X -v ON_ERROR_STOP=1 -q -d empiredb <<'SQL'
CREATE ROLE empiredb_migrator NOLOGIN;
GRANT CREATE ON SCHEMA public TO empiredb_migrator;
CREATE TABLE public.empire_tenant_role_bindings(role_name name PRIMARY KEY,tenant_id uuid NOT NULL,active boolean DEFAULT true);
ALTER TABLE public.empire_tenant_role_bindings OWNER TO empiredb_migrator;
CREATE FUNCTION public.empire_current_tenant_id() RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
  SELECT tenant_id FROM public.empire_tenant_role_bindings WHERE role_name=session_user AND active LIMIT 1
$$;
ALTER FUNCTION public.empire_current_tenant_id() OWNER TO empiredb_migrator;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
SQL
psql -X -v ON_ERROR_STOP=1 -q -d empiredb -f "$root/migrations/empiredb/076_predictive_forecast_registry_native_held.sql"
psql -X -v ON_ERROR_STOP=1 -q -d empiredb <<'SQL'
CREATE ROLE tenant_a LOGIN NOINHERIT;
CREATE ROLE tenant_b LOGIN NOINHERIT;
CREATE ROLE tenant_unknown LOGIN NOINHERIT;
GRANT empire_predictive_registry_reader TO tenant_a,tenant_b,tenant_unknown;
INSERT INTO public.empire_tenant_role_bindings(role_name,tenant_id) VALUES
 ('tenant_a','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('tenant_b','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.predictive_forecasts(
forecast_key,model_name,model_version,metric,dimension_key,horizon_days,
sample_count,predicted_value,r_squared,evidence_confidence,direction,source)
VALUES
('a1','empire','v1','recognized_revenue_cents','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',7,10,100,0.8,0.7,'up','fixture'),
('b1','empire','v1','recognized_revenue_cents','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',7,10,200,0.8,0.7,'up','fixture');
SQL
for who in tenant_a tenant_b tenant_unknown; do
 n="$(psql -X -v ON_ERROR_STOP=1 -qAt -U "$who" -d empiredb -c 'BEGIN READ ONLY; SET LOCAL ROLE empire_predictive_registry_reader; SELECT count(*) FROM public.predictive_forecasts; ROLLBACK;' | grep -E '^[0-9]+$' | tail -1)"
 if test "$who" = tenant_unknown; then expected=0; else expected=1; fi
 test "$n" = "$expected" || { echo TENANT_ISOLATION_FAILED; exit 3; }
 echo "ISOLATION_$who=$n"
done
if psql -X -v ON_ERROR_STOP=1 -q -U tenant_a -d empiredb -c "BEGIN; SET LOCAL ROLE empire_predictive_registry_reader; DELETE FROM public.predictive_forecasts WHERE forecast_key='a1'; ROLLBACK;" >/dev/null 2>&1; then
 echo UNAUTHORIZED_DELETE_WAS_ALLOWED; exit 4
fi
r="$(psql -X -qAt -d empiredb -c "SELECT relrowsecurity::text || ':' || relforcerowsecurity::text FROM pg_catalog.pg_class WHERE oid='public.predictive_forecasts'::regclass")"
test "$r" = "true:true" || { echo FORCE_RLS_FAILED; exit 5; }
echo REV076_DISPOSABLE_POSTGRESQL18_PASS
