#!/usr/bin/env bash
# Stage only: installing 049 v2 needs exact additional founder approval.
# No public buyer endpoint, credential/login assignment, payment send or restart.
set -euo pipefail
umask 077
fail() { printf 'DIRECT049_STATUS=HELD reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" &&
   "$2" == "--approved-049-v2-isolated-private-reader-only" ]] ||
  fail "SEPARATE_EXACT_049_FOUNDER_APPROVAL_REQUIRED"
[[ "$(id -u)" == 0 ]] || fail "ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os
SQL=migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql
PREFLIGHT=scripts/inspect_direct_bsc_private_reader_049.py
POSTCHECK=scripts/inspect_direct_bsc_private_reader_049_postcommit.sql
for file in "$SQL" "$PREFLIGHT" "$POSTCHECK"; do
 [[ -f "$file" ]] || fail "REVIEWED_SOURCE_MISSING"
 [[ -z "$(git status --porcelain -- "$file")" ]] ||
   fail "UNCOMMITTED_REVIEWED_SOURCE"
 [[ "$(git hash-object "$file")" == "$(git rev-parse "HEAD:$file" 2>/dev/null)" ]] ||
   fail "REVIEWED_SOURCE_HASH_DRIFT"
done
for c in runuser psql pg_dump pg_dumpall pg_restore pg_isready flock df sha256sum systemctl curl; do
 command -v "$c" >/dev/null || fail "DEPENDENCY_MISSING"
done
exec 9>/run/lock/empiredb-direct049-v2-isolated-reader.lock
flock -n -x 9 || fail "MIGRATION_ALREADY_RUNNING"
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] ||
  fail "CANONICAL_POSTGRES_NOT_ACTIVE"
[[ -f /etc/empiredb.env ]] || fail "CANONICAL_DSN_ENV_MISSING"
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
pg() { runuser -u postgres -- psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg "SELECT current_database()")" == empiredb ]] || fail "WRONG_DB"
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] ||
  fail "WRONG_POSTGRES_CLUSTER"
[[ "$(pg "SELECT pg_is_in_recovery()")" == f ]] || fail "POSTGRES_RECOVERY_MODE"
pg_isready -q -d empiredb || fail "POSTGRES_NOT_READY"

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
    fail "CHECKOUT_PAYMENT_FLAGS_NOT_HELD"
}
check_checkout
printf 'DIRECT049_PRECHECK_CHECKOUT_FLAGS=OFF_VERIFIED\n'

# New purpose-owned v2 must be independently READY, not v1's unsafe variant.
pre="$(runuser -u postgres -- /srv/empire_os/.venv/bin/python \
 -m scripts.inspect_direct_bsc_private_reader_049 --preflight)" ||
 fail "READONLY_049_V2_PREFLIGHT_HELD"
[[ "$(printf '%s' "$pre" | /srv/empire_os/.venv/bin/python -c '
import json,sys
p=json.load(sys.stdin)
ok=(p.get("schema_version")==
"empire.direct-bsc-buyer-private-reader-049-preflight.v2"
and p.get("status")=="READY_FOR_SEPARATELY_APPROVED_PRIVATE_READER_049"
and p.get("mode")=="READ_ONLY"
and p.get("expected_existing_migrator_login_preserved") is True
and p.get("parent_rls_matches_audited_baseline") is True
and p.get("parent_select_policy_present") is True
and p.get("isolated_owner_absent") is True
and p.get("dedicated_reader_absent") is True
and p.get("sealed_capability_table") is True
and p.get("migration_049_applied") is False)
print("PASS" if ok else "HELD")')" == PASS ]] ||
 fail "PREFLIGHT_049_VERSION_OR_SECURITY_DRIFT"
printf 'DIRECT049_V2_CANONICAL_PREFLIGHT=PASS\n'

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
   row=cur.fetchone()
   print(row[0] if row else "UNVERIFIED")
except Exception:
 print("UNVERIFIED")
PY
)" || fail "CANONICAL_APP_INSTANCE_UNAVAILABLE"
unset EMPIREDB_DSN
[[ "$local_instance" == "$app_instance" ]] ||
 fail "CANONICAL_APP_DB_MISMATCH"

# Verify the 048 post-047 backup remains intact; never restore it implicitly.
ORIGINAL_BACKUP=/var/backups/empiredb/direct-bsc-buyer-acl-048/20261013T172615Z
[[ -d "$ORIGINAL_BACKUP" && -f "$ORIGINAL_BACKUP/SHA256SUMS" ]] ||
 fail "048_BACKUP_NOT_FOUND"
(cd "$ORIGINAL_BACKUP" && sha256sum -c SHA256SUMS >/dev/null) ||
 fail "048_BACKUP_HASH_FAILED"

# New pre-049 root-only archive. This is not a restore rehearsal.
BACKUP_ROOT=/var/backups/empiredb/direct-bsc-private-reader-049
[[ ! -L "$BACKUP_ROOT" ]] || fail "BACKUP_ROOT_SYMLINK"
install -d -o root -g root -m 0700 "$BACKUP_ROOT"
[[ "$(stat -c '%u:%g:%a' "$BACKUP_ROOT")" == '0:0:700' ]] ||
 fail "BACKUP_PERMISSIONS_UNSAFE"
size="$(pg "SELECT pg_database_size('empiredb')")"
free="$(df -PB1 "$BACKUP_ROOT" | awk 'NR==2 {print $4}')"
[[ "$size" =~ ^[0-9]+$ && "$free" =~ ^[0-9]+$ ]] ||
 fail "BACKUP_SPACE_UNKNOWN"
(( free >= size*2 + 536870912 )) || fail "BACKUP_SPACE_INSUFFICIENT"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_ROOT/$timestamp"
[[ ! -e "$backup" && ! -L "$backup" ]] || fail "BACKUP_DIRECTORY_COLLISION"
install -d -o root -g root -m 0700 "$backup"
printf 'DIRECT049_BACKUP_STARTED=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb > "$backup/empiredb-pre-049.dump" ||
 fail "DATABASE_BACKUP_FAILED_DO_NOT_APPLY"
runuser -u postgres -- pg_dumpall -w --globals-only > "$backup/globals-pre-049.sql" ||
 fail "GLOBAL_ROLES_BACKUP_FAILED_DO_NOT_APPLY"
[[ -s "$backup/empiredb-pre-049.dump" &&
   -s "$backup/globals-pre-049.sql" ]] ||
 fail "EMPTY_BACKUP_DO_NOT_APPLY"
pg_restore --list "$backup/empiredb-pre-049.dump" > "$backup/restore-list.txt" ||
 fail "BACKUP_ARCHIVE_INVALID"
grep -q 'TABLE.*public.*direct_bsc_buyer_capabilities' "$backup/restore-list.txt" ||
 fail "CAPABILITY_TABLE_MISSING_FROM_BACKUP"
(cd "$backup" &&
 sha256sum empiredb-pre-049.dump globals-pre-049.sql restore-list.txt > SHA256SUMS &&
 sha256sum -c SHA256SUMS >/dev/null) ||
 fail "BACKUP_HASH_INVALID"
chmod 0600 "$backup"/*
printf 'DIRECT049_BACKUP=VERIFIED\nDIRECT049_BACKUP_LOCATION=%s\n' "$backup"
printf 'DIRECT049_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# SQL has BEGIN/COMMIT with its own independent permission/role checks.
# Abort inside SQL rolls back both new NOLOGIN roles and all RLS changes.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$SQL" >"$backup/install-out.log" 2>"$backup/install-error.log"; then
 chmod 0600 "$backup"/install-*.log 2>/dev/null || true
 echo "DIRECT049_STATUS=TRANSACTION_ABORTED_INSPECT_PRIVATE_LOG_NO_RETRY" >&2
 echo "DIRECT049_PRIVATE_LOG=$backup/install-error.log" >&2
 exit 4
fi
printf 'DIRECT049_SQL_TRANSACTION=COMMITTED\n'

# Post-commit readback is independent and emits 12 labelled conditions.
post="$(runuser -u postgres -- psql -X -w -v ON_ERROR_STOP=1 -d empiredb \
 -f "$POSTCHECK")" ||
 { echo "DIRECT049_STATUS=POSTCOMMIT_CATALOG_UNAVAILABLE_NO_RETRY" >&2;exit 5; }
count="$(printf '%s\n' "$post" |
 grep -Ec '^([01][0-9])_[a-z0-9_]+\|PASS$' || true)"
[[ "$count" == 12 ]] ||
 { echo "DIRECT049_STATUS=POSTCOMMIT_SECURITY_HOLD_NO_RETRY" >&2;exit 5; }
printf 'DIRECT049_TWELVE_POSTCOMMIT_SECURITY_CHECKS=PASS\n'
check_checkout
printf 'DIRECT049_CHECKOUT_FLAGS=STILL_OFF_VERIFIED\n'
printf 'DIRECT049_STATUS=ISOLATED_PRIVATE_READER_INSTALLED_NO_LOGIN_NO_ENDPOINT\n'
