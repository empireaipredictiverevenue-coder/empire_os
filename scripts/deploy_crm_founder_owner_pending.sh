#!/usr/bin/env bash
# EmpireOS — one founder-approved PENDING owner membership.
# Never an active CRM account, real login, tenant-reader grant or mail send.
# Prepared for founder terminal; no automatic activation or scheduling.
set -euo pipefail
umask 077
die() { printf 'CRM_FOUNDER_MEMBER=BLOCKED reason=%s\n' "$1" >&2; exit 3; }

[[ "$#" -eq 2 && "$1" == '--apply' && "$2" == '--approved-pending-owner' ]] ||
  die 'EXPLICIT_SINGLE_ROW_FOUNDER_SCOPE_REQUIRED'
[[ "$(id -u)" -eq 0 ]] || die 'ROOT_OPERATOR_REQUIRED'
cd /srv/empire_os

sql=scripts/provision_crm_founder_owner_pending.sql
sql_sha=b2287dbfffc288d205cf27ef33db070bd59780db7bbfa9c2b76db0c76f4d441c
[[ -f "$sql" ]] || die 'SQL_MISSING'
[[ "$(sha256sum "$sql" | cut -d' ' -f1)" == "$sql_sha" ]] ||
  die 'SQL_HASH_DRIFT'
git ls-files --error-unmatch "$sql" >/dev/null 2>&1 ||
  die 'SOURCE_UNTRACKED'
[[ "$(git rev-parse "HEAD:$sql")" == "$(git hash-object "$sql")" ]] ||
  die 'SOURCE_NOT_COMMITTED'
for executable in pg_dump pg_dumpall pg_restore runuser psql pg_isready flock df sha256sum; do
  command -v "$executable" >/dev/null || die 'MISSING_DEPENDENCY'
done
[[ -f /etc/empiredb.env ]] || die 'DB_ENV_MISSING'
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die 'APP_DSN_MISSING'
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] ||
  die 'POSTGRES18_UNAVAILABLE'
pg_isready -q -d empiredb || die 'POSTGRES_UNAVAILABLE'
exec 9>/run/lock/empiredb-crm-founder-single-member.lock
flock -n -x 9 || die 'SAME_RELEASE_ALREADY_RUNNING'
pg() {
  runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 \
    -h /var/run/postgresql -p 5432 -U postgres -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == empiredb ]] || die 'WRONG_DB'
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] ||
  die 'WRONG_CLUSTER'
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] || die 'READ_ONLY_REPLICA'

operator_instance="$(pg "SELECT current_database()||'|'||
  extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ['EMPIREDB_DSN'], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute("SET LOCAL statement_timeout='3000ms'")
            cur.execute("SELECT current_database()||'|'||"
                        "extract(epoch from pg_postmaster_start_time())::bigint")
            result = cur.fetchone()
            print(result[0] if result else 'UNVERIFIED')
except Exception:
    print('UNVERIFIED')
PY
)"
[[ "$operator_instance" == "$app_instance" ]] ||
  die 'APP_AND_OPERATOR_DATABASE_INSTANCE_DIFFER'

preflight="$(pg "
SELECT
  (to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL)::int
  ||'|'||(to_regclass('public.empire_crm_login_credentials') IS NOT NULL)::int
  ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships)
  ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
  ||'|'||(SELECT count(*) FROM pg_authid
    WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
      AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
      AND NOT rolbypassrls AND rolpassword IS NULL)
  ||'|'||(SELECT count(*) FROM public.empire_tenant_role_bindings b
    JOIN pg_roles r ON b.role_name=r.rolname
    WHERE b.tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'
      AND b.role_name='empire_intelligence_materializer_login'
      AND b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
      AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls)
  ||'|'||(SELECT count(*) FROM public.tenant_business_entity_bindings b
    WHERE b.tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'
      AND b.active AND b.binding_kind='observed'
      AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
      AND b.valid_from<=now() AND (b.valid_until IS NULL OR b.valid_until>now()))
")" || die 'PREFLIGHT_QUERY_FAILED'
[[ "$preflight" == '1|1|0|0|2|1|4' ]] ||
  die 'EXISTING_TENANT_OR_MEMBERSHIP_RECONCILE_FIRST'

db_bytes="$(pg "SELECT pg_database_size('empiredb')")" ||
  die 'DATABASE_SIZE_UNVERIFIED'
[[ "$db_bytes" =~ ^[0-9]+$ ]] || die 'DATABASE_SIZE_NOT_NUMERIC'
backup_root=/var/backups/empiredb/crm-founder-pending-owner
install -d -m 0700 -o root -g root "$backup_root"
available="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$available" =~ ^[0-9]+$ ]] || die 'BACKUP_SPACE_UNKNOWN'
(( available >= db_bytes * 2 + 536870912 )) ||
  die 'BACKUP_SPACE_INSUFFICIENT'
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
[[ ! -e "$backup_dir" ]] || die 'BACKUP_PATH_EXISTS'
install -d -m 0700 -o root -g root "$backup_dir"
archive="$backup_dir/empiredb-before-founder-pending-owner.dump"
globals="$backup_dir/postgresql-globals-before-founder-owner.sql"
manifest="$backup_dir/restore-archive-list.txt"
printf 'CRM_FOUNDER_MEMBER_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" ||
  die 'DATABASE_BACKUP_FAILED'
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" ||
  die 'GLOBAL_BACKUP_FAILED'
[[ -s "$archive" && -s "$globals" ]] || die 'BACKUP_EMPTY'
pg_restore --list "$archive" >"$manifest" ||
  die 'BACKUP_ARCHIVE_INVALID'
grep -q 'TABLE.*public.*empire_crm_tenant_memberships' "$manifest" ||
  die 'MEMBERSHIP_TABLE_ABSENT_IN_ARCHIVE'
grep -q 'TABLE.*public.*empire_crm_login_credentials' "$manifest" ||
  die 'CREDENTIAL_TABLE_ABSENT_IN_ARCHIVE'
(cd "$backup_dir" &&
  sha256sum empiredb-before-founder-pending-owner.dump \
    postgresql-globals-before-founder-owner.sql restore-archive-list.txt > SHA256SUMS &&
  sha256sum -c SHA256SUMS >/dev/null) || die 'BACKUP_INTEGRITY_FAILED'
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'CRM_FOUNDER_MEMBER_BACKUP=VERIFIED_SHA256_FORMAT\n'
printf 'CRM_FOUNDER_MEMBER_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'CRM_FOUNDER_MEMBER_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -h /var/run/postgresql -p 5432 -U postgres -d empiredb \
  -f "$sql" >"$backup_dir/operation-stdout.log" \
  2>"$backup_dir/operation-stderr.log"; then
  printf 'CRM_FOUNDER_MEMBER_TRANSACTION=ROLLED_BACK_OR_UNCONFIRMED\n' >&2
  printf 'CRM_FOUNDER_MEMBER_PRIVATE_ERROR_LOG=%s\n' \
    "$backup_dir/operation-stderr.log" >&2
  exit 4
fi
printf 'CRM_FOUNDER_MEMBER_TRANSACTION=COMMITTED\n'
after="$(pg "
SELECT
 (SELECT count(*) FROM public.empire_crm_tenant_memberships)
 ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships
       WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'
         AND subject='founder:phil_livesley'
         AND role='owner' AND status='pending' AND revoked_at IS NULL)
 ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships WHERE status='active')
 ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
 ||'|'||(SELECT count(*) FROM pg_authid
         WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
           AND NOT rolcanlogin AND NOT rolinherit
           AND NOT rolsuper AND NOT rolbypassrls AND rolpassword IS NULL)
")" || {
  echo 'CRM_FOUNDER_MEMBER_POSTCOMMIT=CATALOG_UNAVAILABLE_DO_NOT_RETRY' >&2
  exit 5
}
[[ "$after" == '1|1|0|0|2' ]] || {
  echo 'CRM_FOUNDER_MEMBER_POSTCOMMIT=UNEXPECTED_STATE_DO_NOT_RETRY' >&2
  exit 5
}
printf 'CRM_FOUNDER_MEMBER_POST_DEPLOYMENT=CATALOG_VERIFIED\n'
printf 'CRM_FOUNDER_MEMBER_TOTAL=1\n'
printf 'CRM_FOUNDER_MEMBER_ROLE=owner\n'
printf 'CRM_FOUNDER_MEMBER_STATUS=pending\n'
printf 'CRM_FOUNDER_MEMBER_ACTIVE=0\n'
printf 'CRM_FOUNDER_MEMBER_CREDENTIALS=0\n'
printf 'CRM_FOUNDER_MEMBER_LOGIN_ROLE_CHANGES=NO\n'
printf 'CRM_FOUNDER_MEMBER_EMAIL_SENT=NO\n'
printf 'CRM_FOUNDER_MEMBER_HTTP_CONFIG_CHANGED=NO\n'
printf 'CRM_FOUNDER_MEMBER_RESULT=PENDING_OWNER_RECORDED_AUTHENTICATION_HELD\n'
