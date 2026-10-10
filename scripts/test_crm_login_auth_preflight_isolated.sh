#!/usr/bin/env bash
# Disposable PostgreSQL-only verification. Never runs against the live cluster.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "${1:-}" != "--isolated-inner" ]]; then
 exec pg_virtualenv -v 18 bash "$0" --isolated-inner
fi
[[ -n "${PGPORT:-}" && "${PGPORT}" != "5432" ]] || exit 3
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 3
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'CREATE DATABASE empiredb'
psql -X -w -v ON_ERROR_STOP=1 -d empiredb -q <<'SQL'
CREATE TABLE public.empire_tenant_role_bindings(role_name name PRIMARY KEY);
CREATE TABLE public.empire_crm_tenant_memberships(
tenant_id uuid,subject text,status text,role text,revoked_at timestamptz,
verified_at timestamptz,valid_until timestamptz,evidence_ref text);
CREATE ROLE empire_crm_auth_login NOLOGIN NOINHERIT;
CREATE ROLE empire_crm_membership_login NOLOGIN NOINHERIT;
SQL
report="$(psql -X -w -v ON_ERROR_STOP=1 -d empiredb -At -f scripts/probe_crm_first_login_auth_readonly.sql)"
printf '%s' "$report" | grep -F 'empire.crm.first_login_auth_transport_preflight.v1' >/dev/null
printf '%s' "$report" | grep -F '"database_changes": false' >/dev/null
printf '%s' "$report" | grep -F 'STOP_RECONCILE_FOUNDER_MEMBERSHIP' >/dev/null
printf 'CRM_LOGIN_HBA_EPHEMERAL_QUERY=PASS\n'
printf 'CRM_LOGIN_HBA_LIVE_DATABASE_TOUCHED=NO\n'
