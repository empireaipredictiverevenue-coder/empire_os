#!/usr/bin/env bash
# Execute CRM046 SQL in a *throw-away* PostgreSQL 18 instance, NEVER production.
set -euo pipefail
cd /srv/empire_os
if [[ "${1:-}" != "--ephemeral-inner" ]]; then
  exec pg_virtualenv -v 18 bash "$0" --ephemeral-inner
fi
[[ -n "${PGPORT:-}" && "${PGPORT}" != "5432" ]] || {
  echo CRM046_FIXTURE=REFUSE_NON_EPHEMERAL_PORT >&2; exit 2;
}
fixture_data_dir="$(psql -X -w -v ON_ERROR_STOP=1 -d postgres -At -c 'SHOW data_directory')" || exit 2
[[ "$fixture_data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || {
  echo CRM046_FIXTURE=REFUSE_NON_EPHEMERAL_DATA_DIRECTORY >&2; exit 2;
}
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c "CREATE DATABASE crm_suppression_fixture"
psql -X -w -v ON_ERROR_STOP=1 -d crm_suppression_fixture -q -f tests/crm046_isolated_fixture.sql
psql -X -w -v ON_ERROR_STOP=1 -d crm_suppression_fixture -q -f migrations/empiredb/046_crm_prospect_suppression_hit.sql
tenant_a="$(psql -X -w -v ON_ERROR_STOP=1 -d crm_suppression_fixture -At <<'SQL'
SET SESSION AUTHORIZATION crm046_fixture_tenant;
SET ROLE empire_revenue_crm_reader;
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000201'::uuid,'sms');
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000202'::uuid,'sms');
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000203'::uuid,'sms');
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000204'::uuid,'sms');
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000201'::uuid,'email');
SELECT public.empire_crm_prospect_suppression_hit(NULL::uuid,'sms');
SELECT has_column_privilege(current_user,'public.prospects','phone','SELECT')::int;
SELECT has_table_privilege(current_user,'public.outbound_suppressions','SELECT')::int;
SQL
)"
expected_a=$'SET\nSET\nSUPPRESSED\nUNKNOWN\nUNKNOWN\nUNKNOWN\nUNKNOWN\nUNKNOWN\n0\n0'
[[ "$tenant_a" == "$expected_a" ]] || {
  printf 'CRM046_FIXTURE_TENANT_A_FAILED\n%s\n' "$tenant_a" >&2; exit 3;
}
tenant_b="$(psql -X -w -v ON_ERROR_STOP=1 -d crm_suppression_fixture -At <<'SQL'
SET SESSION AUTHORIZATION crm046_fixture_other;
SET ROLE empire_revenue_crm_reader;
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000201'::uuid,'sms');
SELECT public.empire_crm_prospect_suppression_hit('00000000-0000-0000-0000-000000000203'::uuid,'sms');
SQL
)"
[[ "$tenant_b" == $'SET\nSET\nUNKNOWN\nSUPPRESSED' ]] || {
  printf 'CRM046_FIXTURE_TENANT_B_FAILED\n%s\n' "$tenant_b" >&2; exit 3;
}
# Verify no PUBLIC or third-party role can execute the function.
privileges="$(psql -X -w -v ON_ERROR_STOP=1 -d crm_suppression_fixture -At -c "
SELECT
  (SELECT prosecdef AND provolatile='s' FROM pg_proc WHERE oid=to_regprocedure('public.empire_crm_prospect_suppression_hit(uuid,text)'))::int
  ||'|'||has_function_privilege('empire_revenue_crm_reader','public.empire_crm_prospect_suppression_hit(uuid,text)','EXECUTE')::int
  ||'|'||(SELECT EXISTS (
    SELECT 1 FROM pg_proc p,
    LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) acl
    WHERE p.oid=to_regprocedure('public.empire_crm_prospect_suppression_hit(uuid,text)')
      AND acl.grantee=0 AND acl.privilege_type='EXECUTE'
  ))::int
")"
[[ "$privileges" == '1|1|0' ]] || {
 echo 'CRM046_FIXTURE_PRIVILEGES_FAILED' >&2; exit 3;
}
printf 'CRM046_ISOLATED_POSTGRESQL18_FIXTURE=PASS\n'
printf 'CRM046_TENANT_A_SUPPRESSED=PASS\nCRM046_CROSS_TENANT_HOLD=PASS\n'
printf 'CRM046_TENANT_B_SUPPRESSED=PASS\nCRM046_NO_HIT_STAYS_UNKNOWN=PASS\n'
printf 'CRM046_EMAIL_UNSUPPORTED=PASS\nCRM046_RAW_CONTACT_ACL_DENIED=PASS\n'
printf 'CRM046_RESTRICTED_FUNCTION_ACL=PASS\n'
