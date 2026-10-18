#!/usr/bin/env bash
# Founder approval, 18 Oct 2026: EmpireDB migration 052 SCHEMA ONLY.
# Never import historical Gmail receipts or generate canonical outbound intents.
# Root-run APPLY uses existing postgres peer auth; no new database credentials.
set -euo pipefail

ROOT=/srv/empire_os
MIGRATION="$ROOT/migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql"
EXPECTED_SHA=1122ad3d77b05b204f37e244a2968b99ed902346b6c4b6e75c291f99e43d4693
BASE_URL=http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-historical-evidence-status
PG_BIN=/usr/bin/psql
MODE="${1:-}"
case "$MODE" in
  --preflight|--apply-founder-approved-migration-052|--verify) ;;
  *) printf 'Usage: %s --preflight | --apply-founder-approved-migration-052 | --verify\n' "$0" >&2;exit 2;;
esac
[[ "${2:-}" == "" ]] || { echo 'Usage: exactly one mode argument' >&2;exit 2; }

die(){ printf 'HOLD_%s\n' "$1" >&2;exit 4; }
[[ -f "$MIGRATION" && ! -L "$MIGRATION" ]] || die MISSING_EXACT_MIGRATION
echo "$EXPECTED_SHA  $MIGRATION" | sha256sum -c --status || die MIGRATION_SOURCE_DIGEST_DRIFT
[[ -x "$PG_BIN" ]] || die POSTGRESQL_CLIENT_NOT_INSTALLED
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || die CANONICAL_POSTGRES_NOT_ACTIVE
for unit in empire-founder-dashboard-api.service empire-founder-console.service empire-revenue-crm-pilot.service empire-buyer-acquisition-team.timer;do
  [[ "$(systemctl is-active "$unit")" == active ]] || die EXISTING_EMPIRE_SERVICE_UNHEALTHY
done

source_status="$(
  curl -fsS --max-time 8 "$BASE_URL" |
  python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["private_custody_receipts_verified"]==6
assert d["canonical_outbound_intents_created"]==0
assert d["crm_records_created"]==0
assert d["outbound_sent"] is False
assert d["database_writes"] is False
print(d["status"],d["database_historical_receipts_verified"],str(d["database_historical_receipt_table_active"]).lower())'
)" || die PRIVATE_EVIDENCE_SOURCE_UNAVAILABLE

if [[ "$MODE" == --preflight ]];then
  [[ "$source_status" == "PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD 0 false" ]] ||
    die SCHEMA_IS_NOT_IN_PRE_MIGRATION_STATE
  echo 'MIGRATION_052_SOURCE_AND_PRIVATE_EVIDENCE_PREFLIGHT_PASS'
  echo 'approved_scope=one_new_historical_evidence_table import_authorized=no canonical_intents_created=no'
  echo 'migration_not_applied=true privileged_database_preflight_occurs_only_during_operator_apply'
  exit 0
fi

[[ "$(id -u)" == 0 ]] || die ROOT_DBA_OPERATOR_REQUIRED
command -v runuser >/dev/null || die EXISTING_POSTGRES_PEER_RUNNER_UNAVAILABLE
LOCK=/run/lock/empiredb-historical-migration-052.lock
exec 9>"$LOCK"
flock -n 9 || die CONCURRENT_SCHEMA_OPERATOR

pg_query(){
  runuser -u postgres -- env -i PATH=/usr/bin:/bin "$PG_BIN" -X -qAt -v ON_ERROR_STOP=1 -h /var/run/postgresql -p 5432 -d empiredb -c "$1"
}

if [[ "$MODE" == --verify ]];then
  [[ "$source_status" == "SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS 0 true" ]] ||
    die POST_MIGRATION_READ_API_NOT_VERIFIED
else
  [[ "$source_status" == "PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD 0 false" ]] ||
    die MIGRATION_ALREADY_APPLIED_OR_STATE_DRIFT
  # No writes if any live role, database, WAL archiver or schema precondition fails.
  checks="$(pg_query "SELECT current_database(),pg_is_in_recovery(),
    current_setting('archive_mode'),
    (SELECT archived_count > 0 AND last_archived_time IS NOT NULL AND
        (last_failed_time IS NULL OR last_archived_time > last_failed_time)
     FROM pg_stat_archiver),
    (SELECT rolsuper FROM pg_roles WHERE rolname='postgres'),
    (SELECT NOT rolcanlogin FROM pg_roles WHERE rolname='empiredb_migrator'),
    (SELECT NOT rolsuper AND NOT rolbypassrls FROM pg_roles
      WHERE rolname='empire_closer_observer'),
    has_schema_privilege('empiredb_migrator','public','CREATE'),
    has_schema_privilege('empire_closer_observer','public','USAGE'),
    to_regclass('public.workspace_historical_sent_receipts') IS NULL;")" ||
    die LIVE_DATABASE_PREFLIGHT_QUERY_FAILED
  [[ "$checks" == $'empiredb|f|on|t|t|t|t|t|t|t' ]] ||
    { printf 'HOLD_LIVE_DB_ARCHIVER_ROLE_OR_SCHEMA_PREFLIGHT [%s]\n' "$checks" >&2;exit 4; }
  echo 'LIVE_EMPIREDB_ROLE_ARCHIVER_AND_SCHEMA_PREFLIGHT_PASS'

  frozen=''
  cleanup(){ [[ -z "$frozen" ]] || rm -f "$frozen"; }
  trap cleanup EXIT
  frozen="$(mktemp /tmp/empiredb-hist052-approved.XXXXXXXX.sql)"
  cp -- "$MIGRATION" "$frozen"
  echo "$EXPECTED_SHA  $frozen" | sha256sum -c --status ||
    die MIGRATION_CHANGED_DURING_FREEZE
  chmod 0644 "$frozen"
  # One transactional migration; failure rolls back inside the SQL.
  runuser -u postgres -- env -i PATH=/usr/bin:/bin "$PG_BIN" -X -v ON_ERROR_STOP=1 -h /var/run/postgresql -p 5432 -d empiredb -f "$frozen" ||
    die MIGRATION_052_TRANSACTION_FAILED
  echo 'MIGRATION_052_SQL_TRANSACTION_RETURNED_SUCCESS'
fi

# Only catalog and counts; never return recipient, token or customer data.
catalog="$(pg_query "SELECT
  c.relrowsecurity,c.relforcerowsecurity,
  (SELECT count(*) FROM pg_trigger t WHERE t.tgrelid=c.oid
     AND t.tgname='workspace_historical_receipts_append_only'
     AND NOT t.tgisinternal),
  has_table_privilege('empire_closer_observer',c.oid,'SELECT'),
  has_table_privilege('empire_closer_observer',c.oid,'INSERT'),
  has_table_privilege('empire_closer_observer',c.oid,'UPDATE'),
  has_table_privilege('empire_closer_observer',c.oid,'DELETE'),
  (SELECT count(*) FROM public.workspace_historical_sent_receipts)
  FROM pg_class c
  WHERE c.oid='public.workspace_historical_sent_receipts'::regclass;")" ||
  die POST_MIGRATION_CATALOG_UNAVAILABLE
[[ "$catalog" == $'t|t|1|t|f|f|f|0' ]] ||
  { echo "HOLD_POST_MIGRATION_RLS_TRIGGER_GRANT_OR_EMPTY_TABLE: $catalog" >&2;exit 4; }

read_status="$(
  curl -fsS --max-time 8 "$BASE_URL" |
  python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["status"]=="SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS"
assert d["database_historical_receipt_table_active"] is True
assert d["private_custody_receipts_verified"]==6
assert d["database_historical_receipts_verified"]==0
assert d["canonical_outbound_intents_created"]==0
assert d["crm_records_created"]==0
assert d["outbound_sent"] is False
print("PRIVATE_FOUNDER_READBACK_CONFIRMED")'
)" || die POST_MIGRATION_PRIVATE_READER_UNAVAILABLE
echo "$read_status"
echo 'EMPIREDB_MIGRATION_052_SCHEMA_VERIFIED'
echo 'historical_table=active rows=0 rls=forced append_only=yes'
echo 'historical_receipt_import=not_run crm_writes=no outbound_sent=no'
