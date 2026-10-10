#!/usr/bin/env bash
# HELD: TAM044 scoped sampling function only; no service/config/credential/read.
# Production DDL requires separate explicit founder approval for migration 044.
set -euo pipefail
umask 077
fail() { printf 'TAM044_RESULT=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
if [[ $# -eq 1 && "$1" == "--preflight" ]]; then
  apply=0
elif [[ $# -eq 2 && "$1" == "--apply" && "$2" == "--approved-044" ]]; then
  apply=1
else
  fail "EXPLICIT_TAM044_APPROVAL_OR_PREFLIGHT_REQUIRED"
fi
[[ "$(id -u)" == 0 ]] || fail "AUTHORISED_DBA_ROOT_REQUIRED"
cd /srv/empire_os
[[ "$(git branch --show-current)" == "agent/data-cloud-wave4" ]] \
  || fail "UNEXPECTED_BRANCH"
migration="migrations/empiredb/044_tam_scoped_market_sampling.sql"
pre="scripts/preflight_empiredb_tam044.sql"
post="scripts/verify_empiredb_tam044.sql"
for tool in runuser psql pg_isready pg_dump pg_dumpall pg_restore sha256sum \
  install flock df git systemctl; do
  command -v "$tool" >/dev/null || fail "RELEASE_DEPENDENCY_MISSING"
done
for file in "$migration" "$pre" "$post"; do
  [[ -f "$file" ]] || fail "REVIEWED_FILE_MISSING"
  git diff --quiet HEAD -- "$file" || fail "UNCOMMITTED_RELEASE_SQL"
done
[[ "$(sha256sum "$migration" | cut -d' ' -f1)" == \
  "c87bbf2ac9e19c0960c79c4e96c03900146dfbd322f2295046d936375d1da011" ]] \
  || fail "REVIEWED_MIGRATION_044_HASH_MISMATCH"
[[ "$(sha256sum "$pre" | cut -d' ' -f1)" == \
  "25ed5f631bb29d406aa79f893ba3948283fe04ba57414f1527080c2652b1ad64" ]] \
  || fail "REVIEWED_PREFLIGHT_044_HASH_MISMATCH"
[[ "$(sha256sum "$post" | cut -d' ' -f1)" == \
  "85754b1fe68b31a67428c4a8cdf3d0b6c5c88b9a5916ecbcbe5b52c586778b9b" ]] \
  || fail "REVIEWED_POSTVERIFY_044_HASH_MISMATCH"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR PGOPTIONS
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == "active" ]] \
  || fail "CANONICAL_POSTGRES_NOT_ACTIVE"
pg_isready -q -d empiredb || fail "EMPIREDB_NOT_READY"
exec 9>/run/lock/empiredb-tam044.lock
flock -n -x 9 || fail "PARALLEL_TAM044_RELEASE_BLOCKED"
pg() {
  runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 \
    -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == "empiredb" ]] \
  || fail "CANONICAL_DATABASE_MISMATCH"
[[ "$(pg "SELECT current_setting('data_directory')")" == \
   "/var/lib/postgresql/18/main" ]] || fail "CANONICAL_CLUSTER_MISMATCH"
[[ "$(pg 'SELECT pg_is_in_recovery()')" == "f" ]] \
  || fail "DATABASE_REPLICA_NOT_ALLOWED"
runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb -f "$pre" >/dev/null \
  || fail "TAM044_READ_ONLY_CATALOG_PREFLIGHT_FAILED"
printf 'TAM044_PREFLIGHT=READ_ONLY_PASS\n'
if [[ "$apply" -eq 0 ]]; then
  printf 'TAM044_DDL=NOT_APPLIED\n'
  printf 'TAM044_RESULT=READ_ONLY_PREFLIGHT_PASS\n'
  exit 0
fi

dbsize="$(pg "SELECT pg_database_size('empiredb')")"
[[ "$dbsize" =~ ^[0-9]+$ ]] || fail "DATABASE_SIZE_UNAVAILABLE"
parent="/var/backups/empiredb/tam044-scoped"
install -d -o root -g root -m 0700 "$parent"
free="$(df -PB1 "$parent" | awk 'NR==2 {print $4}')"
[[ "$free" =~ ^[0-9]+$ ]] || fail "BACKUP_DISK_AVAILABILITY_UNVERIFIED"
(( free >= dbsize * 2 + 536870912 )) \
  || fail "BACKUP_DISK_INSUFFICIENT"
backup="$parent/$(date -u +%Y%m%dT%H%M%SZ)"
[[ ! -e "$backup" ]] || fail "BACKUP_TIMESTAMP_COLLISION"
install -d -o root -g root -m 0700 "$backup"
printf 'TAM044_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb \
  > "$backup/empiredb-before-044.dump" \
  || fail "DATABASE_BACKUP_FAILED"
runuser -u postgres -- pg_dumpall -w --globals-only \
  > "$backup/postgres-globals-before-044.sql" \
  || fail "GLOBAL_ROLE_BACKUP_FAILED"
[[ -s "$backup/empiredb-before-044.dump" &&
   -s "$backup/postgres-globals-before-044.sql" ]] \
  || fail "BACKUP_MISSING_OR_EMPTY"
pg_restore --list "$backup/empiredb-before-044.dump" \
  > "$backup/pg-restore-list.txt" || fail "BACKUP_ARCHIVE_INVALID"
for table in prospect_acquisitions prospect_entity_links business_entities; do
  grep -Eq "TABLE[[:space:]]+public[[:space:]]+$table" \
    "$backup/pg-restore-list.txt" || fail "BACKUP_REQUIRED_TABLE_MISSING"
done
(
  cd "$backup"
  sha256sum empiredb-before-044.dump postgres-globals-before-044.sql \
    pg-restore-list.txt > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
) || fail "BACKUP_SHA256_FAILED"
chmod 0600 "$backup"/*
printf 'TAM044_BACKUP=VERIFIED_FORMAT_AND_SHA256\n'
printf 'TAM044_BACKUP_LOCATION=%s\n' "$backup"
printf 'TAM044_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# 044 is a single guarded transaction, independent of the existing 043.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb -f "$migration" \
  > "$backup/migration.stdout.log" 2>"$backup/migration.stderr.log"; then
  printf 'TAM044_RESULT=MIGRATION_FAILED_NO_RETRY\n' >&2
  printf 'TAM044_PRIVATE_LOG=%s\n' "$backup/migration.stderr.log" >&2
  exit 4
fi
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -d empiredb -f "$post" \
  > "$backup/verify.stdout.log" 2>"$backup/verify.stderr.log"; then
  printf 'TAM044_RESULT=POST_RELEASE_CATALOG_UNVERIFIED_NO_RETRY\n' >&2
  printf 'TAM044_PRIVATE_LOG=%s\n' "$backup/verify.stderr.log" >&2
  exit 5
fi
printf 'TAM044_NEW_SCOPED_FUNCTION=CATALOG_VERIFIED\n'
printf 'TAM044_ORIGINAL_043_AND_MARKET_GPS=UNALTERED\n'
printf 'TAM044_READER_MODE_CHANGE=NO\n'
printf 'TAM044_NEW_CREDENTIAL_OR_LOGIN=NO\n'
printf 'TAM044_NEW_MARKET_DATA_READ=NO\n'
printf 'TAM044_SERVICE_START_OR_RESTART=NO\n'
printf 'TAM044_OUTBOUND_OR_PAYMENTS_AUTHORITY=NONE\n'
printf 'TAM044_RESULT=SCOPED_FUNCTION_INSTALLED_READER_MODE_HELD\n'
