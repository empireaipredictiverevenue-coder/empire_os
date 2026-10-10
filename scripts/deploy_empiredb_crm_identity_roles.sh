#!/usr/bin/env bash
# EmpireOS CRM identity roles — PREPARED ONLY; no founder approval yet.
# NOLOGIN / no credentials / no user rows / no tenant grants / no API activation.
set -euo pipefail
umask 077
die() { printf 'CRM_ROLES=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" && "$2" == "--approved-release" ]] || die "EXPLICIT_FOUNDER_APPROVAL_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || die "ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os
sql=scripts/prepare_crm_pilot_identity_roles.sql
commit=f92cffbd
sha=00f50e9209164968fa1a0b8caf282137a15c39297f1db3f32b2316778620e7b4
[[ -f "$sql" ]] || die "SQL_MISSING"
[[ "$(sha256sum "$sql" | cut -d' ' -f1)" == "$sha" ]] || die "SQL_HASH_DRIFT"
git cat-file -e "$commit^{commit}" 2>/dev/null || die "RELEASE_COMMIT_MISSING"
[[ "$(git rev-parse "$commit:$sql")" == "$(git hash-object "$sql")" ]] || die "SQL_NOT_COMMITTED"
for cmd in pg_dump pg_dumpall pg_restore runuser psql pg_isready flock df sha256sum; do
  command -v "$cmd" >/dev/null || die "MISSING_DEPENDENCY"
done
[[ -f /etc/empiredb.env ]] || die "DB_ENV_MISSING"
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die "APP_DSN_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || die "CANONICAL_PG18_UNAVAILABLE"
pg_isready -q -d empiredb || die "POSTGRES_NOT_READY"
exec 9>/run/lock/empiredb-crm-identity-roles.lock
flock -n -x 9 || die "ROLE_BOOTSTRAP_ALREADY_RUNNING"
pg() { runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg 'SELECT current_database()')" == empiredb ]] || die "WRONG_DATABASE"
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] || die "WRONG_CLUSTER"
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] || die "READ_ONLY_REPLICA"
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ["EMPIREDB_DSN"], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='3000ms'")
            cur.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
            row=cur.fetchone()
            print(row[0] if row else "UNVERIFIED")
except Exception:
    print("UNVERIFIED")
PY
)"
[[ "$app_instance" == "$local_instance" ]] || die "APP_AND_DBA_INSTANCES_DIFFER"
before="$(pg "
SELECT
 (to_regclass('public.empire_crm_login_credentials') IS NOT NULL)::int
 ||'|'||(to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL)::int
 ||'|'||(to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NOT NULL)::int
 ||'|'||(SELECT count(*) FROM pg_roles WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login'))
 ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
 ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships)
")" || die "PREFLIGHT_UNAVAILABLE"
[[ "$before" == "1|1|1|0|0|0" ]] || die "PREEXISTING_ROLE_OR_ACCOUNT_RECONCILE_FIRST"
db_bytes="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$db_bytes" =~ ^[0-9]+$ ]] || die "DATABASE_SIZE_UNVERIFIED"
backup_root=/var/backups/empiredb/crm-identity-roles
install -d -m 0700 -o root -g root "$backup_root"
available="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$available" =~ ^[0-9]+$ ]] || die "BACKUP_SPACE_UNKNOWN"
(( available >= db_bytes * 2 + 536870912 )) || die "BACKUP_CAPACITY_INSUFFICIENT"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
[[ ! -e "$backup_dir" ]] || die "BACKUP_PATH_EXISTS"
install -d -m 0700 -o root -g root "$backup_dir"
archive="$backup_dir/empiredb-before-roles.dump"
globals="$backup_dir/pg-globals-before-roles.sql"
manifest="$backup_dir/pg-restore-list.txt"
printf 'CRM_ROLES_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" || die "DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" || die "GLOBAL_BACKUP_FAILED"
[[ -s "$archive" && -s "$globals" ]] || die "EMPTY_BACKUP"
pg_restore --list "$archive" >"$manifest" || die "BACKUP_ARCHIVE_INVALID"
grep -q 'TABLE.*public.*empire_crm_login_credentials' "$manifest" || die "CREDENTIAL_TABLE_ABSENT_IN_BACKUP"
grep -q 'TABLE.*public.*empire_crm_tenant_memberships' "$manifest" || die "MEMBERSHIP_TABLE_ABSENT_IN_BACKUP"
(cd "$backup_dir" && sha256sum empiredb-before-roles.dump pg-globals-before-roles.sql pg-restore-list.txt >SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null) || die "BACKUP_INTEGRITY_FAILED"
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'CRM_ROLES_BACKUP=VERIFIED_FORMAT_AND_SHA256\n'
printf 'CRM_ROLES_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'CRM_ROLES_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb -f "$sql" >"$backup_dir/apply-stdout.log" 2>"$backup_dir/apply-stderr.log"; then
  printf 'CRM_ROLES_TRANSACTION=ROLLED_BACK\n' >&2
  printf 'CRM_ROLES_PRIVATE_ERROR_LOG=%s\n' "$backup_dir/apply-stderr.log" >&2
  exit 4
fi
printf 'CRM_ROLES_TRANSACTION=COMMITTED\n'
after="$(pg "
SELECT
 (SELECT count(*) FROM pg_authid WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
    AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolbypassrls
    AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND rolpassword IS NULL)
 ||'|'||(has_table_privilege('empire_crm_auth_login','public.empire_crm_login_credentials','SELECT'))::int
 ||'|'||(has_column_privilege('empire_crm_auth_login','public.empire_crm_login_credentials','failed_attempts','UPDATE'))::int
 ||'|'||(has_column_privilege('empire_crm_auth_login','public.empire_crm_login_credentials','evidence_ref','UPDATE'))::int
 ||'|'||(has_table_privilege('empire_crm_auth_login','public.empire_crm_tenant_memberships','SELECT'))::int
 ||'|'||(has_table_privilege('empire_crm_membership_login','public.empire_crm_login_credentials','SELECT'))::int
 ||'|'||(has_function_privilege('empire_crm_membership_login','public.empire_crm_read_member(text,uuid)','EXECUTE'))::int
 ||'|'||(has_function_privilege('empire_crm_auth_login','public.empire_crm_read_member(text,uuid)','EXECUTE'))::int
 ||'|'||(pg_has_role('empire_crm_auth_login','empire_revenue_crm_reader','MEMBER'))::int
 ||'|'||(pg_has_role('empire_crm_membership_login','empire_revenue_crm_reader','MEMBER'))::int
 ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
 ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships)
")" || { printf 'CRM_ROLES_POSTCOMMIT=CATALOG_UNAVAILABLE_NO_RETRY\n' >&2; exit 5; }
[[ "$after" == "2|1|1|0|0|0|1|0|0|0|0|0" ]] || { printf 'CRM_ROLES_POSTCOMMIT=UNEXPECTED_PERMISSION_NO_RETRY\n' >&2; exit 5; }
printf 'CRM_ROLES_POST_DEPLOYMENT=CATALOG_VERIFIED\n'
printf 'CRM_ROLES_USABLE_LOGINS=0\n'
printf 'CRM_ROLES_PASSWORDS_CONFIGURED=0\n'
printf 'CRM_ROLES_CREDENTIAL_ROWS=0\n'
printf 'CRM_ROLES_MEMBERSHIP_ROWS=0\n'
printf 'CRM_ROLES_TENANT_READER_GRANTS=NONE\n'
printf 'CRM_ROLES_PUBLIC_API_ACTIVATED=NO\n'
printf 'CRM_ROLES_RESULT=NOLOGIN_IDENTITIES_PREPARED_PILOT_HELD\n'
