#!/usr/bin/env bash
# Stage only: installing 050 v1 needs exact additional founder approval.
# No public buyer endpoint, credential/login assignment, payment send or restart.
set -euo pipefail
umask 077
fail() { printf 'DIRECT050_STATUS=HELD reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" &&
   "$2" == "--approved-050-private-token-issuer-only" ]] ||
  fail "SEPARATE_EXACT_050_FOUNDER_APPROVAL_REQUIRED"
[[ "$(id -u)" == 0 ]] || fail "ROOT_OPERATOR_REQUIRED"
cd /srv/empire_os
SQL=migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql
PREFLIGHT=scripts/inspect_direct_bsc_private_issuer_050.py
POSTCHECK=scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql
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
exec 9>/run/lock/empiredb-direct050-private-issuer.lock
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
printf 'DIRECT050_PRECHECK_CHECKOUT_FLAGS=OFF_VERIFIED\n'

# The isolated issuer 050 v1 must independently pass all 049-derived security gates.
pre="$(runuser -u postgres -- /srv/empire_os/.venv/bin/python \
 -m scripts.inspect_direct_bsc_private_issuer_050 --preflight)" ||
 fail "READONLY_050_PREFLIGHT_HELD"
[[ "$(printf '%s' "$pre" | /srv/empire_os/.venv/bin/python -c '
import json,sys
p=json.load(sys.stdin)
ok=(p.get("schema_version")==
"empire.direct-bsc-private-issuer-050-preflight.v1"
and p.get("status")=="READY_FOR_SEPARATELY_APPROVED_PRIVATE_ISSUER_050"
and p.get("mode")=="READ_ONLY"
and p.get("canonical_empiredb") is True
and p.get("capability_force_rls_one_policy") is True
and p.get("reader_and_owner_isolated") is True
and p.get("reader_role_memberships_zero") is True
and p.get("private_status_function_sealed") is True
and p.get("request_rls_policy_count") is True
and p.get("047_guard_trigger_present") is True
and p.get("issuer_roles_absent") is True
and p.get("issuer_function_absent") is True
and p.get("existing_migrator_login_preserved") is True
and p.get("migration_050_applied") is False)
print("PASS" if ok else "HELD")')" == PASS ]] ||
 fail "PREFLIGHT_050_VERSION_OR_SECURITY_DRIFT"
printf 'DIRECT050_CANONICAL_PREFLIGHT=PASS\n'

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

# Verify the founder-verified 049 backup remains intact; never restore it implicitly.
ORIGINAL_BACKUP=/var/backups/empiredb/direct-bsc-private-reader-049/20261013T191124Z
[[ -d "$ORIGINAL_BACKUP" && -f "$ORIGINAL_BACKUP/SHA256SUMS" ]] ||
 fail "049_BACKUP_NOT_FOUND"
(cd "$ORIGINAL_BACKUP" && sha256sum -c SHA256SUMS >/dev/null) ||
 fail "049_BACKUP_HASH_FAILED"

# New pre-050 root-only archive. This is not a restore rehearsal.
BACKUP_ROOT=/var/backups/empiredb/direct-bsc-private-issuer-050
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
printf 'DIRECT050_BACKUP_STARTED=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb > "$backup/empiredb-pre-050.dump" ||
 fail "DATABASE_BACKUP_FAILED_DO_NOT_APPLY"
runuser -u postgres -- pg_dumpall -w --globals-only > "$backup/globals-pre-050.sql" ||
 fail "GLOBAL_ROLES_BACKUP_FAILED_DO_NOT_APPLY"
[[ -s "$backup/empiredb-pre-050.dump" &&
   -s "$backup/globals-pre-050.sql" ]] ||
 fail "EMPTY_BACKUP_DO_NOT_APPLY"
pg_restore --list "$backup/empiredb-pre-050.dump" > "$backup/restore-list.txt" ||
 fail "BACKUP_ARCHIVE_INVALID"
grep -q 'TABLE.*public.*direct_bsc_buyer_capabilities' "$backup/restore-list.txt" ||
 fail "CAPABILITY_TABLE_MISSING_FROM_BACKUP"
(cd "$backup" &&
 sha256sum empiredb-pre-050.dump globals-pre-050.sql restore-list.txt > SHA256SUMS &&
 sha256sum -c SHA256SUMS >/dev/null) ||
 fail "BACKUP_HASH_INVALID"
chmod 0600 "$backup"/*
printf 'DIRECT050_BACKUP=VERIFIED\nDIRECT050_BACKUP_LOCATION=%s\n' "$backup"
printf 'DIRECT050_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# SQL has BEGIN/COMMIT with its own independent permission/role checks.
# Abort inside SQL rolls back both new NOLOGIN issuer roles and all RLS changes.
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb \
  -f "$SQL" >"$backup/install-out.log" 2>"$backup/install-error.log"; then
 chmod 0600 "$backup"/install-*.log 2>/dev/null || true
 echo "DIRECT050_STATUS=TRANSACTION_ABORTED_INSPECT_PRIVATE_LOG_NO_RETRY" >&2
 echo "DIRECT050_PRIVATE_LOG=$backup/install-error.log" >&2
 exit 4
fi
printf 'DIRECT050_SQL_TRANSACTION=COMMITTED\n'

# Post-commit readback is independent and emits 10 labelled conditions.
post="$(runuser -u postgres -- psql -X -w -v ON_ERROR_STOP=1 -d empiredb \
 -f "$POSTCHECK")" ||
 { echo "DIRECT050_STATUS=POSTCOMMIT_CATALOG_UNAVAILABLE_NO_RETRY" >&2;exit 5; }
count="$(printf '%s\n' "$post" |
 grep -Ec '^([01][0-9])_[a-z0-9_]+\|PASS$' || true)"
[[ "$count" == 10 ]] ||
 { echo "DIRECT050_STATUS=POSTCOMMIT_SECURITY_HOLD_NO_RETRY" >&2;exit 5; }
printf 'DIRECT050_TEN_POSTCOMMIT_SECURITY_CHECKS=PASS\n'
check_checkout
printf 'DIRECT050_CHECKOUT_FLAGS=STILL_OFF_VERIFIED\n'
printf 'DIRECT050_STATUS=PRIVATE_TOKEN_ISSUER_INSTALLED_NO_LOGIN_NO_ENDPOINT\n'
