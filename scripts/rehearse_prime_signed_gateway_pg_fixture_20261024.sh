#!/usr/bin/env bash
# ORIGINAL EMPIREOS: isolated test-only ASTRA signed gateway -> held 059 ledger.
# NEVER run against original production EmpireDB or an unverified PostgreSQL.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?pg_virtualenv disposable port required}"
: "${PGHOST:?pg_virtualenv host required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && ((PGPORT >= 5433)) || {
 echo "REFUSED_NON_EPHEMERAL_PGPORT"; exit 9;
}
[[ "$PGHOST" == localhost || "$PGHOST" == 127.0.0.1 || "$PGHOST" == "::1" ]] || {
 echo "REFUSED_UNEXPECTED_POSTGRES_HOST"; exit 9;
}
export PGDATABASE=postgres
directory="$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'SHOW data_directory')"
[[ "$directory" == /tmp/pg_virtualenv.*/data/18/regress ]] || {
 echo "REFUSED_NON_TEMPORARY_POSTGRES_DATA_DIR"; exit 9;
}
[[ "$(psql -X -Atq -c 'select inet_server_port()')" == "$PGPORT" ]] || {
 echo "REFUSED_MISMATCHED_POSTGRES_SERVER"; exit 9;
}
createdb empire_timer_fixture
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;"
for part in \
  057_flagship_voice_timer_ledger_held \
  058_flagship_timer_atomic_transition_held \
  059_flagship_timer_provider_receipt_custody_held \
  060_flagship_timer_receipt_restricted_writer_held; do
  psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "migrations/empiredb/${part}.sql" >/dev/null
done
# TEST-ONLY privilege boundary, never part of held migration 060.
# This fixture role has no LOGIN, membership, table INSERT or SELECT.
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 CREATE ROLE timer_fixture_gateway_exec NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
 GRANT USAGE ON SCHEMA public TO timer_fixture_gateway_exec;
 GRANT EXECUTE ON FUNCTION public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz) TO timer_fixture_gateway_exec;"
# Prove the fixture role has only the one specific function, no direct table access.
psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 SELECT has_table_privilege('timer_fixture_gateway_exec','public.empire_prime_timer_provider_receipts','INSERT'),
        has_table_privilege('timer_fixture_gateway_exec','public.empire_prime_timer_provider_receipts','SELECT'),
        has_function_privilege('timer_fixture_gateway_exec',
          'public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz)','EXECUTE');" \
  | grep -Fxq 'f|f|t' || { echo RESTRICTED_WRITER_ROLE_PERMISSION_FAILURE; exit 6; }
echo RESTRICTED_GATEWAY_FIXTURE_ROLE_NO_TABLE_PERMISSIONS=true
export PGDATABASE=empire_timer_fixture
export EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED=ephemeral
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
    scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py
# A fresh, restricted SQL worker must NOT read or directly INSERT into 059.
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -c   "SET ROLE timer_fixture_gateway_exec; SELECT count(*) FROM public.empire_prime_timer_provider_receipts"   >/tmp/empire_timer_060_denied_$$.log 2>&1; then
  echo 'UNEXPECTED_060_RUNTIME_TABLE_READ'; exit 6
fi
grep -Fq 'permission denied for table empire_prime_timer_provider_receipts'   /tmp/empire_timer_060_denied_$$.log || { cat /tmp/empire_timer_060_denied_$$.log; exit 6; }
rm -f /tmp/empire_timer_060_denied_$$.log
echo 'RESTRICTED_060_DIRECT_TABLE_SELECT_DENIED=true'
# Concurrency test: two independent sessions use only the restricted
# function for the SAME timer. One claim wins; one loses after row lock.
t='123e4567-e89b-42d3-a456-426614174000'
hex(){ printf '%064d' "$1"; }
timer="$(hex 710)"; src="$(hex 711)"; claim="$(hex 712)"
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 WITH moment AS (SELECT clock_timestamp()-interval '10 seconds' AS created),
 request AS (
 INSERT INTO public.empire_prime_voice_timer_requests(
 tenant_id,timer_digest,actor_digest,source_attestation_digest,
 consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at)
 SELECT '$t','$timer','$(hex 713)','$src','$(hex 714)',
        'pilot.v1',3,created,created+interval '3 seconds' FROM moment
 RETURNING tenant_id,timer_digest,created_at,source_attestation_digest)
 INSERT INTO public.empire_prime_voice_timer_events(
 tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)
 SELECT tenant_id,timer_digest,1,'$(hex 715)','TIMER_CREATED',created_at,
 source_attestation_digest FROM request;
 SELECT seq FROM public.empire_prime_voice_timer_transition_held(
 '$t','$timer','DISPATCH_CLAIMED','$claim','$src');" >/dev/null
pfunc='public.empire_prime_timer_receipt_record_held'
callback(){
 local nonce="$1" receipt="$2"
 echo "SELECT held_receipt_seq,held_status FROM $pfunc(
 '$t','$timer','synthetic_local_receipt_fixture','$nonce','$receipt',
 '$claim','$(hex 716)','$src','ACCEPTED',clock_timestamp());"
}
tmp="$(mktemp -d /tmp/empire_timer_060_race.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
(
 psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c  "BEGIN; SET ROLE timer_fixture_gateway_exec;
 $(callback "$(hex 717)" "$(hex 718)")
 SELECT pg_sleep(1.4); COMMIT;" >"$tmp/first.log" 2>&1
) &
worker=$!
sleep 0.35
if psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c  "SET ROLE timer_fixture_gateway_exec; $(callback "$(hex 719)" "$(hex 720)")"  >"$tmp/second.log" 2>&1; then
 echo 'UNEXPECTED_060_DUPLICATE_ACCEPTED_CALLBACK'; wait "$worker"; exit 6
fi
wait "$worker"
grep -Fq 'HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED' "$tmp/first.log"
grep -Fq 'TIMER059_ILLEGAL_OR_REPLAYED_RECEIPT_TRANSITION' "$tmp/second.log"
[[ "$(psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c  "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer'")" == '1' ]] || {
 echo '060_CONCURRENT_RECEIPT_COUNT_MISMATCH'; exit 6;
}
echo 'RESTRICTED_060_TWO_WORKERS_ONE_CALLBACK=true'

echo "SIGNED_GATEWAY_060_RESTRICTED_PG_FIXTURE_FINISHED production_touched=false provider_network_calls=0"
