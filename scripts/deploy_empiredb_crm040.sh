#!/usr/bin/env bash
# EmpireDB CRM 040 - explicitly founder-approved, one-time gated deployment.
# Run locally on EmpireOS with sudo -n bash scripts/deploy_empiredb_crm040.sh --apply
# NEVER starts/stops services, creates login memberships, or alters Cloudflare.
set -euo pipefail
umask 077
die() { printf 'CRM040_DEPLOY_STATUS=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 1 ]] || die "EXPLICIT_APPLY_REQUIRED"
[[ "$1" == "--apply" ]] || die "EXPLICIT_APPLY_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || die "AUTHORIZED_ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os
sql="migrations/empiredb/040_revenue_crm_tenant_reader_views.sql"
verifier="scripts/verify_revenue_crm_live_contract.py"
expected_sha256="04379446bcbbeb282051cc79b96e628f9c17457ea9db875b5fba32952f31d22c"
[[ -f "$sql" && -f "$verifier" ]] || die "RELEASE_FILES_MISSING"
actual_sha256="$(sha256sum "$sql" | awk '{print $1}')"
[[ "$actual_sha256" == "$expected_sha256" ]] || die "MIGRATION_NOT_REVIEWED_COMMIT"
git cat-file -e "25680327^{commit}" || die "APPROVED_RELEASE_COMMIT_MISSING"
[[ "$(git rev-parse "25680327:$sql")" == "$(git hash-object "$sql")" ]] \
  || die "MIGRATION_DRIFT_FROM_APPROVED_COMMIT"
for command in runuser pg_dump pg_dumpall pg_restore psql pg_isready flock df sha256sum; do
  command -v "$command" >/dev/null || die "REQUIRED_DEPLOY_DEPENDENCY_MISSING"
done
[[ -f /etc/empiredb.env ]] || die "APPROVED_READONLY_VERIFIER_ENV_MISSING"
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die "APPROVED_READONLY_VERIFIER_DSN_MISSING"
# Force the local PostgreSQL 18/main socket, not inherited connection variables.
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST="/var/run/postgresql" PGPORT="5432"
[[ "$(systemctl is-active postgresql@18-main.service)" == "active" ]] \
  || die "POSTGRES_SERVICE_NOT_HEALTHY"
pg_isready -q -d empiredb || die "POSTGRES_NOT_READY"
exec 9>/run/lock/empiredb-crm040-deploy.lock
flock -n -x 9 || die "ANOTHER_CRM040_DEPLOYMENT_RUNNING"
pg() {
  runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 \
    -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == "empiredb" ]] \
  || die "WRONG_DATABASE"
[[ "$(pg "SELECT current_setting('data_directory')")" == \
   "/var/lib/postgresql/18/main" ]] || die "LOCAL_CANONICAL_CLUSTER_NOT_VERIFIED"
# Verify that the approved application DSN resolves to this same DB instance.
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ["EMPIREDB_DSN"], connect_timeout=5) as c:
        with c.cursor() as q:
            q.execute("SET TRANSACTION READ ONLY")
            q.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
            row = q.fetchone()
            print(row[0] if row else "UNVERIFIED")
except Exception:
    print("UNVERIFIED")
PY
)"
[[ "$app_instance" == "$local_instance" ]] \
  || die "BACKUP_AND_APPLICATION_DATABASE_NOT_SAME_INSTANCE"
present="$(pg "
SELECT
  (to_regclass('public.revenue_crm_prospects') IS NOT NULL)::int
 + (to_regclass('public.revenue_crm_buyers') IS NOT NULL)::int
 + (to_regprocedure('public.empire_crm_prospect_authorized(uuid)') IS NOT NULL)::int
")"
[[ "$present" == "0" ]] || die "CRM_OBJECTS_ALREADY_EXIST_RECONCILE_FIRST"
login_memberships="$(pg "
SELECT count(*)
FROM pg_catalog.pg_roles account
WHERE account.rolcanlogin AND NOT account.rolsuper
  AND EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles target
    WHERE target.rolname='empire_revenue_crm_reader'
      AND pg_catalog.pg_has_role(account.oid,target.oid,'MEMBER')
  )
")"
[[ "$login_memberships" == "0" ]] || die "CRM_ROLE_ALREADY_REACHABLE_FROM_LOGIN"
unsafe_policies="$(pg "
SELECT count(*) FROM pg_catalog.pg_policy p
JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('prospects','buyers')
  AND p.polcmd IN ('r','*') AND p.polpermissive
  AND 0=ANY(p.polroles)
")"
[[ "$unsafe_policies" == "0" ]] || die "PUBLIC_PERMISSIVE_RLS_POLICY_REQUIRES_REVIEW"
db_size="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$db_size" =~ ^[0-9]+$ ]] || die "DATABASE_SIZE_UNKNOWN"
backup_root="/var/backups/empiredb/crm040"
install -d -m 0700 -o root -g root "$backup_root"
free_space="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$free_space" =~ ^[0-9]+$ ]] || die "BACKUP_DISK_FREE_UNKNOWN"
(( free_space >= db_size * 2 + 536870912 )) || die "INSUFFICIENT_BACKUP_DISK_CAPACITY"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$timestamp"
[[ ! -e "$backup_dir" ]] || die "BACKUP_DESTINATION_EXISTS"
install -d -m 0700 -o root -g root "$backup_dir"
archive="$backup_dir/empiredb-before-040.dump"
globals="$backup_dir/cluster-globals-before-040.sql"
manifest="$backup_dir/pg-restore-list.txt"
printf 'CRM040_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" \
  || die "DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" \
  || die "CLUSTER_GLOBALS_BACKUP_FAILED"
[[ -s "$archive" && -s "$globals" ]] || die "BACKUP_EMPTY"
pg_restore --list "$archive" >"$manifest" || die "BACKUP_ARCHIVE_UNREADABLE"
grep -q 'TABLE.*public.*prospects' "$manifest" || die "BACKUP_PROSPECT_TABLE_MISSING"
grep -q 'TABLE.*public.*buyers' "$manifest" || die "BACKUP_BUYER_TABLE_MISSING"
(cd "$backup_dir" && sha256sum \
  empiredb-before-040.dump cluster-globals-before-040.sql \
  pg-restore-list.txt > SHA256SUMS)
(cd "$backup_dir" && sha256sum -c SHA256SUMS >/dev/null) \
  || die "BACKUP_INTEGRITY_CHECK_FAILED"
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'CRM040_BACKUP_ARCHIVE=VERIFIED_FORMAT_AND_SHA256\n'
printf 'CRM040_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'CRM040_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'
printf 'CRM040_MIGRATION_APPLY=STARTING\n'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
      -d empiredb -f "$sql" >"$backup_dir/migration-stdout.log" \
      2>"$backup_dir/migration-stderr.log"; then
  printf 'CRM040_MIGRATION_STATUS=FAILED_TRANSACTION_ROLLED_BACK\n' >&2
  printf 'CRM040_PRIVATE_ERROR_LOG=%s\n' "$backup_dir/migration-stderr.log" >&2
  exit 4
fi
printf 'CRM040_MIGRATION_TRANSACTION=COMMITTED\n'
if ! /srv/empire_os/.venv/bin/python \
     /srv/empire_os/scripts/verify_revenue_crm_live_contract.py \
     >"$backup_dir/post-apply-catalog.json"; then
  printf 'CRM040_POST_DEPLOYMENT=BLOCKED_CATALOG_VERIFICATION\n' >&2
  printf 'CRM040_TRANSACTION_ALREADY_COMMITTED=YES\n' >&2
  exit 5
fi
printf 'CRM040_POST_DEPLOYMENT_CATALOG=PASS\n'
post_memberships="$(pg "
SELECT count(*)
FROM pg_catalog.pg_roles account
WHERE account.rolcanlogin AND NOT account.rolsuper
  AND EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles target
    WHERE target.rolname='empire_revenue_crm_reader'
      AND pg_catalog.pg_has_role(account.oid,target.oid,'MEMBER')
  )
")"
[[ "$post_memberships" == "0" ]] || die "POST_COMMIT_CRM_ROLE_LOGIN_MEMBERSHIP_FOUND"
printf 'CRM040_ROLE_HAS_LOGIN_MEMBERSHIP=NO\n'
printf 'CRM040_PUBLIC_API_ACTIVATED=NO\n'
printf 'CRM040_OUTBOUND_PAYMENT_AUTHORITY=NONE\n'
printf 'CRM040_RESULT=SCHEMA_INSTALLED_APPLICATION_ACTIVATION_HELD\n'
