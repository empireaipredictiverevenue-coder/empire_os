#!/usr/bin/env bash
# CRM exact three-role CONNECT grant, PostgreSQL 18 disposable cluster.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "${1:-}" != "--ephemeral-inner" ]]; then
 exec pg_virtualenv -v 18 bash "$0" --ephemeral-inner
fi
[[ -n "${PGPORT:-}" && "$PGPORT" != "5432" ]] || exit 3
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
hba="$(psql -X -w -At -d postgres -c 'SHOW hba_file')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 3
[[ "$hba" == /tmp/pg_virtualenv.*/postgresql/18/regress/pg_hba.conf ]] || exit 3
psql -X -w -q -v ON_ERROR_STOP=1 -d postgres -c 'CREATE DATABASE empiredb'
psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb <<'SQL'
CREATE ROLE postgres LOGIN SUPERUSER;
CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT;
SET password_encryption='scram-sha-256';
CREATE ROLE empire_crm_auth_login LOGIN NOINHERIT PASSWORD 'fixture-crm-auth-strong-secret';
CREATE ROLE empire_crm_membership_login LOGIN NOINHERIT PASSWORD 'fixture-crm-member-strong-secret';
CREATE ROLE empire_crm_tenant_708efd4b53b2 LOGIN NOINHERIT PASSWORD 'fixture-crm-reader-strong-secret';
GRANT empire_revenue_crm_reader TO empire_crm_tenant_708efd4b53b2 WITH INHERIT FALSE, SET TRUE;
CREATE TABLE public.empire_tenant_role_bindings (
 role_name name PRIMARY KEY, tenant_id uuid NOT NULL,
 active boolean NOT NULL, evidence_ref text NOT NULL);
CREATE TABLE public.empire_crm_tenant_memberships (
 tenant_id uuid NOT NULL, subject text NOT NULL,role text NOT NULL,
 status text NOT NULL, verified_at timestamptz,revoked_at timestamptz,
 valid_until timestamptz,evidence_ref text);
INSERT INTO public.empire_tenant_role_bindings VALUES
 ('empire_crm_tenant_708efd4b53b2',
 '708efd4b-53b2-43d7-961d-1cecab67f17a',true,'fixture:tenant');
SQL
psql -X -w -q -v ON_ERROR_STOP=1 -d postgres -c 'REVOKE CONNECT ON DATABASE empiredb FROM PUBLIC'
/srv/empire_os/.venv/bin/python - "$hba" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
p.write_bytes(b"local empiredb postgres trust\n"+p.read_bytes())
PY
psql -X -w -q -At -v ON_ERROR_STOP=1 -d postgres -c 'SELECT pg_reload_conf()' | grep -qx t
# Without canonical active founder membership the entire grant must fail.
if psql -X -w -U postgres -h /tmp -p "$PGPORT" -d empiredb     -v ON_ERROR_STOP=1 -f scripts/grant_crm_three_logins_connect.sql     >/dev/null 2>&1; then
 echo CRM_CONNECT_FIXTURE=UNSAFE_MEMBERSHIP_GUARD; exit 3
fi
psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb <<'SQL'
INSERT INTO public.empire_crm_tenant_memberships VALUES (
 '708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid,
 'founder:phil_livesley','owner','active',now(),NULL,NULL,'fixture:active-owner');
SQL
# Grant exact three role CONNECT rights, no other privilege types.
out="$(psql -X -w -q -At -U postgres -h /tmp -p "$PGPORT" -d empiredb -v ON_ERROR_STOP=1 -f scripts/grant_crm_three_logins_connect.sql)"
printf '%s' "$out" | grep -q 'CRM_CONNECT_RESULT=EXACT_THREE_ROLE_CONNECT_GRANT_COMMITTED'
for role in empire_crm_auth_login empire_crm_membership_login empire_crm_tenant_708efd4b53b2; do
 actual="$(psql -X -w -q -At -d empiredb -c "SELECT has_database_privilege('$role','empiredb','CONNECT'),has_database_privilege('$role','empiredb','CREATE')")"
 [[ "$actual" == 't|f' ]] || { echo CRM_CONNECT_FIXTURE=OVERBROAD_DATABASE_GRANT; exit 3; }
done
# Rerunning exact grant must fail closed, not execute again.
if psql -X -w -U postgres -h /tmp -p "$PGPORT" -d empiredb     -v ON_ERROR_STOP=1 -f scripts/grant_crm_three_logins_connect.sql     >/dev/null 2>&1; then
 echo CRM_CONNECT_FIXTURE=RERUN_NOT_BLOCKED; exit 3
fi
echo CRM_CONNECT_ISOLATED_ACTIVE_FOUNDER_GUARD=PASS
echo CRM_CONNECT_ISOLATED_ATOMIC_EXACT_THREE_GRANTS=PASS
echo CRM_CONNECT_ISOLATED_NO_CREATE_PRIVILEGE=PASS
echo CRM_CONNECT_ISOLATED_RERUN_FAIL_CLOSED=PASS
echo CRM_CONNECT_ISOLATED_PRODUCTION_DATABASE_TOUCHED=NO
