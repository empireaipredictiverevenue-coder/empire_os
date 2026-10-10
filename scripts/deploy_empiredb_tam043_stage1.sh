#!/usr/bin/env bash
# EmpireOS TAM043 Stage 1 ONLY: prepared isolated NOLOGIN database identities
# and restricted research-only SQL function. NO credentials, login activation,
# service installation, market-data SELECT, outbound, payments, or automation.
set -euo pipefail
umask 077

fail() { printf 'TAM043_RESULT=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
if [[ $# -ne 2 || $1 != "--apply" || $2 != "--approved-stage1" ]]; then
  fail "EXPLICIT_STAGE1_APPROVAL_REQUIRED"
fi
[[ $(id -u) -eq 0 ]] || fail "ROOT_DBA_EXECUTION_REQUIRED"
cd /srv/empire_os

bootstrap=deploy/empiredb/tam_isolated_roles_bootstrap.sql
migration=migrations/empiredb/043_tam_isolated_restricted_reader.sql
preflight=scripts/preflight_empiredb_tam043_stage1.sql
postverify=scripts/verify_empiredb_tam043_stage1.sql
for utility in runuser psql pg_isready pg_dump pg_dumpall pg_restore \
  flock df sha256sum git install; do
  command -v "$utility" >/dev/null || fail "MISSING_RELEASE_DEPENDENCY"
done
[[ "$(sha256sum "$bootstrap" | cut -d' ' -f1)" == \
  76af158a953c1bf1c933cc10eec2d6116c2a06bf38af9b52840f01eddbd9ffd1 ]] \
  || fail "PINNED_BOOTSTRAP_SHA_DRIFT"
[[ "$(sha256sum "$migration" | cut -d' ' -f1)" == \
  7edaadd65d67b2cb5d8e14dc29e23d32011ccb290f282a1fa6c8a846cb64dfaa ]] \
  || fail "PINNED_MIGRATION_SHA_DRIFT"
[[ "$(sha256sum "$preflight" | cut -d' ' -f1)" == \
  8be4ebce8dc15b1225c0950faeff974befe0f5014806bf0c760ef3db8be7514f ]] \
  || fail "PINNED_PREFLIGHT_SHA_DRIFT"
[[ "$(sha256sum "$postverify" | cut -d' ' -f1)" == \
  73d2197d322d57f6cdd623e3b6f1f146506dc87b8ec2dd28892d3aa0e70ae759 ]] \
  || fail "PINNED_POSTVERIFY_SHA_DRIFT"
git cat-file -e '63f6699b^{commit}' 2>/dev/null \
  || fail "REVIEWED_SQL_COMMIT_MISSING"
git cat-file -e '0aa7e8fa^{commit}' 2>/dev/null \
  || fail "REVIEWED_PREFLIGHT_COMMIT_MISSING"
for sql in "$bootstrap" "$migration"; do
  [[ "$(git rev-parse "63f6699b:$sql")" == "$(git hash-object "$sql")" ]] \
    || fail "REVIEWED_SQL_GIT_OBJECT_DRIFT"
done
[[ "$(git rev-parse '0aa7e8fa:scripts/preflight_empiredb_tam043_stage1.sql')" == \
  "$(git hash-object "$preflight")" ]] \
  || fail "REVIEWED_PREFLIGHT_GIT_OBJECT_DRIFT"
[[ -f /etc/empiredb.env ]] || fail "CANONICAL_ROOT_ENV_MISSING"
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -v EMPIREDB_DSN && -n "$EMPIREDB_DSN" ]] \
  || fail "CANONICAL_APPLICATION_DSN_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] \
  || fail "CANONICAL_POSTGRES_NOT_ACTIVE"
pg_isready -q -d empiredb || fail "DATABASE_NOT_READY"
exec 9>/run/lock/empiredb-tam043-stage1.lock
flock -n -x 9 || fail "PARALLEL_TAM043_RELEASE_ATTEMPT"

pg() {
  runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 \
    -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == empiredb ]] \
  || fail "CANONICAL_DATABASE_MISMATCH"
[[ "$(pg "SELECT current_setting('data_directory')")" == \
  /var/lib/postgresql/18/main ]] \
  || fail "CANONICAL_POSTGRES_CLUSTER_MISMATCH"
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] \
  || fail "POSTGRES_REPLICA_BLOCKED"

db_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ["EMPIREDB_DSN"], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='3000ms'")
            cur.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
            x=cur.fetchone()
            print(x[0] if x else "UNVERIFIED")
except Exception:
    print("UNVERIFIED")
PY
)"
[[ "$db_instance" == "$app_instance" ]] \
  || fail "APPLICATION_AND_DBA_DATABASES_DIFFER"

# Repeat the passed 12-column/role/catalog preflight directly before backup.
runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$preflight" >/dev/null \
  || fail "LIVE_READ_ONLY_PREFLIGHT_FAILED"
printf 'TAM043_PREFLIGHT=VERIFIED_READ_ONLY\n'

db_size="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$db_size" =~ ^[0-9]+$ ]] || fail "DATABASE_SIZE_UNVERIFIED"
backup_root=/var/backups/empiredb/tam043-stage1
install -d -o root -g root -m 0700 "$backup_root"
free_space="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$free_space" =~ ^[0-9]+$ ]] || fail "BACKUP_SPACE_UNVERIFIED"
(( free_space >= db_size * 2 + 536870912 )) \
  || fail "BACKUP_SPACE_INSUFFICIENT"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
[[ ! -e "$backup_dir" ]] || fail "BACKUP_FOLDER_COLLISION"
install -d -o root -g root -m 0700 "$backup_dir"
archive="$backup_dir/empiredb-before-043.dump"
globals="$backup_dir/postgres-globals-before-043.sql"
manifest="$backup_dir/pg-restore-list.txt"

printf 'TAM043_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" \
  || fail "PRECHANGE_DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" \
  || fail "PRECHANGE_GLOBAL_ROLES_BACKUP_FAILED"
[[ -s "$archive" && -s "$globals" ]] \
  || fail "BACKUP_FILES_EMPTY"
pg_restore --list "$archive" >"$manifest" || fail "BACKUP_INVALID_FORMAT"
for table in prospect_acquisitions prospect_entity_links business_entities; do
  grep -Eq "TABLE[[:space:]]+public[[:space:]]+$table" "$manifest" \
    || fail "BACKUP_CANONICAL_TABLE_NOT_FOUND"
done
(
  cd "$backup_dir"
  sha256sum empiredb-before-043.dump postgres-globals-before-043.sql \
    pg-restore-list.txt > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
) || fail "BACKUP_SHA256_MISMATCH"
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'TAM043_BACKUP=VERIFIED_FORMAT_AND_SHA256\n'
printf 'TAM043_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'TAM043_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# Two independent guarded transactions. Failure leaves at most dormant NOLOGIN
# roles, and never automatically retries or revokes the legacy materializer.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$bootstrap" >"$backup_dir/bootstrap.stdout.log" \
  2>"$backup_dir/bootstrap.stderr.log"; then
  printf 'TAM043_RESULT=BOOTSTRAP_FAILED_NO_RETRY\n' >&2
  printf 'TAM043_PRIVATE_LOG=%s\n' "$backup_dir/bootstrap.stderr.log" >&2
  exit 4
fi
printf 'TAM043_ROLES=COMMITTED_NOLOGIN_PASSWORD_NULL\n'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$migration" >"$backup_dir/migration.stdout.log" \
  2>"$backup_dir/migration.stderr.log"; then
  printf 'TAM043_RESULT=MIGRATION_FAILED_DORMANT_ROLES_HELD_NO_RETRY\n' >&2
  printf 'TAM043_PRIVATE_LOG=%s\n' "$backup_dir/migration.stderr.log" >&2
  exit 4
fi
printf 'TAM043_FUNCTION=COMMITTED_RESTRICTED_EXECUTE\n'

# The final proof is a second READ ONLY ROLLBACK catalog transaction.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb -f "$postverify" >"$backup_dir/verify.stdout.log" \
  2>"$backup_dir/verify.stderr.log"; then
  printf 'TAM043_RESULT=POSTCOMMIT_CATALOG_UNSAFE_NO_RETRY\n' >&2
  printf 'TAM043_PRIVATE_LOG=%s\n' "$backup_dir/verify.stderr.log" >&2
  exit 5
fi
printf 'TAM043_POST_RELEASE=CATALOG_VERIFIED_DORMANT_NOLOGIN\n'
printf 'TAM043_LEGACY_MARKET_GPS_GRANTS=UNCHANGED\n'
printf 'TAM043_LOGIN_ENABLED=NO\n'
printf 'TAM043_CREDENTIAL_PROVISIONED=NO\n'
printf 'TAM043_TAM_MARKET_DATA_READ=NO\n'
printf 'TAM043_SERVICE_ACTIVATED=NO\n'
printf 'TAM043_OUTBOUND_OR_PAYMENT_AUTHORITY=NONE\n'
printf 'TAM043_RESULT=STAGE1_SQL_INSTALLED_STAGE2_HELD\n'
