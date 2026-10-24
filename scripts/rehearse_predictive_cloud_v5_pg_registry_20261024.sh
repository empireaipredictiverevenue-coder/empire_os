#!/usr/bin/env bash
# Only disposable PostgreSQL 18; NO canonical EmpireDB operations.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?temporary PG host required}" "${PGPORT:?temporary PG port required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT>=5433 )) || exit 9
[[ "$PGHOST" == localhost ]] || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
psql -Xq -v ON_ERROR_STOP=1 -c 'CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS'
createdb empire_v5_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c 'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
file=migrations/empiredb/063_v5_whitelabel_candidate_registry_held.sql
rejected(){
 local expected="$1"; shift
 local report
 report="$(mktemp /tmp/empire_v5_063_rejected.XXXXXX)"
 if "$@" >"$report" 2>&1; then rm -f "$report";echo "UNEXPECTED_V5_ACCEPTANCE=$expected";exit 6; fi
 grep -Fq "$expected" "$report" || { cat "$report";rm -f "$report";exit 6; }
 rm -f "$report"
}
rejected 'V5_063_WRONG_DATABASE' psql -Xq -v ON_ERROR_STOP=1 -d postgres -f "$file"
psql -Xq -v ON_ERROR_STOP=1 -d empire_v5_fixture -f "$file"
rejected 'V5_063_EXISTING_REGISTRY_REQUIRES_REVIEW' psql -Xq -v ON_ERROR_STOP=1 -d empire_v5_fixture -f "$file"
query(){ psql -XAtq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c "$1"; }
[[ "$(query "SELECT count(*) FROM pg_class WHERE relname IN ('empire_v5_whitelabel_candidates_held','empire_v5_domain_candidates_held') AND relrowsecurity AND relforcerowsecurity")" == '2' ]]
[[ "$(query "SELECT count(*) FROM pg_policies WHERE tablename IN ('empire_v5_whitelabel_candidates_held','empire_v5_domain_candidates_held') AND roles::text LIKE '%empiredb_migrator%'")" == '2' ]]
query "CREATE ROLE v5_fixture_unprivileged NOLOGIN" >/dev/null
[[ "$(query "SELECT has_table_privilege('v5_fixture_unprivileged','public.empire_v5_whitelabel_candidates_held','SELECT'),has_table_privilege('v5_fixture_unprivileged','public.empire_v5_domain_candidates_held','INSERT')")" == 'f|f' ]]
A='00000000-0000-0000-0000-000000000101'
B='00000000-0000-0000-0000-000000000102'
for tenant in "$A" "$B"; do
 query "INSERT INTO public.empire_v5_whitelabel_candidates_held(tenant_id,display_name,accent_hex,logo_asset_digest,requested_plan)
 VALUES ('$tenant','Original Partner Labs','#3162AA',repeat('a',64),'enterprise')" >/dev/null
done
query "INSERT INTO public.empire_v5_domain_candidates_held(hostname,tenant_id)
 VALUES ('portal.partner.example.org','$A')" >/dev/null
rejected 'duplicate key value violates unique constraint' psql -XAtq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c "INSERT INTO public.empire_v5_domain_candidates_held(hostname,tenant_id)
 VALUES('portal.partner.example.org','$B')"
rejected 'violates check constraint' psql -XAtq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c "UPDATE public.empire_v5_domain_candidates_held SET activation_state='ACTIVE' WHERE hostname='portal.partner.example.org'"
rejected 'violates check constraint' psql -XAtq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c "UPDATE public.empire_v5_domain_candidates_held SET ownership_state='VERIFIED' WHERE tenant_id='$A'"
for bad_host in 'foo..example.org' 'foo.-invalid.org' 'foo.invalid-.org' 'foo.xn--host.org' 'portal.partner.invalid' 'admin.empire-ai.co.uk'; do
 rejected 'violates check constraint' psql -XAtq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c "INSERT INTO public.empire_v5_domain_candidates_held(hostname,tenant_id) VALUES('$bad_host','$A')"
done
rejected 'violates foreign key constraint' psql -XAtq -v ON_ERROR_STOP=1 -d empire_v5_fixture -c "INSERT INTO public.empire_v5_domain_candidates_held(hostname,tenant_id)
 VALUES('portal.unknown.example.org','00000000-0000-0000-0000-000000000999')"
[[ "$(query 'SELECT count(*) FROM public.empire_v5_domain_candidates_held')" == '1' ]]
echo 'V5_063_ISOLATED_TENANT_DOMAIN_UNIQUENESS_FORCE_RLS=PASS'
echo 'V5_063_UNTRUSTED_DOMAIN_CANNOT_ACTIVATE=PASS'
echo 'V5_063_FIXTURE_COMPLETE production_empiredb_writes=false live_domain_activated=false'
