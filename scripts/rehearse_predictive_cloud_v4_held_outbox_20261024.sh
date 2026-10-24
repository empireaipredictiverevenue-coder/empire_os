#!/usr/bin/env bash
# Predictive Cloud V4.2 owner-held, disposable PostgreSQL 18 proof ONLY.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?disposable PG host required}" "${PGPORT:?disposable PG port required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
file=migrations/empiredb/064_predictive_v4_projection_outbox_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c \
 'CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS'
createdb empire_v4_outbox_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c \
 'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
query(){ psql -XAtq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c "$1"; }
rejected(){
 local expected="$1"; shift
 local err
 err="$(mktemp /tmp/empire_v4_064_expected.XXXXXX)"
 if "$@" >"$err" 2>&1; then cat "$err";rm -f "$err";echo "UNEXPECTED_V4_064_ACCEPTED=$expected";exit 6; fi
 grep -Fq "$expected" "$err" || { cat "$err";rm -f "$err";exit 6; }
 rm -f "$err"
}
rejected V4_064_WRONG_DATABASE psql -Xq -v ON_ERROR_STOP=1 -d postgres -f "$file"
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f "$file"
rejected V4_064_EXISTING_CONTRACT_REQUIRES_REVIEW psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f "$file"
[[ "$(query "SELECT count(*) FROM pg_class WHERE relname IN
 ('empire_predictive_v4_watermarks_held','empire_predictive_v4_outbox_held')
 AND relrowsecurity AND relforcerowsecurity")" == 2 ]]
query "CREATE ROLE empire_v4_unprivileged NOLOGIN" >/dev/null
[[ "$(query "SELECT has_table_privilege('empire_v4_unprivileged',
 'public.empire_predictive_v4_watermarks_held','SELECT'),
 has_table_privilege('empire_v4_unprivileged',
 'public.empire_predictive_v4_outbox_held','INSERT'),
 has_function_privilege('empire_v4_unprivileged',
 'public.stage_empire_predictive_v4_projection_held(uuid,text,text,text,bigint,text,text)','EXECUTE')")" == 'f|f|f' ]]
tenant='00000000-0000-0000-0000-000000000101'
other='00000000-0000-0000-0000-000000000102'
# All values are fictional opaque digests; no canonical CRM identities or contacts.
call(){
 local t="$1" revision="$2" evt="$3" kind="$4"
 query "SET ROLE empiredb_migrator;
 SELECT public.stage_empire_predictive_v4_projection_held(
 '$t','roofing',repeat('a',64),repeat('b',64),
 $revision,repeat('$evt',64),'$kind');"
}
[[ "$(call "$tenant" 13 c OBSERVED)" == *'HELD_STAGED'* ]]
[[ "$(call "$tenant" 13 c OBSERVED)" == *'HELD_DUPLICATE'* ]]
rejected V4_064_STALE_OR_WITHDRAWN psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;SELECT public.stage_empire_predictive_v4_projection_held('$tenant','roofing',repeat('a',64),repeat('b',64),12,repeat('d',64),'OBSERVED')"
# Use normal psql for remaining rejection tests to avoid any dependence on exception wrappers.
rejected V4_064_EVENT_IDENTITY_COLLISION psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;SELECT public.stage_empire_predictive_v4_projection_held('$other','roofing',repeat('a',64),repeat('b',64),13,repeat('c',64),'OBSERVED')"
[[ "$(call "$tenant" 14 e OBSERVED)" == *'HELD_STAGED'* ]]
[[ "$(call "$tenant" 15 f WITHDRAWN)" == *'HELD_STAGED'* ]]
rejected V4_064_STALE_OR_WITHDRAWN psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;SELECT public.stage_empire_predictive_v4_projection_held('$tenant','roofing',repeat('a',64),repeat('b',64),16,repeat('1',64),'OBSERVED')"
[[ "$(query "SELECT latest_revision,withdrawn,source_review_state
 FROM public.empire_predictive_v4_watermarks_held WHERE tenant_id='$tenant'")" == '15|t|UNVERIFIED' ]]
[[ "$(query "SELECT count(*),bool_and(delivery_state='HELD' AND execution_authority='none')
 FROM public.empire_predictive_v4_outbox_held WHERE tenant_id='$tenant'")" == '3|t' ]]
rejected V4_064_APPEND_ONLY_OUTBOX psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;DELETE FROM public.empire_predictive_v4_outbox_held WHERE event_digest=repeat('c',64)"
rejected V4_064_APPEND_ONLY_OUTBOX psql -Xq -v ON_ERROR_STOP=1 \
 -d empire_v4_outbox_fixture -c \
 "SET ROLE empiredb_migrator;UPDATE public.empire_predictive_v4_outbox_held SET revision=1 WHERE event_digest=repeat('c',64)"
# Concurrent, independent DB connections on a fresh tenant: final revision cannot regress.
[[ "$(call "$other" 2 2 OBSERVED)" == *'HELD_STAGED'* ]]
(
 call "$other" 4 4 OBSERVED >/tmp/empire_v4_064_concurrency_a.$$
) 2>/dev/null &
a_pid=$!
(
 call "$other" 5 5 OBSERVED >/tmp/empire_v4_064_concurrency_b.$$
) 2>/dev/null &
b_pid=$!
wait "$a_pid" || true
wait "$b_pid" || true
rm -f /tmp/empire_v4_064_concurrency_a.$$ /tmp/empire_v4_064_concurrency_b.$$
[[ "$(query "SELECT latest_revision FROM public.empire_predictive_v4_watermarks_held WHERE tenant_id='$other'")" == 5 ]]
# Exact owner-scope read-only snapshot, from the real temporary PG engine.
# This is NOT a production authorised tenant/source reader.
rejected 'permission denied for table empire_predictive_v4_outbox_held' \
 psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c \
 "SET ROLE empire_v4_unprivileged;SELECT count(*) FROM public.empire_predictive_v4_outbox_held"
payload="$(query "SET ROLE empiredb_migrator;
 BEGIN READ ONLY;
 SELECT jsonb_build_object('requested_tenant_id','$tenant',
 'rows',COALESCE(jsonb_agg(to_jsonb(x)),'[]'::jsonb))
 FROM (
   SELECT o.event_digest,o.tenant_id::text AS tenant_id,o.sector,
    o.entity_digest,o.source_evidence_digest,o.revision,o.event_kind,
    o.delivery_state,o.execution_authority,w.latest_revision,w.withdrawn,
    w.source_review_state,w.source_evidence_digest AS watermark_source_digest
   FROM public.empire_predictive_v4_outbox_held AS o
   JOIN public.empire_predictive_v4_watermarks_held AS w
     USING (tenant_id,sector,entity_digest)
   WHERE o.tenant_id='$tenant'::uuid
   ORDER BY o.revision,o.event_digest LIMIT 33
 ) AS x; COMMIT;")"
result="$(printf '%s' "$payload" | PYTHONPATH=. \
  /srv/empire_os/.venv/bin/python -B -m empire_os.predictive_cloud_v4_outbox_hold_reader)"
[[ "$result" == *'"reviewed_count":3'* ]]
[[ "$result" == *'"redis_publish_authorized":false'* ]]
[[ "$result" == *'"WITHDRAWN_SOURCE_HELD"'* ]]
[[ "$result" == *'"source_authority_verified":false'* ]]
echo 'V4_064_HELD_READER_SNAPSHOT=PASS'
echo 'V4_064_ATOMIC_REVISION_AND_TOMBSTONE_FIXTURE=PASS'
echo 'V4_064_OUTBOX_UNIQUE_RLS_OWNER_HELD=PASS'
echo 'V4_064_DISPOSABLE_ONLY production_empiredb_writes=false redis_published=false money_moved=false'
