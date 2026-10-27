#!/usr/bin/env bash
# Founder-approved Analytics054/055 SCHEMA ONLY. Does not activate visitor collection.
set -Eeuo pipefail
umask 077
cd /srv/empire_os
ROOT=/srv/empire_os
PY="$ROOT/.venv/bin/python"
A="$ROOT/migrations/empiredb/054_first_party_analytics_ledger_held.sql"
B="$ROOT/migrations/empiredb/055_first_party_analytics_erasure_held.sql"
HA=3a7ae044eba0e30fdaa532bcda1208668712293dfa2a61e3a483505c0de64113
HB=a49f84cb2b4875df23f4b499de721d750e99066c5d0f10f2b112a0e34be9dd76
BASE=/var/backups/empiredb/analytics054055-schema-release-20261027
die(){ printf 'ANALYTICS054055_STATUS=HELD_%s\n' "$1" >&2; exit 3; }
[[ "$#" == 1 && "$1" == "--preflight" ||
   "$#" == 2 && "$1" == "--apply" && "$2" == "--schema-only-founder-approved-20261027" ]] || die EXACT_SCOPE_FLAGS_REQUIRED
MODE="$1"
[[ "$(id -u)" == 0 ]] || die ROOT_OPERATOR_REQUIRED
# Privileged psql must never inherit a caller-supplied PG* connection override.
unset PGHOST PGPORT PGHOSTADDR PGUSER PGPASSWORD PGDATABASE PGOPTIONS
unset PGSERVICE PGSERVICEFILE PGSSLMODE PGCONNECT_TIMEOUT
for tool in runuser psql pg_isready flock sha256sum git stat grep; do
 command -v "$tool" >/dev/null || die TOOL_MISSING
done
[[ -x "$PY" && -f "$A" && -f "$B" && ! -L "$A" && ! -L "$B" ]] || die ORIGINAL_SQL_MISSING
[[ "$(sha256sum "$A" | cut -d' ' -f1)" == "$HA" &&
   "$(sha256sum "$B" | cut -d' ' -f1)" == "$HB" ]] || die SOURCE_HASH_DRIFT
[[ -z "$(git status --porcelain -- migrations/empiredb/054_first_party_analytics_ledger_held.sql migrations/empiredb/055_first_party_analytics_erasure_held.sql)" ]] || die MIGRATIONS_DIRTY
[[ "$(git hash-object "$A")" == "$(git rev-parse HEAD:migrations/empiredb/054_first_party_analytics_ledger_held.sql)" &&
   "$(git hash-object "$B")" == "$(git rev-parse HEAD:migrations/empiredb/055_first_party_analytics_erasure_held.sql)" ]] || die SOURCE_NOT_COMMITTED
"$PY" -B -m scripts.review_analytics_ledger_schema_20261019 --read-only >/dev/null || die SOURCE054_UNVERIFIED
"$PY" -B -m scripts.review_analytics_erasure_preflight_20261019 --read-only >/dev/null || die SOURCE055_UNVERIFIED
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || die POSTGRES_NOT_ACTIVE
pg_isready -q -h /var/run/postgresql -p 5432 -d empiredb || die POSTGRES_NOT_READY
exec 9>/run/lock/empiredb-analytics054055-schema-only.lock
flock -n -x 9 || die ANALYTICS_RELEASE_LOCKED
pg(){
 runuser -u postgres -- psql -X -w -q -A -t -v ON_ERROR_STOP=1 \
 -h /var/run/postgresql -p 5432 -U postgres -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == empiredb ]] || die WRONG_DATABASE
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] || die RECOVERY_MODE
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] || die NONCANONICAL_DATA_DIRECTORY
[[ "$(pg "SELECT COALESCE((SELECT (NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)::int FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'),0)")" == 1 ]] || die MIGRATOR_ROLE_UNSAFE
[[ "$(pg "SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE rolname IN ('empire_analytics_maintenance_login','empire_analytics_collection_login')")" == 0 ]] || die RUNTIME_LOGIN_ALREADY_EXISTS
[[ "$(pg "SELECT (to_regprocedure('public.empire_analytics_immutable()') IS NULL AND to_regprocedure('public.empire_analytics_consent_before_insert()') IS NULL AND to_regprocedure('public.empire_analytics_event_before_insert()') IS NULL AND to_regprocedure('public.empire_analytics_erase_session(uuid,text,text,text,text)') IS NULL)::int")" == 1 ]] || die FUNCTION_COLLISION
[[ "$(pg "SELECT COUNT(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('empire_analytics_sessions','empire_analytics_consent_decisions','empire_analytics_event_receipts','empire_analytics_erasure_audit')")" == 0 ]] || die TABLE_COLLISION
[[ -f /etc/pgbackrest/empiredb.conf && ! -L /etc/pgbackrest/empiredb.conf ]] || die PGBACKREST_CONFIG_MISSING
[[ "$(stat -c '%U:%G:%a' /etc/pgbackrest/empiredb.conf)" == postgres:postgres:600 ]] || die PGBACKREST_CONFIG_PERMISSION_DRIFT
grep -Fxq 'repo1-cipher-type=aes-256-cbc' /etc/pgbackrest/empiredb.conf || die ENCRYPTED_BACKUP_CONFIG_NOT_VERIFIED
BACKUP_JSON="$("$PY" -B -m scripts.review_rev051_pgbackrest_backup_readonly --read-only)" || die ENCRYPTED_BACKUP_UNVERIFIED
BACKUP_STATE="$(printf '%s' "$BACKUP_JSON" | "$PY" -B -c 'import json,sys;print(json.load(sys.stdin).get("status","UNKNOWN"))')" || die BACKUP_REPORT_INVALID
[[ "$BACKUP_STATE" == PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED ]] || die RECENT_ENCRYPTED_BACKUP_MISSING
echo 'ANALYTICS054055_PREFLIGHT=PASS_PINNED_SQL_ROLE_PRIMARY_ZERO_TABLES_BACKUP'
echo 'ANALYTICS054055_SCOPE=SCHEMA_ONLY_NO_COLLECTION'
if [[ "$MODE" == "--preflight" ]]; then
 echo 'ANALYTICS054055_EXECUTION=READ_ONLY'
 exit 0
fi
install -d -m 0700 -o root -g root "$BASE"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RECEIPT="$BASE/$STAMP"
[[ ! -e "$RECEIPT" && ! -L "$RECEIPT" ]] || die RECEIPT_COLLISION
install -d -m 0700 -o root -g root "$RECEIPT"
TMP="$(mktemp -d /run/empire-analytics054055.XXXXXXXX)" || die PRIVATE_COPY_FAILED
cleanup(){
 RC=$?
 trap - EXIT
 rm -f -- "$TMP/054.sql" "$TMP/055.sql" 2>/dev/null || true
 rmdir -- "$TMP" 2>/dev/null || true
 exit "$RC"
}
trap cleanup EXIT
chown root:postgres "$TMP"
chmod 0710 "$TMP"
install -m 0440 -o root -g postgres "$A" "$TMP/054.sql"
install -m 0440 -o root -g postgres "$B" "$TMP/055.sql"
[[ "$(sha256sum "$TMP/054.sql" | cut -d' ' -f1)" == "$HA" &&
   "$(sha256sum "$TMP/055.sql" | cut -d' ' -f1)" == "$HB" ]] || die PINNED_SQL_COPY_DRIFT
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
 -h /var/run/postgresql -p 5432 -U postgres -d empiredb -f "$TMP/054.sql" \
 >"$RECEIPT/054.stdout" 2>"$RECEIPT/054.stderr"; then
 echo 'ANALYTICS054_TRANSACTION=FAILED_DO_NOT_RETRY'
 echo "PRIVATE_ERROR_LOG=$RECEIPT/054.stderr"
 exit 4
fi
S054="$(runuser -u postgres -- "$PY" -B -m scripts.review_analytics_live_catalog_20261019 --read-only)" || die POST054_CATALOG_HELD
printf '%s' "$S054" | "$PY" -B -c 'import json,sys;v=json.load(sys.stdin);assert v["status"]=="ANALYTICS054_PRESENT_055_NOT_DEPLOYED" and v["table_count_catalog"]==3' || die POST054_CATALOG_MISMATCH
echo 'ANALYTICS054_POSTCOMMIT=THREE_LOCKED_TABLES_VERIFIED'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
 -h /var/run/postgresql -p 5432 -U postgres -d empiredb -f "$TMP/055.sql" \
 >"$RECEIPT/055.stdout" 2>"$RECEIPT/055.stderr"; then
 echo 'ANALYTICS055_TRANSACTION=FAILED_054_PRESENT_STOP_DO_NOT_RETRY'
 echo "PRIVATE_ERROR_LOG=$RECEIPT/055.stderr"
 exit 5
fi
S055="$(runuser -u postgres -- "$PY" -B -m scripts.review_analytics_live_catalog_20261019 --read-only)" || die POST055_CATALOG_HELD
printf '%s' "$S055" | "$PY" -B -c 'import json,sys;v=json.load(sys.stdin);assert v["status"]=="ANALYTICS054_055_CATALOG_OBJECTS_OBSERVED_RELEASE_HELD" and v["table_count_catalog"]==4 and v["analytics054_production_deployed_verified"] is True and v["analytics055_production_deployed_verified"] is True and v["no_public_erasure_execute_verified"] is True and v["maintenance_role_not_activated_verified"] is True' || die POST055_CATALOG_MISMATCH
EMPTY="$(pg "SELECT (SELECT count(*) FROM public.empire_analytics_sessions)||'|'||(SELECT count(*) FROM public.empire_analytics_consent_decisions)||'|'||(SELECT count(*) FROM public.empire_analytics_event_receipts)||'|'||(SELECT count(*) FROM public.empire_analytics_erasure_audit)")" || die EMPTY_ROW_PROOF_UNAVAILABLE
[[ "$EMPTY" == '0|0|0|0' ]] || die NONEMPTY_SCHEMA_UNEXPECTED
chmod 0600 "$RECEIPT"/*.stdout "$RECEIPT"/*.stderr
echo 'ANALYTICS054055_POSTCOMMIT=FOUR_EMPTY_FORCED_RLS_TABLES_VERIFIED'
echo 'ANALYTICS054055_WRITER=NOT_PROVISIONED'
echo 'ANALYTICS054055_COLLECTION=OFF'
echo 'ANALYTICS075=NOT_APPLIED'
echo 'ANALYTICS054055_STATUS=SCHEMA_ONLY_INSTALLATION_VERIFIED'
echo "PRIVATE_RECEIPT_DIR=$RECEIPT"
