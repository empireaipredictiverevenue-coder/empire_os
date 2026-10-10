#!/usr/bin/env bash
# EmpireDB CRM046 — founder-approved EXACT suppression-hit function only.
# Does not activate CRM endpoints, tenant login, outreach, payment or traffic.
set -euo pipefail
umask 077
die() { printf 'CRM046_STATUS=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" && "$2" == "--approved-046-suppression-only" ]] || die "TWO_EXACT_APPROVAL_FLAGS_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || die "AUTHORIZED_ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os
sql=migrations/empiredb/046_crm_prospect_suppression_hit.sql
[[ -f "$sql" ]] || die "MIGRATION_FILE_MISSING"
[[ -z "$(git status --porcelain -- "$sql")" ]] || die "UNCOMMITTED_MIGRATION_NOT_APPROVED"
[[ "$(git rev-parse "HEAD:$sql" 2>/dev/null)" == "$(git hash-object "$sql")" ]] || die "REVIEWED_MIGRATION_DRIFT"
for command in runuser pg_dump pg_dumpall pg_restore psql pg_isready flock df sha256sum; do
 command -v "$command" >/dev/null || die "DEPLOYMENT_DEPENDENCY_MISSING"
done
[[ -f /etc/empiredb.env ]] || die "APPROVED_APP_DB_ENV_MISSING"
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die "CANONICAL_APPLICATION_DSN_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == "active" ]] || die "POSTGRES_NOT_ACTIVE"
pg_isready -q -d empiredb || die "POSTGRES_NOT_READY"
exec 9>/run/lock/empiredb-crm046-suppression.lock
flock -n -x 9 || die "MIGRATION_LOCK_HELD"
pg() { runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg 'SELECT current_database()')" == empiredb ]] || die "WRONG_DATABASE"
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] || die "NONCANONICAL_CLUSTER"
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] || die "DATABASE_IN_RECOVERY"
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
 import psycopg
 with psycopg.connect(os.environ["EMPIREDB_DSN"],connect_timeout=5) as conn:
  with conn.cursor() as c:
   c.execute("SET TRANSACTION READ ONLY")
   c.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
   row=c.fetchone()
   print(row[0] if row else "UNVERIFIED")
except Exception:
 print("UNVERIFIED")
PY
)"
[[ "$local_instance" == "$app_instance" ]] || die "APPLICATION_AND_BACKUP_DATABASE_DIFFER"
preflight="$(pg "
SELECT
 (to_regprocedure('public.empire_crm_prospect_suppression_hit(uuid,text)') IS NULL)::int
 ||'|'||(to_regprocedure('public.empire_crm_prospect_authorized(uuid)') IS NOT NULL)::int
 ||'|'||(to_regprocedure('public.empire_current_tenant_id()') IS NOT NULL)::int
 ||'|'||(to_regclass('public.outbound_suppressions') IS NOT NULL)::int
 ||'|'||(to_regclass('public.prospects') IS NOT NULL)::int
 ||'|'||(SELECT count(*) FROM pg_roles WHERE rolname IN ('empire_revenue_crm_reader','empiredb_migrator'))
")" || die "CANONICAL_PREFLIGHT_UNAVAILABLE"
[[ "$preflight" == "1|1|1|1|1|2" ]] || die "FUNCTION_EXISTS_OR_TENANT_PREREQUISITES_MISSING"
db_size="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$db_size" =~ ^[0-9]+$ ]] || die "DATABASE_SIZE_UNVERIFIED"
backup_root=/var/backups/empiredb/crm046-suppression-hit
install -d -m 0700 -o root -g root "$backup_root"
disk_free="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$disk_free" =~ ^[0-9]+$ ]] || die "BACKUP_DISK_UNKNOWN"
(( disk_free >= db_size * 2 + 536870912 )) || die "INSUFFICIENT_BACKUP_CAPACITY"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
[[ ! -e "$backup_dir" ]] || die "BACKUP_PATH_CONFLICT"
install -d -m 0700 -o root -g root "$backup_dir"
printf 'CRM046_BACKUP_START=YES\n'
archive="$backup_dir/empiredb-before-046.dump"
globals="$backup_dir/cluster-globals-before-046.sql"
manifest="$backup_dir/pg-restore-list.txt"
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" || die "DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" || die "CLUSTER_GLOBALS_BACKUP_FAILED"
[[ -s "$archive" && -s "$globals" ]] || die "BACKUP_EMPTY"
pg_restore --list "$archive" >"$manifest" || die "BACKUP_ARCHIVE_INVALID"
grep -q 'TABLE.*public.*prospects' "$manifest" || die "PROSPECT_SOURCE_NOT_BACKED_UP"
grep -q 'TABLE.*public.*outbound_suppressions' "$manifest" || die "SUPPRESSION_SOURCE_NOT_BACKED_UP"
(cd "$backup_dir" && sha256sum empiredb-before-046.dump cluster-globals-before-046.sql pg-restore-list.txt >SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null) || die "BACKUP_SHA256_CHECK_FAILED"
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'CRM046_BACKUP=VERIFIED_ARCHIVE_AND_SHA256\nCRM046_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'CRM046_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb -f "$sql" >"$backup_dir/migration-stdout.log" 2>"$backup_dir/migration-stderr.log"; then
 printf 'CRM046_TRANSACTION=FAILED_ROLLED_BACK\n' >&2
 printf 'CRM046_PRIVATE_ERROR_LOG=%s\n' "$backup_dir/migration-stderr.log" >&2
 exit 4
fi
printf 'CRM046_TRANSACTION=COMMITTED\n'
readback="$(pg "
SELECT
 (SELECT (p.prosecdef AND p.provolatile='s' AND owner.rolname='empiredb_migrator')::int
  FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
  WHERE p.oid=to_regprocedure('public.empire_crm_prospect_suppression_hit(uuid,text)'))
 ||'|'||has_function_privilege('empire_revenue_crm_reader','public.empire_crm_prospect_suppression_hit(uuid,text)','EXECUTE')::int
 ||'|'||has_function_privilege('empiredb_app','public.empire_crm_prospect_suppression_hit(uuid,text)','EXECUTE')::int
 ||'|'||has_function_privilege('empiredb_readonly','public.empire_crm_prospect_suppression_hit(uuid,text)','EXECUTE')::int
 ||'|'||(SELECT EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc p,
   LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) acl
   WHERE p.oid=to_regprocedure('public.empire_crm_prospect_suppression_hit(uuid,text)')
     AND acl.grantee=0 AND acl.privilege_type='EXECUTE'
 ))::int
")" || { echo 'CRM046_POST_COMMIT=CATALOG_UNAVAILABLE_DO_NOT_RETRY' >&2; exit 5; }
[[ "$readback" == "1|1|0|0|0" ]] || { echo 'CRM046_POST_COMMIT=UNEXPECTED_PRIVILEGES_DO_NOT_RETRY' >&2; exit 5; }
# Irrelevant identifiers must NEVER disclose a contact or imply clearance.
negative="$(pg "SELECT public.empire_crm_prospect_suppression_hit(NULL::uuid,'sms')")" || {
 echo 'CRM046_NEGATIVE_PROOF=ERROR_DO_NOT_RETRY' >&2; exit 5;
}
[[ "$negative" == UNKNOWN ]] || { echo 'CRM046_NEGATIVE_PROOF=FAILED_DO_NOT_RETRY' >&2; exit 5; }
printf 'CRM046_POSTCOMMIT_CATALOG=PASS\nCRM046_NEGATIVE_PROOF=UNKNOWN\n'
printf 'CRM046_FUNCTION_OWNER=VERIFIED_MIGRATOR\nCRM046_GLOBAL_SUPPRESSION_TABLE_GRANTS_CHANGED=NO\n'
printf 'CRM046_CONTACT_DATA_READ=NO\nCRM046_PUBLIC_API_ACTIVATED=NO\nCRM046_OUTBOUND_AUTHORITY=NONE\n'
printf 'CRM046_STATUS=FUNCTION_DEPLOYED_NOT_MARKETING_ELIGIBILITY\n'
