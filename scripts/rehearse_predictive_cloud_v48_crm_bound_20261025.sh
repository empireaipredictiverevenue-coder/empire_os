#!/usr/bin/env bash
# Predictive Cloud V4.8: original CRM041 + V4 held064 isolated PG18 evidence.
# No production migration, CRM access, live Redis, outreach, funds, or payments.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?temporary PG host required}" "${PGPORT:?temporary PG port required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
dir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c "
 CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
 CREATE ROLE empiredb_app NOLOGIN;
 CREATE ROLE empiredb_readonly NOLOGIN;
 CREATE ROLE empiredb_tenant_reader NOLOGIN;
 CREATE ROLE empire_revenue_crm_reader NOLOGIN;
 CREATE ROLE empire_crm_membership_login LOGIN NOINHERIT;
 CREATE ROLE untrusted_fixture_login LOGIN NOINHERIT;"
createdb -E UTF8 -T template0 crm_membership_fixture
createdb -E UTF8 -T template0 empire_v4_outbox_fixture
for database in crm_membership_fixture empire_v4_outbox_fixture; do
 psql -Xq -v ON_ERROR_STOP=1 -d "$database" -c \
  'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
done
psql -Xq -v ON_ERROR_STOP=1 -d crm_membership_fixture \
 -f migrations/empiredb/041_crm_membership_authority.sql
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture \
 -f migrations/empiredb/064_predictive_v4_projection_outbox_held.sql
# Fixture operator action ONLY. Real production 041 does not automatically
# create any account/role login, real owner membership or application grant.
psql -Xq -v ON_ERROR_STOP=1 -d crm_membership_fixture -c "
 GRANT EXECUTE ON FUNCTION public.empire_crm_read_member(text,uuid)
  TO empire_crm_membership_login;
 INSERT INTO public.empire_crm_tenant_memberships
 (tenant_id,subject,role,status,evidence_ref,verified_at)
 VALUES
 ('00000000-0000-0000-0000-000000000101','pilot:verified','viewer','active','fixture:owner-verified',now()),
 ('00000000-0000-0000-0000-000000000102','pilot:verified','viewer','disabled','fixture:disabled',now());"
# An arbitrary database identity cannot use the restricted CRM function.
err="$(mktemp /tmp/empire-v48-denied.XXXXXX)"
if psql -XAtq -v ON_ERROR_STOP=1 -d crm_membership_fixture \
 -c "SET ROLE untrusted_fixture_login;SELECT * FROM public.empire_crm_read_member('pilot:verified','00000000-0000-0000-0000-000000000101'::uuid);" >"$err" 2>&1; then
 echo V48_UNBOUND_LOGIN_UNEXPECTEDLY_AUTHORISED
 rm -f "$err"
 exit 7
fi
grep -q 'permission denied for function empire_crm_read_member' "$err"
rm -f "$err"
# Disposable SCRAM secret only: do NOT weaken pg_hba peer/SCRAM policy.
# The credential exists solely in this throwaway PostgreSQL 18 cluster.
V48_FIXTURE_PG_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
export V48_FIXTURE_PG_PASSWORD
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c \
 "ALTER ROLE empire_crm_membership_login PASSWORD '$V48_FIXTURE_PG_PASSWORD'"
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/rehearse_predictive_cloud_v48_crm_bound_20261025.py
echo 'V48_ORIGINAL_CRM_AND_HELD_OUTBOX_FIXTURE_COMPLETE production_db_modified=false redis_published=false payment_moved=false'
