#!/usr/bin/env bash
# 048: one-table ACL REPAIR ONLY, never reapply committed 047.
set -euo pipefail
umask 077
fail() { printf 'DIRECT048_STATUS=HELD reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" &&
   "$2" == "--approved-048-one-table-acl-seal-only" ]] ||
   fail "SEPARATE_EXACT_FOUNDER_APPROVAL_REQUIRED"
[[ "$(id -u)" -eq 0 ]] || fail "PRIVILEGED_OPERATOR_REQUIRED"
cd /srv/empire_os
SQL=migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql
FORENSIC=scripts/inspect_direct_bsc_capability_047_postcommit.sql
for file in "$SQL" "$FORENSIC"; do
  [[ -f "$file" ]] || fail "REVIEWED_SOURCE_MISSING"
  [[ -z "$(git status --porcelain -- "$file")" ]] || fail "REVIEWED_SOURCE_UNCOMMITTED"
  [[ "$(git hash-object "$file")" == "$(git rev-parse "HEAD:$file" 2>/dev/null)" ]] ||
    fail "REVIEWED_SOURCE_HASH_DRIFT"
done
for c in runuser psql pg_dump pg_dumpall pg_restore pg_isready flock df sha256sum systemctl curl; do
  command -v "$c" >/dev/null || fail "DEPENDENCY_MISSING"
done
exec 9>/run/lock/empiredb-direct048-acl-repair.lock
flock -n -x 9 || fail "REPAIR_ALREADY_RUNNING"
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] ||
  fail "CANONICAL_POSTGRESQL_NOT_ACTIVE"
[[ -f /etc/empiredb.env ]] || fail "EMPIREDB_ENV_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
pg() { runuser -u postgres -- psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg "SELECT current_database()")" == empiredb ]] || fail "WRONG_DB"
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] ||
  fail "WRONG_POSTGRES_CLUSTER"
[[ "$(pg "SELECT pg_is_in_recovery()")" == f ]] || fail "POSTGRES_RECOVERY_MODE"
pg_isready -q -d empiredb || fail "POSTGRES_NOT_READY"
[[ "$(pg "SELECT pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NOT NULL")" == t ]] ||
  fail "COMMITTED_047_TABLE_ABSENT"

# The first 047 backup is preserved. Do not use it for an automatic rollback:
# it predates creation of the capability table.
ORIGINAL_BACKUP=/var/backups/empiredb/direct-bsc-buyer-capability-047/20261013T165434Z
[[ -d "$ORIGINAL_BACKUP" && -f "$ORIGINAL_BACKUP/SHA256SUMS" ]] ||
  fail "ORIGINAL_047_BACKUP_ABSENT"
(cd "$ORIGINAL_BACKUP" && sha256sum -c SHA256SUMS >/dev/null) ||
  fail "ORIGINAL_047_BACKUP_INTEGRITY_LOST"

# Application and privileged operator must resolve exactly the same instance.
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || fail "APP_DSN_MISSING"
local_instance="$(pg "SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
 import psycopg
 with psycopg.connect(os.environ["EMPIREDB_DSN"],connect_timeout=5) as conn:
  with conn.cursor() as cur:
   cur.execute("SET TRANSACTION READ ONLY")
   cur.execute("SELECT current_database()||'|'||extract(epoch from pg_postmaster_start_time())::bigint")
   record=cur.fetchone()
   print(record[0] if record else 'UNVERIFIED')
except Exception:
 print('UNVERIFIED')
PY
)" || fail "APPLICATION_DB_INSTANCE_UNAVAILABLE"
unset EMPIREDB_DSN
[[ "$local_instance" == "$app_instance" ]] || fail "APP_DB_AND_BACKUP_DB_DIVERGE"

# FINANCIAL GATES HELD both before and after the ACL change; no restart.
check_checkout() {
 local health
 health="$(curl --noproxy '*' -sS --fail --max-time 5 http://127.0.0.1:8098/health)" ||
   fail "CHECKOUT_HEALTH_UNVERIFIED"
 [[ "$(printf '%s' "$health" | /srv/empire_os/.venv/bin/python -c '
import json,sys
h=json.load(sys.stdin)
print("PASS" if h.get("status")=="online" and
h.get("checkout_settlement_mode")=="direct" and
h.get("payment_proposal_authorized") is False and
h.get("binding_order_creation_authorized") is False and
h.get("payment_execution") is False and
h.get("revenue_recognition") is False else "HELD")')" == PASS ]] ||
 fail "PAYMENT_FLAGS_NOT_HELD"
}
check_checkout
printf 'DIRECT048_PRECHECK_SERVICE_AND_PAYMENT_FLAGS=PASS\n'

# Check expected eight passes and exact initial app SELECT failure before
# beginning even the backup. No existing public endpoint may be activated.
report="$(runuser -u postgres -- psql -X -w -v ON_ERROR_STOP=1 -d empiredb -f "$FORENSIC")" ||
 fail "READONLY_POST047_FORENSIC_UNAVAILABLE"
passed="$(printf '%s\n' "$report" | grep -Ec '^[[:space:]]*0[1-9]_[[:alnum:]_]+[[:space:]]*\|[[:space:]]*PASS[[:space:]]*$' || true)"
failed="$(printf '%s\n' "$report" | grep -Ec '^[[:space:]]*03_app_select_denied[[:space:]]*\|[[:space:]]*FAIL[[:space:]]*$' || true)"
[[ "$passed" == 8 && "$failed" == 1 ]] ||
 fail "EXPECTED_SINGLE_ACL_HOLD_CHANGED_DO_NOT_APPLY"
printf 'DIRECT048_EXACT_047_ACL_HOLD=VERIFIED\n'

# Fresh root-protected backup of COMMITTED 047 state, before narrow repair.
backup_root=/var/backups/empiredb/direct-bsc-buyer-acl-048
[[ ! -L "$backup_root" ]] || fail "BACKUP_DIR_SYMLINK"
install -d -m 0700 -o root -g root "$backup_root"
[[ "$(stat -c '%u:%g:%a' "$backup_root")" == '0:0:700' ]] ||
 fail "BACKUP_PERMISSIONS_UNSAFE"
db_size="$(pg "SELECT pg_database_size('empiredb')")"
free="$(df -PB1 "$backup_root" | awk 'NR==2 {print $4}')"
[[ "$db_size" =~ ^[0-9]+$ && "$free" =~ ^[0-9]+$ ]] ||
 fail "BACKUP_DISK_INDETERMINATE"
(( free >= db_size*2 + 536870912 )) || fail "BACKUP_DISK_INSUFFICIENT"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$backup_root/$stamp"
[[ ! -e "$backup" && ! -L "$backup" ]] || fail "BACKUP_PATH_COLLISION"
install -d -m 0700 -o root -g root "$backup"
printf 'DIRECT048_BACKUP_STARTED=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb > "$backup/empiredb-post-047-pre-048.dump" ||
 fail "DATABASE_BACKUP_FAILED_DO_NOT_APPLY"
runuser -u postgres -- pg_dumpall -w --globals-only > "$backup/globals-pre-048.sql" ||
 fail "GLOBALS_BACKUP_FAILED_DO_NOT_APPLY"
[[ -s "$backup/empiredb-post-047-pre-048.dump" &&
   -s "$backup/globals-pre-048.sql" ]] ||
 fail "EMPTY_BACKUP_DO_NOT_APPLY"
pg_restore --list "$backup/empiredb-post-047-pre-048.dump" > "$backup/restore-list.txt" ||
 fail "CORRUPT_BACKUP_DO_NOT_APPLY"
grep -q 'TABLE.*public.*direct_bsc_buyer_capabilities' "$backup/restore-list.txt" ||
 fail "BACKUP_MISSING_047_TABLE"
(cd "$backup" && sha256sum empiredb-post-047-pre-048.dump globals-pre-048.sql restore-list.txt > SHA256SUMS &&
  sha256sum -c SHA256SUMS >/dev/null) || fail "BACKUP_HASH_INVALID"
chmod 0600 "$backup"/*
printf 'DIRECT048_BACKUP=VERIFIED\nDIRECT048_BACKUP_LOCATION=%s\n' "$backup"
printf 'DIRECT048_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# Transaction SQL independently checks the EXACT five undesired table ACLs
# and rejects unknown privileges. No default privilege or other object writes.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$SQL" > "$backup/repair-out.log" 2> "$backup/repair-error.log"; then
  chmod 0600 "$backup"/repair-*.log 2>/dev/null || true
  echo "DIRECT048_STATUS=TRANSACTION_ABORTED_DO_NOT_RETRY" >&2
  echo "DIRECT048_PRIVATE_LOG=$backup/repair-error.log" >&2
  exit 4
fi
printf 'DIRECT048_SQL_TRANSACTION=COMMITTED\n'

# Explicit independent verification; a nonzero after COMMIT is NOT rollback.
result="$(runuser -u postgres -- psql -X -w -v ON_ERROR_STOP=1 -d empiredb -f "$FORENSIC")" ||
 { echo 'DIRECT048_STATUS=POSTCOMMIT_CATALOG_UNAVAILABLE_DO_NOT_RETRY' >&2;exit 5; }
count="$(printf '%s\n' "$result" | grep -Ec '^[[:space:]]*0[1-9]_[[:alnum:]_]+[[:space:]]*\|[[:space:]]*PASS[[:space:]]*$' || true)"
[[ "$count" == 9 ]] ||
 { echo 'DIRECT048_STATUS=POSTCOMMIT_CHECK_FAILED_DO_NOT_RETRY' >&2;exit 5; }
[[ "$(pg "SELECT (NOT has_table_privilege('empiredb_readonly','public.direct_bsc_buyer_capabilities','SELECT'))::int")" == 1 ]] ||
 { echo 'DIRECT048_STATUS=READONLY_ROLE_STILL_HAS_ACCESS_DO_NOT_RETRY' >&2;exit 5; }
printf 'DIRECT048_ALL_NINE_POSTCOMMIT_SECURITY_CHECKS=PASS\n'
printf 'DIRECT048_APP_AND_READONLY_ROLE_DENIAL=VERIFIED\n'
check_checkout
printf 'DIRECT048_RUNTIME_FINANCIAL_GATES=STILL_OFF_VERIFIED\n'
printf 'DIRECT048_DEFAULT_PRIVILEGES_AND_OTHER_TABLES=UNCHANGED_BY_MIGRATION\n'
printf 'DIRECT048_STATUS=ONE_TABLE_ACL_SEALED_NO_PAYMENT_ACTIVATION\n'
