#!/usr/bin/env bash
# EmpireDB 047 — separate founder approval required; SEALED buyer capability only.
# Nothing in this script authorises buyer API, public access, or money handling.
set -euo pipefail
umask 077
fail() { printf 'DIRECT047_STATUS=HELD reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" && "$2" == "--approved-047-sealed-buyer-capability-only" ]] ||
  fail "EXACT_FOUNDER_MIGRATION_APPROVAL_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || fail "ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os
SQL=migrations/empiredb/047_direct_bsc_buyer_status_capability.sql
PREFLIGHT=/srv/empire_os/scripts/inspect_direct_bsc_capability_migration.py
[[ -f "$SQL" && -f "$PREFLIGHT" ]] || fail "REVIEWED_SOURCE_MISSING"
[[ -z "$(git status --porcelain -- "$SQL" "$PREFLIGHT")" ]] || fail "REVIEWED_SOURCE_DIRTY"
[[ "$(git hash-object "$SQL")" == "$(git rev-parse "HEAD:$SQL" 2>/dev/null)" ]] ||
  fail "SQL_BLOB_NOT_COMMITTED"
[[ "$(git hash-object "$PREFLIGHT")" == "$(git rev-parse "HEAD:scripts/inspect_direct_bsc_capability_migration.py" 2>/dev/null)" ]] ||
  fail "PREFLIGHT_BLOB_NOT_COMMITTED"
for c in runuser psql pg_dump pg_dumpall pg_restore pg_isready flock df sha256sum systemctl curl; do
  command -v "$c" >/dev/null || fail "DEPENDENCY_MISSING"
done
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] ||
  fail "CANONICAL_POSTGRESQL_SERVICE_INACTIVE"
[[ -f /etc/empiredb.env ]] || fail "CANONICAL_APP_DSN_ENV_MISSING"
exec 9>/run/lock/empiredb-direct047-sealed.lock
flock -n -x 9 || fail "DIRECT047_DEPLOYMENT_ALREADY_RUNNING"
export PGHOST=/var/run/postgresql PGPORT=5432
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
pg() { runuser -u postgres -- psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg "SELECT current_database()")" == empiredb ]] || fail "WRONG_DATABASE"
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] ||
  fail "NONCANONICAL_POSTGRESQL_CLUSTER"
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] || fail "NOT_PRIMARY"
pg_isready -q -d empiredb || fail "POSTGRESQL_NOT_READY"

# Recheck all v2 membership security gates in a *separate read-only* session.
PREFLIGHT_RESULT="$(runuser -u postgres -- /srv/empire_os/.venv/bin/python \
  -m scripts.inspect_direct_bsc_capability_migration --preflight)" ||
  fail "READONLY_CATALOG_PREFLIGHT_HELD"
[[ "$(printf '%s' "$PREFLIGHT_RESULT" | /srv/empire_os/.venv/bin/python -c '
import sys,json
p=json.load(sys.stdin)
print("PASS" if (
 p.get("status")=="READY_FOR_SEPARATELY_APPROVED_CAPABILITY_MIGRATION"
 and p.get("schema_version")=="empire.direct-bsc-buyer-capability-migration-preflight.v2"
 and p.get("mode")=="READ_ONLY" and p.get("migration_applied") is False
 and p.get("exact_existing_tenant_reader_membership") is True
 and p.get("no_transitive_reader_memberships") is True
 and p.get("tenant_reader_role_restricted") is True
 and p.get("restricted_migrator") is True
) else "HELD")')" == PASS ]] || fail "PRE_FLIGHT_CATALOG_RESPONSE_UNSAFE"
printf 'DIRECT047_PRODUCTION_PREFLIGHT=PASS\n'

# The app and root operator must point at the SAME canonical running cluster.
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || fail "CANONICAL_APP_DSN_MISSING"
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
 import psycopg
 with psycopg.connect(os.environ["EMPIREDB_DSN"],connect_timeout=5) as conn:
  with conn.cursor() as cur:
   cur.execute("SET TRANSACTION READ ONLY")
   cur.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
   result=cur.fetchone()
   print(result[0] if result else "UNVERIFIED")
except Exception:
 print("UNVERIFIED")
PY
)" || fail "CANONICAL_APP_INSTANCE_UNAVAILABLE"
[[ "$local_instance" == "$app_instance" ]] || fail "APPLICATION_DATABASE_MISMATCH"
unset EMPIREDB_DSN

db_size="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$db_size" =~ ^[0-9]+$ ]] || fail "DB_SIZE_UNAVAILABLE"
BACKUP_BASE=/var/backups/empiredb/direct-bsc-buyer-capability-047
[[ ! -L "$BACKUP_BASE" ]] || fail "BACKUP_PATH_SYMLINK"
install -d -o root -g root -m 0700 "$BACKUP_BASE"
[[ "$(stat -c '%u:%g:%a' "$BACKUP_BASE")" == '0:0:700' ]] ||
  fail "BACKUP_BASE_PERMISSIONS_UNSAFE"
free="$(df -PB1 "$BACKUP_BASE" | awk 'NR==2 {print $4}')"
[[ "$free" =~ ^[0-9]+$ ]] || fail "BACKUP_FREE_SPACE_UNKNOWN"
(( free >= db_size * 2 + 536870912 )) || fail "BACKUP_INSUFFICIENT_SPACE"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dir="$BACKUP_BASE/$stamp"
[[ ! -e "$dir" && ! -L "$dir" ]] || fail "BACKUP_DIRECTORY_CONFLICT"
install -d -o root -g root -m 0700 "$dir"
printf 'DIRECT047_BACKUP_STARTED=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb > "$dir/empiredb-pre-047.dump" ||
  fail "BACKUP_FAILED_DO_NOT_APPLY"
runuser -u postgres -- pg_dumpall -w --globals-only > "$dir/globals-pre-047.sql" ||
  fail "GLOBALS_BACKUP_FAILED_DO_NOT_APPLY"
[[ -s "$dir/empiredb-pre-047.dump" && -s "$dir/globals-pre-047.sql" ]] ||
  fail "EMPTY_BACKUP_DO_NOT_APPLY"
pg_restore --list "$dir/empiredb-pre-047.dump" > "$dir/restore-list.txt" ||
  fail "CORRUPT_DATABASE_BACKUP_DO_NOT_APPLY"
grep -q 'TABLE.*public.*fulfilment_orders' "$dir/restore-list.txt" ||
  fail "ORDER_SOURCE_NOT_BACKED_UP"
grep -q 'TABLE.*public.*bsc_payment_requests' "$dir/restore-list.txt" ||
  fail "PAYMENT_SOURCE_NOT_BACKED_UP"
(cd "$dir" && sha256sum empiredb-pre-047.dump globals-pre-047.sql restore-list.txt > SHA256SUMS &&
 sha256sum -c SHA256SUMS >/dev/null) || fail "BACKUP_HASH_NOT_VERIFIED"
chmod 0600 "$dir"/*
printf 'DIRECT047_BACKUP=VERIFIED\nDIRECT047_BACKUP_LOCATION=%s\n' "$dir"
printf 'DIRECT047_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# SQL migration includes BEGIN/COMMIT and independent exact-role-membership
# validation BEFORE touching a table. Failed transaction rolls back atomically.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$SQL" > "$dir/migration-stdout.log" 2> "$dir/migration-stderr.log"; then
  chmod 0600 "$dir/migration-stdout.log" "$dir/migration-stderr.log" 2>/dev/null || true
  printf 'DIRECT047_STATUS=SQL_ABORTED_INSPECT_PRIVATE_LOG_DO_NOT_RETRY\n' >&2
  printf 'DIRECT047_PRIVATE_LOG=%s\n' "$dir/migration-stderr.log" >&2
  exit 4
fi
printf 'DIRECT047_SQL_TRANSACTION=COMMITTED\n'

# Read-only postcommit privilege and sealing proof, not merely successful SQL.
post="$(pg "
SELECT
 (to_regclass('public.direct_bsc_buyer_capabilities') IS NOT NULL)::int
 ||'|'||
 COALESCE((SELECT (c.relrowsecurity AND c.relforcerowsecurity)::int
 FROM pg_catalog.pg_class c
 WHERE c.oid=to_regclass('public.direct_bsc_buyer_capabilities')),0)
 ||'|'||
 (NOT has_table_privilege('empiredb_app','public.direct_bsc_buyer_capabilities','SELECT'))::int
 ||'|'||
 (NOT has_table_privilege('empire_payment_approver','public.direct_bsc_buyer_capabilities','SELECT'))::int
 ||'|'||
 (NOT has_table_privilege('empire_bsc_verifier','public.direct_bsc_buyer_capabilities','SELECT'))::int
 ||'|'||
 (NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_policy p
   WHERE p.polrelid=to_regclass('public.direct_bsc_buyer_capabilities')
 ))::int
 ||'|'||
 (EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc f
   JOIN pg_catalog.pg_roles owner ON owner.oid=f.proowner
   WHERE f.oid=to_regprocedure('public.guard_direct_bsc_buyer_capability()')
     AND f.prosecdef AND owner.rolname='empiredb_migrator'
 ))::int
 ||'|'||
 (NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc f
   CROSS JOIN LATERAL pg_catalog.aclexplode(
     COALESCE(f.proacl, pg_catalog.acldefault('f',f.proowner))) acl
   WHERE f.oid=to_regprocedure('public.guard_direct_bsc_buyer_capability()')
     AND acl.grantee=0
 ))::int
 ||'|'||
 (EXISTS (
   SELECT 1 FROM pg_catalog.pg_trigger t
   WHERE t.tgrelid=to_regclass('public.direct_bsc_buyer_capabilities')
     AND t.tgname='direct_bsc_buyer_capability_guard'
     AND t.tgenabled='O'
 ))::int
")" || { echo "DIRECT047_STATUS=POSTCOMMIT_CATALOG_UNAVAILABLE_DO_NOT_RETRY" >&2;exit 5; }
[[ "$post" == '1|1|1|1|1|1|1|1|1' ]] ||
 { echo 'DIRECT047_STATUS=POSTCOMMIT_PRIVILEGE_DRIFT_DO_NOT_RETRY' >&2;exit 5; }
printf 'DIRECT047_RLS_AND_FINANCIAL_ROLE_DENIAL=VERIFIED\n'

# No customer payment or order activation may be claimed without actual
# checkout runtime readback. No service is restarted by this migration.
health="$(curl --noproxy '*' --max-time 5 --silent --show-error --fail \
  http://127.0.0.1:8098/health)" ||
  { echo "DIRECT047_STATUS=CHECKOUT_HEALTH_UNVERIFIED_DO_NOT_RETRY" >&2;exit 5; }
[[ "$(printf '%s' "$health" | /srv/empire_os/.venv/bin/python -c '
import json,sys
h=json.load(sys.stdin)
ok=(h.get("status")=="online"
 and h.get("checkout_settlement_mode")=="direct"
 and h.get("payment_proposal_authorized") is False
 and h.get("binding_order_creation_authorized") is False
 and h.get("payment_execution") is False
 and h.get("revenue_recognition") is False)
print("PASS" if ok else "HELD")')" == PASS ]] ||
  { echo "DIRECT047_STATUS=CHECKOUT_FLAGS_CHANGED_DO_NOT_RETRY" >&2;exit 5; }
printf 'DIRECT047_RUNTIME_FINANCIAL_GATES=STILL_OFF_VERIFIED\n'
printf 'DIRECT047_BUYER_STATUS_API=NOT_ACTIVATED\n'
printf 'DIRECT047_STATUS=SEALED_TABLE_INSTALLED_NO_APP_GRANTS\n'
