#!/usr/bin/env bash
# CRM042: founder-gated schema-only deployment. DOES NOT PROVISION USERS.
# Not executable without explicit --apply and --approved-release arguments.
# Mandatory backup, pin, canonical instance verification, catalog readback.
set -euo pipefail
umask 077

die() { printf 'CRM042_RESULT=BLOCKED reason=%s\n' "$1" >&2; exit 3; }

[[ "$#" -eq 2 && "$1" == "--apply" && "$2" == "--approved-release" ]] \
  || die "EXPLICIT_FOUNDER_APPROVAL_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || die "ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os

migration="migrations/empiredb/042_crm_first_party_login.sql"
approved_commit="810d1dfb"
approved_sha="5ecee3b24d886e6664d2189a94da95695a71c2825820ab74388443c909893f43"
[[ -f "$migration" ]] || die "APPROVED_MIGRATION_MISSING"
[[ "$(sha256sum "$migration" | awk '{print $1}')" == "$approved_sha" ]] \
  || die "MIGRATION_SHA256_DRIFT"
git cat-file -e "$approved_commit^{commit}" 2>/dev/null \
  || die "REVIEWED_GIT_COMMIT_MISSING"
[[ "$(git rev-parse "$approved_commit:$migration")" == "$(git hash-object "$migration")" ]] \
  || die "MIGRATION_COMMIT_DRIFT"

for program in runuser pg_dump pg_dumpall pg_restore psql pg_isready flock df sha256sum; do
  command -v "$program" >/dev/null || die "REQUIRED_DEPENDENCY_MISSING"
done
[[ -f /etc/empiredb.env ]] || die "CANONICAL_DB_ENV_MISSING"
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die "CANONICAL_APP_DSN_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST="/var/run/postgresql" PGPORT="5432"
[[ "$(systemctl is-active postgresql@18-main.service)" == "active" ]] \
  || die "CANONICAL_POSTGRES_UNAVAILABLE"
pg_isready -q -d empiredb || die "DATABASE_NOT_READY"

exec 9>/run/lock/empiredb-crm042-deploy.lock
flock -n -x 9 || die "CRM042_ALREADY_RUNNING"
pg() {
  runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == "empiredb" ]] \
  || die "WRONG_DATABASE"
[[ "$(pg "SELECT current_setting('data_directory')")" == "/var/lib/postgresql/18/main" ]] \
  || die "WRONG_CLUSTER"
[[ "$(pg "SELECT pg_is_in_recovery()")" == "f" ]] \
  || die "DATABASE_IS_REPLICA"
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ["EMPIREDB_DSN"], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='3000ms'")
            cur.execute(
                "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint"
            )
            row = cur.fetchone()
            print(row[0] if row else "UNVERIFIED")
except Exception:
    print("UNVERIFIED")
PY
)"
[[ "$app_instance" == "$local_instance" ]] \
  || die "APPLICATION_AND_BACKUP_DATABASE_DIFFER"

prerequisites="$(pg "
SELECT
  (to_regclass('public.revenue_crm_prospects') IS NOT NULL)::int
  ||'|'||(to_regclass('public.revenue_crm_buyers') IS NOT NULL)::int
  ||'|'||(to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL)::int
  ||'|'||(to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NOT NULL)::int
  ||'|'||(to_regclass('public.empire_crm_login_credentials') IS NULL)::int
  ||'|'||(SELECT count(*) FROM pg_roles WHERE rolname IN
    ('empiredb_migrator','empiredb_app','empiredb_readonly',
     'empiredb_tenant_reader','empire_revenue_crm_reader'))
")"
[[ "$prerequisites" == "1|1|1|1|1|5" ]] \
  || die "SCHEMA_PREREQUISITES_OR_ALREADY_INSTALLED"

database_bytes="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$database_bytes" =~ ^[0-9]+$ ]] || die "DATABASE_SIZE_UNKNOWN"
backup_root="/var/backups/empiredb/crm042"
install -d -o root -g root -m 0700 "$backup_root"
free_bytes="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$free_bytes" =~ ^[0-9]+$ ]] || die "BACKUP_FREE_SPACE_UNKNOWN"
(( free_bytes >= database_bytes * 2 + 536870912 )) \
  || die "INSUFFICIENT_DISK_FOR_BACKUP"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive_dir="$backup_root/$stamp"
[[ ! -e "$archive_dir" ]] || die "BACKUP_DIRECTORY_EXISTS"
install -d -o root -g root -m 0700 "$archive_dir"
archive="$archive_dir/empiredb-before-042.dump"
globals="$archive_dir/postgres-globals-before-042.sql"
manifest="$archive_dir/pg-restore-list.txt"

printf 'CRM042_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb > "$archive" \
  || die "DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only > "$globals" \
  || die "GLOBAL_ROLES_BACKUP_FAILED"
[[ -s "$archive" && -s "$globals" ]] || die "BACKUP_EMPTY"
pg_restore --list "$archive" > "$manifest" \
  || die "BACKUP_FORMAT_INVALID"
grep -q 'TABLE.*public.*prospects' "$manifest" \
  || die "PROSPECT_BACKUP_CONTENT_MISSING"
grep -q 'TABLE.*public.*buyers' "$manifest" \
  || die "BUYER_BACKUP_CONTENT_MISSING"
(
  cd "$archive_dir"
  sha256sum empiredb-before-042.dump postgres-globals-before-042.sql \
    pg-restore-list.txt > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
) || die "BACKUP_HASH_MISMATCH"
chmod 0600 "$archive" "$globals" "$manifest" "$archive_dir/SHA256SUMS"
printf 'CRM042_BACKUP_ARCHIVE=VERIFIED_SHA256_FORMAT\n'
printf 'CRM042_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'
printf 'CRM042_BACKUP_LOCATION=%s\n' "$archive_dir"

if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb -f "$migration" \
  > "$archive_dir/migration-stdout.log" \
  2> "$archive_dir/migration-stderr.log"; then
  printf 'CRM042_RESULT=FAILED_MIGRATION_ROLLED_BACK\n' >&2
  printf 'CRM042_PRIVATE_ERROR_LOG=%s\n' "$archive_dir/migration-stderr.log" >&2
  exit 4
fi
printf 'CRM042_TRANSACTION=COMMITTED\n'
# The migration intentionally creates no active user, membership or grants.
catalog="$(pg "
SELECT
  (to_regclass('public.empire_crm_login_credentials') IS NOT NULL)::int
  ||'|'||(SELECT relrowsecurity::int FROM pg_class
          WHERE oid='public.empire_crm_login_credentials'::regclass)
  ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
  ||'|'||(has_table_privilege('empiredb_app',
      'public.empire_crm_login_credentials','SELECT'))::int
  ||'|'||(has_table_privilege('empire_revenue_crm_reader',
      'public.empire_crm_login_credentials','SELECT'))::int
  ||'|'||(SELECT count(*) FROM pg_catalog.pg_class c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      coalesce(c.relacl,pg_catalog.acldefault('r',c.relowner))
    ) a
    WHERE c.oid='public.empire_crm_login_credentials'::pg_catalog.regclass
      AND a.grantee=0 AND a.privilege_type='SELECT')
")" || die "POST_COMMIT_CATALOG_UNAVAILABLE"
[[ "$catalog" == "1|1|0|0|0|0" ]] \
  || die "POST_COMMIT_CATALOG_UNSAFE_NO_RETRY"
printf 'CRM042_POST_DEPLOYMENT=CATALOG_VERIFIED\n'
printf 'CRM042_CREDENTIAL_ROWS=0\n'
printf 'CRM042_ROLE_GRANTS_PERFORMED=NO\n'
printf 'CRM042_PUBLIC_API_ACTIVATED=NO\n'
printf 'CRM042_OUTBOUND_PAYMENT_AUTHORITY=NONE\n'
printf 'CRM042_RESULT=SCHEMA_INSTALLED_IDENTITY_ACTIVATION_HELD\n'
