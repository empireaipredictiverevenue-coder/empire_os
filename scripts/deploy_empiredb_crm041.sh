#!/usr/bin/env bash
# Founder-approved one-shot EmpireDB 041; NOT user/CRM activation.
set -euo pipefail
umask 077
die() { printf 'CRM041_STATUS=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 1 && "$1" == "--apply" ]] || die "EXPLICIT_APPLY_FLAG_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || die "AUTHORIZED_ROOT_REQUIRED"
cd /srv/empire_os
sql="migrations/empiredb/041_crm_membership_authority.sql"
approved_commit="19350a99"
approved_sha="de8124235e411a23607492fb12fe1142a7176f04a2c0b55bb6c6f71a38eec2ab"
[[ -f "$sql" ]] || die "MIGRATION_FILE_MISSING"
[[ "$(sha256sum "$sql" | cut -d' ' -f1)" == "$approved_sha" ]] || die "APPROVED_SQL_SHA_MISMATCH"
git cat-file -e "${approved_commit}^{commit}" || die "RELEASE_COMMIT_MISSING"
[[ "$(git rev-parse "${approved_commit}:$sql")" == "$(git hash-object "$sql")" ]] || die "COMMITTED_SQL_DRIFT"
for cmd in runuser pg_dump pg_dumpall pg_restore psql pg_isready flock df sha256sum; do
  command -v "$cmd" >/dev/null || die "MISSING_DEPENDENCY"
done
[[ -f /etc/empiredb.env ]] || die "PROTECTED_EMPIREDB_ENV_MISSING"
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die "CANONICAL_APPLICATION_DSN_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST="/var/run/postgresql" PGPORT="5432"
[[ "$(systemctl is-active postgresql@18-main.service)" == "active" ]] || die "CANONICAL_POSTGRES_NOT_ACTIVE"
pg_isready -q -d empiredb || die "POSTGRES_NOT_READY"
exec 9>/run/lock/empiredb-crm041-deploy.lock
flock -n -x 9 || die "CRM041_DEPLOYMENT_ALREADY_RUNNING"
pg() { runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg 'SELECT current_database()')" == "empiredb" ]] || die "WRONG_DATABASE"
[[ "$(pg "SELECT current_setting('data_directory')")" == "/var/lib/postgresql/18/main" ]] || die "WRONG_DATABASE_CLUSTER"
[[ "$(pg "SELECT pg_is_in_recovery()")" == "f" ]] || die "DATABASE_IS_REPLICA"
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ["EMPIREDB_DSN"], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
            row = cur.fetchone()
            print(row[0] if row else "UNVERIFIED")
except Exception:
    print("UNVERIFIED")
PY
)"
[[ "$local_instance" == "$app_instance" ]] || die "APP_DATABASE_INSTANCE_MISMATCH"
preflight="$(pg "
SELECT (to_regclass('public.empire_crm_tenant_memberships') IS NULL)::int
||'|'||(to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NULL)::int
||'|'||(SELECT count(*) FROM pg_roles WHERE rolname IN
 ('empiredb_migrator','empiredb_app','empiredb_readonly',
  'empiredb_tenant_reader','empire_revenue_crm_reader'))
||'|'||(to_regclass('public.revenue_crm_prospects') IS NOT NULL)::int
||'|'||(to_regclass('public.revenue_crm_buyers') IS NOT NULL)::int
")"
[[ "$preflight" == "1|1|5|1|1" ]] || die "MIGRATION_041_DEPENDENCIES_OR_ALREADY_INSTALLED"
db_size="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$db_size" =~ ^[0-9]+$ ]] || die "DATABASE_SIZE_UNKNOWN"
backup_root="/var/backups/empiredb/crm041"
install -d -m 0700 -o root -g root "$backup_root"
free_space="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$free_space" =~ ^[0-9]+$ ]] || die "BACKUP_SPACE_UNKNOWN"
(( free_space >= db_size * 2 + 536870912 )) || die "INSUFFICIENT_BACKUP_CAPACITY"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
[[ ! -e "$backup_dir" ]] || die "BACKUP_ALREADY_EXISTS"
install -d -m 0700 -o root -g root "$backup_dir"
archive="$backup_dir/empiredb-before-041.dump"
globals="$backup_dir/cluster-globals-before-041.sql"
manifest="$backup_dir/pg-restore-list.txt"
printf 'CRM041_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" || die "DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" || die "GLOBALS_BACKUP_FAILED"
[[ -s "$archive" && -s "$globals" ]] || die "BACKUP_EMPTY"
pg_restore --list "$archive" >"$manifest" || die "BACKUP_INVALID"
grep -q 'TABLE.*public.*prospects' "$manifest" || die "PROSPECTS_ABSENT_FROM_BACKUP"
grep -q 'TABLE.*public.*buyers' "$manifest" || die "BUYERS_ABSENT_FROM_BACKUP"
(cd "$backup_dir" && sha256sum empiredb-before-041.dump cluster-globals-before-041.sql pg-restore-list.txt >SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null) || die "BACKUP_SHA256_FAILED"
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'CRM041_BACKUP_ARCHIVE=VERIFIED_FORMAT_AND_SHA256\n'
printf 'CRM041_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'CRM041_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb -f "$sql" >"$backup_dir/migration-stdout.log" 2>"$backup_dir/migration-stderr.log"; then
  printf 'CRM041_TRANSACTION=FAILED_ROLLED_BACK\n' >&2
  printf 'CRM041_PRIVATE_ERROR_LOG=%s\n' "$backup_dir/migration-stderr.log" >&2
  exit 4
fi
printf 'CRM041_TRANSACTION=COMMITTED\n'
# Any unexpected post-commit result is NOT permission to retry.
postflight="$(pg "
SELECT (to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL)::int
||'|'||(to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NOT NULL)::int
||'|'||(SELECT relrowsecurity::int FROM pg_class WHERE oid='public.empire_crm_tenant_memberships'::regclass)
||'|'||(SELECT prosecdef::int FROM pg_proc WHERE oid='public.empire_crm_read_member(text,uuid)'::regprocedure)
||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships)
||'|'||(has_function_privilege('empiredb_app','public.empire_crm_read_member(text,uuid)','EXECUTE'))::int
||'|'||(has_function_privilege('empire_revenue_crm_reader','public.empire_crm_read_member(text,uuid)','EXECUTE'))::int
||'|'||(SELECT CASE WHEN EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empire_crm_membership_login')
 THEN has_function_privilege('empire_crm_membership_login','public.empire_crm_read_member(text,uuid)','EXECUTE')::int ELSE 0 END)
")" || { printf 'CRM041_POSTCOMMIT=CATALOG_UNAVAILABLE_NO_RETRY\n' >&2; exit 5; }
[[ "$postflight" == "1|1|1|1|0|0|0|0" ]] || { printf 'CRM041_POSTCOMMIT=UNEXPECTED_PERMISSIONS_NO_RETRY\n' >&2; exit 5; }
printf 'CRM041_POST_DEPLOYMENT=CATALOG_VERIFIED\n'
printf 'CRM041_MEMBERSHIP_ROWS=0\n'
printf 'CRM041_MEMBERSHIP_LOGIN_GRANTED=NO\n'
printf 'CRM041_PUBLIC_API_ACTIVATED=NO\n'
printf 'CRM041_OUTBOUND_PAYMENT_AUTHORITY=NONE\n'
printf 'CRM041_RESULT=SCHEMA_INSTALLED_APPLICATION_ACTIVATION_HELD\n'
