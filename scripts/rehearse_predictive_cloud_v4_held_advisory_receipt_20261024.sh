#!/usr/bin/env bash
# Original Predictive Cloud V4.4: disposable PostgreSQL 18 advisory replay audit.
# No Redis network, production DB, service, consumer, funds, or outbound.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?isolated PG host required}" "${PGPORT:?isolated PG port required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
base=migrations/empiredb/064_predictive_v4_projection_outbox_held.sql
migration=migrations/empiredb/065_predictive_v4_advisory_replay_receipts_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c \
 'CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS'
createdb empire_v4_outbox_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c \
 'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
query(){ psql -XAtq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c "$1"; }
rejected(){
 local expected="$1"; shift
 local err
 err="$(mktemp /tmp/empire_v4_065_expected.XXXXXX)"
 if "$@" >"$err" 2>&1; then cat "$err";rm -f "$err";echo "UNEXPECTED_V4_065_ACCEPTED=$expected";exit 6; fi
 grep -Fq "$expected" "$err" || { cat "$err";rm -f "$err";exit 6; }
 rm -f "$err"
}
rejected V4_065_WRONG_DATABASE psql -Xq -v ON_ERROR_STOP=1 -d postgres -f "$migration"
rejected V4_065_ORIGINAL_HELD_OUTBOX_REQUIRED psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f "$migration"
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f "$base"
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f "$migration"
rejected V4_065_EXISTING_RECEIPTS_REQUIRES_REVIEW psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -f "$migration"
tenant='00000000-0000-0000-0000-000000000101'
other='00000000-0000-0000-0000-000000000102'
stage(){
 local rev="$1" digest="$2" kind="$3"
 query "SET ROLE empiredb_migrator;
 SELECT public.stage_empire_predictive_v4_projection_held(
 '$tenant','roofing',repeat('a',64),repeat('d',64),
 $rev,repeat('$digest',64),'$kind');"
}
observe(){
 local t="$1" digest="$2" stream="$3"
 query "SET ROLE empiredb_migrator;
 SELECT public.audit_empire_predictive_v4_stream_observation_held(
 '$t',repeat('$digest',64),'$stream');"
}
[[ "$(stage 2 b OBSERVED)" == *'HELD_STAGED'* ]]
[[ "$(stage 3 c OBSERVED)" == *'HELD_STAGED'* ]]
# No privileged direct insert may attach another tenant to this outbox event.
rejected 'violates foreign key constraint' psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator; INSERT INTO public.empire_predictive_v4_advisory_receipts_held
 (tenant_id,event_digest,first_stream_id,decision)
 VALUES('$other',repeat('b',64),'999-0','UNVERIFIED_BLOCKED')"
[[ "$(observe "$tenant" b '1000-0')" == *'SUPERSEDED_BLOCKED'* ]]
[[ "$(observe "$tenant" b '1001-0')" == *'DUPLICATE_HELD'* ]]
rejected V4_065_STREAM_ID_COLLISION psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;SELECT public.audit_empire_predictive_v4_stream_observation_held('$tenant',repeat('c',64),'1000-0')"
rejected V4_065_UNKNOWN_TENANT_EVENT psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;SELECT public.audit_empire_predictive_v4_stream_observation_held('$other',repeat('b',64),'1002-0')"
rejected V4_065_INVALID_HELD_OBSERVATION psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;SELECT public.audit_empire_predictive_v4_stream_observation_held('$tenant',repeat('c',64),'not-stream-id')"
# Two independent PostgreSQL connections race to record the same event with
# different Redis-like XADD IDs: unique event key permits one first receipt.
(
 observe "$tenant" c '2000-0' >/dev/null
) &
first=$!
(
 observe "$tenant" c '2001-0' >/dev/null
) &
second=$!
wait "$first"
wait "$second"
[[ "$(query "SELECT count(*) FROM public.empire_predictive_v4_advisory_receipts_held
 WHERE tenant_id='$tenant'")" == '2' ]]
[[ "$(observe "$tenant" c '2002-0')" == *'DUPLICATE_HELD'* ]]
[[ "$(stage 4 e WITHDRAWN)" == *'HELD_STAGED'* ]]
[[ "$(observe "$tenant" e '3000-0')" == *'WITHDRAWN_BLOCKED'* ]]
# Persistent in this database fixture across separate processes; no execution.
[[ "$(query "SELECT count(*),bool_and(receipt_state='HELD' AND
 NOT redis_acknowledged AND NOT action_executed AND NOT source_authorized)
 FROM public.empire_predictive_v4_advisory_receipts_held
 WHERE tenant_id='$tenant'")" == '3|t' ]]
query "CREATE ROLE empire_v4_receipt_unprivileged NOLOGIN" >/dev/null
[[ "$(query "SELECT has_table_privilege('empire_v4_receipt_unprivileged',
 'public.empire_predictive_v4_advisory_receipts_held','SELECT'),
 has_function_privilege('empire_v4_receipt_unprivileged',
 'public.audit_empire_predictive_v4_stream_observation_held(uuid,text,text)','EXECUTE')")" == 'f|f' ]]
rejected V4_065_APPEND_ONLY_RECEIPTS psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;UPDATE public.empire_predictive_v4_advisory_receipts_held SET decision='UNVERIFIED_BLOCKED' WHERE event_digest=repeat('b',64)"
rejected V4_065_APPEND_ONLY_RECEIPTS psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;DELETE FROM public.empire_predictive_v4_advisory_receipts_held WHERE event_digest=repeat('b',64)"
[[ "$(query "SELECT count(*) FROM pg_class WHERE relname='empire_predictive_v4_advisory_receipts_held'
 AND relrowsecurity AND relforcerowsecurity")" == 1 ]]
echo 'V4_065_ATOMIC_EVENT_DIGEST_DEDUP=PASS'
echo 'V4_065_CROSS_TENANT_STREAM_COLLISION_WITHDRAWAL=PASS'
echo 'V4_065_APPEND_ONLY_HELD_OWNER_RLS=PASS'
echo 'V4_065_DISPOSABLE_ONLY production_empiredb_writes=false redis_acknowledged=false executed=false'
