#!/usr/bin/env bash
# Real PostgreSQL fixture for HELD EmpireDB 057, 058, 059 only.
# Refuses canonical server; never runs a provider, dispatcher or outbound.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?temporary pg_virtualenv port required}"
: "${PGHOST:?temporary pg_virtualenv socket required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && ((PGPORT >= 5433)) || {
 echo REFUSED_NON_EPHEMERAL_PGPORT; exit 9;
}
export PGDATABASE=postgres
directory="$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'SHOW data_directory;')"
[[ "$directory" == /tmp/pg_virtualenv.*/data/* ]] || {
 echo REFUSED_NON_TEMPORARY_POSTGRES_CLUSTER; exit 9;
}
[[ "$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'SELECT inet_server_port()')" == "$PGPORT" ]] || exit 9
tmp="$(mktemp -d /tmp/empire_timer_receipts_059.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
checks=0
pass(){ checks=$((checks+1)); echo "RECEIPT_059_PASS [$checks] $*"; }
sql(){ psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
execsql(){ psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1" >/dev/null; }
same(){ local actual="$1" expected="$2" label="$3";
 [[ "$actual" == "$expected" ]] || {
 echo "FIXTURE_059_ASSERT_FAILED [$label] expected:$expected got:$actual"; exit 7;
 }; pass "$label"; }
reject(){ local marker="$1"; shift;
 if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$*" >"$tmp/reject.log" 2>&1; then
   echo "UNEXPECTED_SQL_SUCCESS [$marker]"; exit 6;
 fi
 grep -Fq "$marker" "$tmp/reject.log" || {
   echo "INCORRECT_SQL_FAILURE [$marker]"; tail -13 "$tmp/reject.log"; exit 6;
 }
 pass "rejected $marker"
}
createdb empire_timer_fixture
# Guards must refuse wrong DB and missing canonical baseline schema.
if psql -X -v ON_ERROR_STOP=1 -d postgres -f migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql >"$tmp/wrong.log" 2>&1; then
 echo WRONG_DATABASE_WAS_ACCEPTED; exit 6;
fi
grep -Fq TIMER059_WRONG_DATABASE "$tmp/wrong.log"
pass 'wrong database rejected'
execsql "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator"
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql >"$tmp/missing.log" 2>&1; then
 echo MISSING_PREDECESSOR_WAS_ACCEPTED; exit 6;
fi
grep -Fq TIMER059_REQUIRES_ORIGINAL_LEDGER_057_AND_GUARD_058 "$tmp/missing.log"
pass '057 and 058 dependency enforced'
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/057_flagship_voice_timer_ledger_held.sql
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/058_flagship_timer_atomic_transition_held.sql

# DDL rollback after full CREATE TABLE/trigger/function/policy.
python3 - "$tmp/forced-late-error.sql" <<'PY'
from pathlib import Path
import sys
s=Path("migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql").read_text()
assert s.endswith("COMMIT;\n")
Path(sys.argv[1]).write_text(s[:-8]+"SELECT 1 / 0;\nCOMMIT;\n")
PY
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "$tmp/forced-late-error.sql" >"$tmp/late.log" 2>&1; then
 echo LATE_DDL_ERROR_WAS_ACCEPTED; exit 6;
fi
grep -Fq 'division by zero' "$tmp/late.log"
same "$(sql "select count(*) from pg_class where relname='empire_prime_timer_provider_receipts'")" 0 'late error rolls back receipt table'
same "$(sql "select count(*) from pg_proc where proname='empire_prime_timer_provider_receipt_guard_held'")" 0 'late error rolls back receipt guard'
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql
same "$(sql "select count(*) from pg_class where relname='empire_prime_timer_provider_receipts' and relrowsecurity and relforcerowsecurity")" 1 'receipt table FORCE RLS enabled'
same "$(sql "select count(*) from pg_policies where tablename='empire_prime_timer_provider_receipts' and roles::text like '%empiredb_migrator%'")" 1 'migration owner-only RLS policy'
same "$(sql "select count(*) from pg_proc p cross join lateral aclexplode(p.proacl) acl where p.proname='empire_prime_timer_provider_receipt_guard_held' and acl.grantee=0")" 0 'no PUBLIC EXECUTE on receipt guard'
same "$(sql "select count(*) from pg_trigger where tgname IN ('empire_prime_timer_receipt_insert_guard','empire_prime_timer_receipt_immutable') and not tgisinternal")" 2 'insert guard and append-only trigger'
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql >"$tmp/repeat.log" 2>&1; then
 echo REAPPLY_059_WAS_ACCEPTED; exit 6;
fi
grep -Fq TIMER059_ALREADY_PRESENT_REQUIRE_OWNER_REVIEW "$tmp/repeat.log"
pass 'repeat migration refused'

t='123e4567-e89b-42d3-a456-426614174000'
t2='123e4567-e89b-42d3-a456-426614174001'
hex(){ printf '%064d' "$1"; }
a="$(hex 1)"; b="$(hex 2)"; c="$(hex 3)"
source_ref="$(hex 900)"; actor="$(hex 901)"; consent="$(hex 902)"
claim_a="$(hex 101)"; claim_b="$(hex 102)"; claim_c="$(hex 103)"
provider='synthetic_fixture'
reference_a="$(hex 201)"; reference_b="$(hex 202)"; reference_c="$(hex 203)"
# Three already-due SYNTHETIC timers; each 058 claim must be atomic.
create_timer(){
 local timer="$1" first="$2" claimed="$3"
 execsql "WITH ts AS (SELECT clock_timestamp()-interval '8 seconds' AS moment),
 created AS (INSERT INTO public.empire_prime_voice_timer_requests(
    tenant_id,timer_digest,actor_digest,source_attestation_digest,
    consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at)
    SELECT '$t','$timer','$actor','$source_ref','$consent','pilot.v1',3,
           moment,moment+interval '3 seconds' FROM ts
    RETURNING tenant_id,timer_digest,created_at,source_attestation_digest)
 INSERT INTO public.empire_prime_voice_timer_events(
    tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)
 SELECT tenant_id,timer_digest,1,'$first','TIMER_CREATED',created_at,source_attestation_digest
 FROM created;"
 same "$(sql "SET ROLE empiredb_migrator; SELECT seq FROM public.empire_prime_voice_timer_transition_held('$t','$timer','DISPATCH_CLAIMED','$claimed','$source_ref')")" 2 "atomic original 058 claimed timer $timer"
}
create_timer "$a" "$(hex 11)" "$claim_a"
create_timer "$b" "$(hex 12)" "$claim_b"
create_timer "$c" "$(hex 13)" "$claim_c"
# All SQL uses strictly synthetic test references. No callback endpoint.
receipt_insert(){
 local timer="$1" cl="$2" ref="$3" nonce="$4" content="$5" stage="$6" seq="$7" provider_code="${8:-$provider}" tenant="${9:-$t}" source="${10:-$source_ref}"
 echo "INSERT INTO public.empire_prime_timer_provider_receipts(
  tenant_id,timer_digest,provider_code,callback_nonce_digest,receipt_digest,
  claim_event_digest,delivery_reference_digest,source_attestation_digest,
  callback_stage,callback_seq,provider_reported_at)
 VALUES ('$tenant','$timer','$provider_code','$nonce','$content',
         '$cl','$ref','$source','$stage',$seq,clock_timestamp())"
}
nonce1="$(hex 301)"; nonce2="$(hex 302)"; nonce3="$(hex 303)"; nonce4="$(hex 304)"
receipt1="$(hex 401)"; receipt2="$(hex 402)"; receipt3="$(hex 403)"
# No delivery is permitted before provider acceptance, even from superuser.
reject TIMER059_FIRST_RECEIPT_MUST_ACCEPT_OR_FAIL "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce1" "$receipt1" DELIVERED 1)"
reject TIMER059_ATOMIC_CLAIM_BINDING_REQUIRED "$(receipt_insert "$a" "$claim_b" "$reference_a" "$nonce1" "$receipt1" ACCEPTED 1)"
reject TIMER059_TENANT_OR_SOURCE_BINDING_REFUSED "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce1" "$receipt1" ACCEPTED 1 "$provider" "$t2")"
reject TIMER059_TENANT_OR_SOURCE_BINDING_REFUSED "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce1" "$receipt1" ACCEPTED 1 "$provider" "$t" "$(hex 999)")"
execsql "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce1" "$receipt1" ACCEPTED 1)"
same "$(sql "select count(*) from public.empire_prime_timer_provider_receipts where tenant_id='$t' and timer_digest='$a'")" 1 'first ACCEPTED callback is stored'
# Re-open independent psql sessions to model restarts. Persistent nonce
# uniqueness across *timers* means a replay cannot be reassigned to another.
reject 'duplicate key value violates unique constraint' "$(receipt_insert "$b" "$claim_b" "$reference_b" "$nonce1" "$receipt2" ACCEPTED 1)"
reject 'duplicate key value violates unique constraint' "$(receipt_insert "$b" "$claim_b" "$reference_b" "$nonce3" "$receipt1" ACCEPTED 1)"
reject TIMER059_ILLEGAL_OR_REPLAYED_RECEIPT_TRANSITION "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce3" "$receipt3" ACCEPTED 2)"
reject TIMER059_ILLEGAL_OR_REPLAYED_RECEIPT_TRANSITION "$(receipt_insert "$a" "$claim_a" "$reference_b" "$nonce3" "$receipt3" DELIVERED 2)"
execsql "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce2" "$receipt2" DELIVERED 2)"
same "$(sql "select string_agg(callback_stage,',' order by callback_seq) from public.empire_prime_timer_provider_receipts where tenant_id='$t' and timer_digest='$a'")" 'ACCEPTED,DELIVERED' 'ordered callback chain persisted in PostgreSQL'
reject 'duplicate key value violates unique constraint' "$(receipt_insert "$b" "$claim_b" "$reference_b" "$nonce2" "$receipt3" ACCEPTED 1)"
reject TIMER059_TERMINAL_RECEIPT_NO_RETRY "$(receipt_insert "$a" "$claim_a" "$reference_a" "$nonce4" "$receipt3" FAILED 2)"
reject TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE "UPDATE public.empire_prime_timer_provider_receipts SET callback_stage='FAILED' WHERE tenant_id='$t' AND timer_digest='$a'"
reject TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE "DELETE FROM public.empire_prime_timer_provider_receipts WHERE tenant_id='$t' AND timer_digest='$a'"
# FAILED can be the first and terminal callback.
execsql "$(receipt_insert "$b" "$claim_b" "$reference_b" "$nonce3" "$receipt3" FAILED 1)"
reject TIMER059_ILLEGAL_OR_REPLAYED_RECEIPT_TRANSITION "$(receipt_insert "$b" "$claim_b" "$reference_b" "$nonce4" "$(hex 404)" DELIVERED 2)"
# Real separate DB role without RLS policy gets no rows. Grants here are
# fixture-only and are NEVER part of migration 059.
execsql "CREATE ROLE timer_fixture_receipt_reader NOLOGIN NOSUPERUSER NOBYPASSRLS;
 GRANT USAGE ON SCHEMA public TO timer_fixture_receipt_reader;
 GRANT SELECT,INSERT ON public.empire_prime_timer_provider_receipts
     TO timer_fixture_receipt_reader"
same "$(sql "SET ROLE timer_fixture_receipt_reader; SELECT count(*) FROM public.empire_prime_timer_provider_receipts")" 0 'FORCE RLS hides synthetic callbacks from fixture role'
reject 'new row violates row-level security policy' "SET ROLE timer_fixture_receipt_reader; $(receipt_insert "$c" "$claim_c" "$reference_c" "$(hex 309)" "$(hex 409)" ACCEPTED 1)"
same "$(sql "select count(*) from public.empire_prime_timer_provider_receipts")" 3 'only three legally ordered receipt rows stored'
same "$(sql "select count(*) from pg_proc where proname like 'empire_prime_timer_provider_send%'")" 0 'no sender or delivery RPC installed'
# Two real concurrent PostgreSQL sessions compete to record the SAME
# opaque nonce under two different timers. One transaction holds its
# unique-index conflict until COMMIT; the second must be refused.
race_timer1="$(hex 44)"; race_timer2="$(hex 45)"
create_timer "$race_timer1" "$(hex 144)" "$(hex 145)"
create_timer "$race_timer2" "$(hex 146)" "$(hex 147)"
race_nonce="$(hex 333)"
(
 psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "BEGIN;
 $(receipt_insert "$race_timer1" "$(hex 145)" "$(hex 244)" "$race_nonce" "$(hex 444)" ACCEPTED 1);
 SELECT pg_sleep(1.4);
 COMMIT;" >"$tmp/receipt-worker1.log" 2>&1
) &
worker1=$!
sleep 0.35
if psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$(receipt_insert "$race_timer2" "$(hex 147)" "$(hex 245)" "$race_nonce" "$(hex 445)" ACCEPTED 1)" >"$tmp/receipt-worker2.log" 2>&1; then
 echo 'CONCURRENT_DUPLICATE_NONCE_INSERT_SUCCEEDED'; wait "$worker1"; exit 6;
fi
wait "$worker1"
grep -Fq 'duplicate key value violates unique constraint' "$tmp/receipt-worker2.log"
pass 'two competing PostgreSQL sessions cannot record same callback nonce twice'
same "$(sql "select count(*) from public.empire_prime_timer_provider_receipts where callback_nonce_digest='$race_nonce'")" 1 'one persisted callback nonce after concurrent race'
echo "EPHEMERAL_PG059_RECEIPT_CUSTODY_PASS checks=$checks port=$PGPORT persisted_only_in_disposable_fixture=true provider_network_calls=0 production_touched=false"
