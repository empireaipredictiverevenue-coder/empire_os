#!/usr/bin/env bash
# Sovereign EmpireDB 047->048 default-ACL regression, DISPOSABLE PG18 only.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" -eq 0 ]]; then
  exec pg_virtualenv -v 18 bash "$0" --isolated-postgres-only
fi
[[ "$1" == "--isolated-postgres-only" && -n "${PGPORT:-}" && "$PGPORT" != 5432 ]] || exit 70
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 71
pg() { psql -X -w -v ON_ERROR_STOP=1 -d direct_bsc_capability_fixture "$@"; }
psql -X -w -v ON_ERROR_STOP=1 -d postgres <<'SQL' >/dev/null
CREATE ROLE empiredb_migrator NOLOGIN INHERIT;
CREATE ROLE empiredb_tenant_reader NOLOGIN NOINHERIT;
GRANT empiredb_tenant_reader TO empiredb_migrator WITH INHERIT TRUE, SET TRUE, ADMIN FALSE;
CREATE ROLE empiredb_app NOLOGIN NOINHERIT;
CREATE ROLE empiredb_readonly NOLOGIN NOINHERIT;
CREATE ROLE empire_payment_approver NOLOGIN NOINHERIT;
CREATE ROLE empire_bsc_verifier NOLOGIN NOINHERIT;
CREATE ROLE extra_observer NOLOGIN NOINHERIT;
CREATE DATABASE direct_bsc_capability_fixture;
SQL
pg <<'SQL' >/dev/null
CREATE TABLE public.fulfilment_orders (
 id uuid PRIMARY KEY, buyer_id uuid NOT NULL, state text NOT NULL
);
CREATE TABLE public.bsc_payment_requests (
 id uuid PRIMARY KEY, buyer_id uuid NOT NULL,
 fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id),
 settlement_mode text NOT NULL, status text NOT NULL,
 created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL
);
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
GRANT SELECT,REFERENCES ON public.fulfilment_orders,public.bsc_payment_requests TO empiredb_migrator;
-- Clone EXACT unexpected production DEFAULT privilege behaviour.
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO empiredb_app;
ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public
 GRANT SELECT ON TABLES TO empiredb_readonly;
SQL
original_defaults="$(pg -At -c "SELECT COALESCE(string_agg(owner.rolname||':'||COALESCE(ns.nspname,'GLOBAL')||':'||g.oid::text||':'||a.privilege_type,',' ORDER BY owner.rolname,ns.nspname,g.oid,a.privilege_type),'EMPTY') FROM pg_catalog.pg_default_acl d JOIN pg_catalog.pg_roles owner ON owner.oid=d.defaclrole LEFT JOIN pg_catalog.pg_namespace ns ON ns.oid=d.defaclnamespace CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a JOIN pg_catalog.pg_roles g ON g.oid=a.grantee WHERE owner.rolname='empiredb_migrator' AND d.defaclobjtype='r'")"
[[ "$original_defaults" != EMPTY ]] || { echo 'FAIL_DEFAULT_PRIVILEGES_SETUP';exit 72; }
pg -f migrations/empiredb/047_direct_bsc_buyer_status_capability.sql >/dev/null
before="$(pg -At -c "SELECT has_table_privilege('empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')::int||'|'||has_table_privilege('empiredb_readonly','public.direct_bsc_buyer_capabilities','SELECT')::int")"
[[ "$before" == '1|1' ]] || { echo 'FAIL_TO_REPRODUCE_PRODUCTION_GRANT';exit 73; }
report="$(pg -f scripts/inspect_direct_bsc_capability_047_postcommit.sql)"
printf '%s\n' "$report" | grep -Eq '03_app_select_denied[[:space:]]*\\|[[:space:]]*FAIL' ||
  { echo 'FAIL_FORENSIC_MISMATCH_NOT_REPRODUCED';exit 74; }
echo "EPHEMERAL_ORIGINAL_047_DEFAULT_GRANT_DEFECT=REPRODUCED"

# Test fail-close: unknown third-party grantee must abort before revocations.
pg -c 'GRANT SELECT ON public.direct_bsc_buyer_capabilities TO extra_observer' >/dev/null
log="$(mktemp)"
if pg -f migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql >"$log" 2>&1; then
  rm -f "$log"; echo "FAIL_048_ACCEPTED_UNEXPECTED_GRANTEE";exit 75
fi
grep -q 'DIRECT048_EXACT_EXISTING_GRANTS_DRIFT' "$log" ||
  { rm -f "$log";echo "FAIL_048_DID_NOT_IDENTIFY_GRANT_DRIFT";exit 76; }
rm -f "$log"
[[ "$(pg -At -c "SELECT has_table_privilege('empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')::int")" == 1 ]] ||
  { echo "FAIL_048_PARTIAL_COMMIT_ON_ERROR";exit 77; }
pg -c 'REVOKE SELECT ON public.direct_bsc_buyer_capabilities FROM extra_observer' >/dev/null
echo "EPHEMERAL_048_EXTRA_GRANT_ATOMIC_ROLLBACK=PASS"

pg -f migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql >/dev/null
after="$(pg -At -c "SELECT has_table_privilege('empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')::int||'|'||has_table_privilege('empiredb_readonly','public.direct_bsc_buyer_capabilities','SELECT')::int")"
[[ "$after" == '0|0' ]] || { echo 'FAIL_048_ACCESS_UNSEALED';exit 78; }
report="$(pg -f scripts/inspect_direct_bsc_capability_047_postcommit.sql)"
passed="$(printf '%s\n' "$report" | grep -Ec '^[[:space:]]*0[1-9]_[[:alnum:]_]+[[:space:]]*\\|[[:space:]]*PASS[[:space:]]*$' || true)"
[[ "$passed" == 9 ]] || { echo 'FAIL_048_NINE_SECURITY_CHECKS';exit 79; }
now_defaults="$(pg -At -c "SELECT COALESCE(string_agg(owner.rolname||':'||COALESCE(ns.nspname,'GLOBAL')||':'||g.oid::text||':'||a.privilege_type,',' ORDER BY owner.rolname,ns.nspname,g.oid,a.privilege_type),'EMPTY') FROM pg_catalog.pg_default_acl d JOIN pg_catalog.pg_roles owner ON owner.oid=d.defaclrole LEFT JOIN pg_catalog.pg_namespace ns ON ns.oid=d.defaclnamespace CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a JOIN pg_catalog.pg_roles g ON g.oid=a.grantee WHERE owner.rolname='empiredb_migrator' AND d.defaclobjtype='r'")"
[[ "$now_defaults" == "$original_defaults" ]] ||
 { echo 'FAIL_048_CHANGED_EXISTING_DEFAULT_GRANTS';exit 80; }
echo "EPHEMERAL_048_ALL_NINE_SECURITY_CHECKS=PASS"
echo "EPHEMERAL_048_ORIGINAL_DEFAULT_GRANTS_UNCHANGED=PASS"

# A second migration invocation must fail rather than silently broaden scope.
if pg -f migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql >/dev/null 2>&1; then
  echo 'FAIL_048_REPEATED_APPLY_NOT_HELD';exit 81
fi
echo "EPHEMERAL_048_REPEAT_EXECUTION=BLOCKED"
echo "PRODUCTION_DATABASE_ACCESSED=NO"
echo "PRODUCTION_MIGRATION_APPLIED=NO"
