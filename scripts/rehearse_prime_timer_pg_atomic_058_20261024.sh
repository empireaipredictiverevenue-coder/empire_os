#!/usr/bin/env bash
# Disposable PostgreSQL 18 fixture ONLY. Zero production access, sends or DB migration.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?pg_virtualenv required}"
: "${PGHOST:?pg_virtualenv socket required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && ((PGPORT >= 5433)) || {
  echo REFUSED_NON_EPHEMERAL_PGPORT; exit 9;
}
export PGDATABASE=postgres
directory="$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'SHOW data_directory')"
[[ "$directory" == /tmp/pg_virtualenv.*/data/* ]] || {
  echo REFUSED_NON_TEMPORARY_POSTGRES_CLUSTER; exit 9;
}
[[ "$(psql -X -Atq -c 'SELECT inet_server_port()')" == "$PGPORT" ]] || exit 9
tmp="$(mktemp -d /tmp/empire_timer_atomic_058.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
checks=0
pass(){ checks=$((checks+1)); echo "ATOMIC_058_PASS [$checks] $*"; }
sql(){ psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
execsql(){ psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1" >/dev/null; }
must_eq(){ local v="$1" expected="$2" desc="$3";
 [[ "$v" == "$expected" ]] || { echo "ATOMIC_ASSERT_FAILED $desc EXPECT=$expected GOT=$v"; exit 7; }; pass "$desc"; }
reject(){ local marker="$1"; shift;
 if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$*" >"$tmp/failed.out" 2>&1; then
  echo "UNEXPECTED_SQL_SUCCESS $marker"; exit 6;
 fi
 grep -Fq "$marker" "$tmp/failed.out" || {
  echo "WRONG_SQL_REJECTION $marker"; tail -12 "$tmp/failed.out"; exit 6;
 }
 pass "rejected $marker"
}
createdb empire_timer_fixture
execsql "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator"
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/057_flagship_voice_timer_ledger_held.sql
# The ordinary fixture owner role has no membership in the migrator.
if psql -X -v ON_ERROR_STOP=1 -d postgres -f migrations/empiredb/058_flagship_timer_atomic_transition_held.sql >"$tmp/wrong-db.log" 2>&1; then
 echo UNEXPECTED_058_NONCANONICAL_DB_SUCCESS; exit 6
fi
grep -Fq TIMER058_WRONG_DATABASE "$tmp/wrong-db.log"
pass 'wrong database refuses migration 058'
# Forced error after 058 DDL creation: transaction must roll back policies,
# trigger function, trigger and SECURITY DEFINER function together.
python3 - "$tmp/late.sql" <<'PY'
from pathlib import Path
import sys
s=Path("migrations/empiredb/058_flagship_timer_atomic_transition_held.sql").read_text()
assert s.endswith("COMMIT;\n")
Path(sys.argv[1]).write_text(s[:-8]+"SELECT 1 / 0;\nCOMMIT;\n")
PY
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "$tmp/late.sql" >"$tmp/late.log" 2>&1; then
 echo UNEXPECTED_058_LATE_ERROR_SUCCESS; exit 6;
fi
grep -Fq 'division by zero' "$tmp/late.log"
must_eq "$(sql "select count(*) from pg_policies where policyname like 'empire_prime_timer_held%'")" 0 'rollback removes RLS policies'
must_eq "$(sql "select count(*) from pg_proc where proname like 'empire_prime_voice_timer_%_held'")" 0 'rollback removes SQL functions'
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/058_flagship_timer_atomic_transition_held.sql
must_eq "$(sql "select count(*) from pg_policies where policyname like 'empire_prime_timer_held%'")" 2 'owner-scoped FORCE RLS policies installed'
must_eq "$(sql "select count(*) from pg_proc where proname in ('empire_prime_voice_timer_transition_held','empire_prime_voice_timer_insert_guard_held') and prosecdef")" 2 'function and insert guard are SECURITY DEFINER'
must_eq "$(sql "select count(*) from pg_proc p cross join lateral aclexplode(p.proacl) grants where p.proname in ('empire_prime_voice_timer_transition_held','empire_prime_voice_timer_insert_guard_held') and grants.grantee=0")" 0 'no PUBLIC EXECUTE permission on either function'
must_eq "$(sql "select count(*) from pg_trigger where tgname='empire_prime_timer_event_transition_held' and not tgisinternal")" 1 'database write-path event guard installed'
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f migrations/empiredb/058_flagship_timer_atomic_transition_held.sql >"$tmp/repeat.log" 2>&1; then
 echo UNEXPECTED_058_REAPPLY_SUCCESS; exit 6
fi
grep -Fq TIMER058_EXISTING_TRANSITION_NEEDS_OWNER_REVIEW "$tmp/repeat.log"
pass 're-applying 058 fails without overwrite'
execsql "CREATE ROLE timer_fixture_app NOLOGIN NOSUPERUSER NOBYPASSRLS; GRANT USAGE ON SCHEMA public TO timer_fixture_app"
t='123e4567-e89b-42d3-a456-426614174000'
t2='123e4567-e89b-42d3-a456-426614174001'
a="$(printf '%064d' 0 | tr 0 a)"
b="$(printf '%064d' 0 | tr 0 b)"
c="$(printf '%064d' 0 | tr 0 c)"
d="$(printf '%064d' 0 | tr 0 d)"
e="$(printf '%064d' 0 | tr 0 e)"
f="$(printf '%064d' 0 | tr 0 f)"
g="$(printf '%064d' 0 | tr 0 1)"
h="$(printf '%064d' 0 | tr 0 2)"
i="$(printf '%064d' 0 | tr 0 3)"
j="$(printf '%064d' 0 | tr 0 4)"
k="$(printf '%064d' 0 | tr 0 5)"
l="$(printf '%064d' 0 | tr 0 6)"
m="$(printf '%064d' 0 | tr 0 7)"
n="$(printf '%064d' 0 | tr 0 8)"
s="$(printf '%064d' 0 | tr 0 9)"
# e = source digest; f = immutable actor digest; fictional all-digest data.
seed(){
 local key="$1" ev="$2" delay="$3"
 execsql "WITH tm AS (SELECT pg_catalog.clock_timestamp()+('$delay seconds')::interval AS moment), r AS (
 INSERT INTO public.empire_prime_voice_timer_requests(
 tenant_id,timer_digest,actor_digest,source_attestation_digest,
 consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at)
 SELECT '$t','$key','$f','$e','$g','pilot.v1',3,moment,moment+interval '3 seconds'
 FROM tm RETURNING tenant_id,timer_digest,created_at,source_attestation_digest)
 INSERT INTO public.empire_prime_voice_timer_events(
 tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)
 SELECT tenant_id,timer_digest,1,'$ev','TIMER_CREATED',created_at,source_attestation_digest
 FROM r;"
}
# due, future, cancellation, concurrency, direct-invalid.
seed "$a" "$g" -8
seed "$b" "$h" 0
seed "$c" "$i" 0
seed "$d" "$j" -8
seed "$k" "$l" -8
pass 'five synthetic tenant-bound timers created through guarded insert trigger'
fn="public.empire_prime_voice_timer_transition_held"
reject 'permission denied for function empire_prime_voice_timer_transition_held' "SET ROLE timer_fixture_app; SELECT * FROM $fn('$t','$a','DISPATCH_CLAIMED','$m','$e')"
reject TIMER058_UNKNOWN_OR_WRONG_TENANT_TIMER "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t2','$a','DISPATCH_CLAIMED','$m','$e')"
reject TIMER058_SOURCE_DIGEST_MISMATCH "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t','$a','DISPATCH_CLAIMED','$m','$s')"
reject TIMER058_RESTRICTED_SYNTHETIC_ARGUMENTS_REQUIRED "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t','$a','PROVIDER_DELIVERED_REPORTED','$m','$e')"
reject TIMER058_CLAIM_NOT_YET_DUE "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t','$b','DISPATCH_CLAIMED','$m','$e')"
must_eq "$(sql "SET ROLE empiredb_migrator; SELECT seq,state_code FROM $fn('$t','$c','TIMER_CANCELLED','$m','$e')")" '2|HELD_CANCEL_NO_EXTERNAL_DISPATCH' 'future timer cancellation is atomic'
reject TIMER058_ALREADY_TRANSITIONED_OR_CLOSED "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t','$c','DISPATCH_CLAIMED','$n','$e')"
reject TIMER058_CANCELLATION_AFTER_DUE_REFUSED "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t','$a','TIMER_CANCELLED','$n','$e')"
must_eq "$(sql "SET ROLE empiredb_migrator; SELECT seq,state_code FROM $fn('$t','$a','DISPATCH_CLAIMED','$n','$e')")" '2|HELD_CLAIM_NO_EXTERNAL_DISPATCH' 'due claim inserts exactly one held event'
reject TIMER058_ALREADY_TRANSITIONED_OR_CLOSED "SET ROLE empiredb_migrator; SELECT * FROM $fn('$t','$a','DISPATCH_CLAIMED','$s','$e')"
must_eq "$(sql "select count(*) from public.empire_prime_voice_timer_events where tenant_id='$t' and timer_digest='$a' and event_kind='DISPATCH_CLAIMED'")" 1 'replayed claim cannot duplicate delivery ownership'
# Previous 057 semantic gap must be closed by real PostgreSQL trigger.
reject TIMER058_ILLEGAL_OR_UNDUE_TRANSITION "INSERT INTO public.empire_prime_voice_timer_events(tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest,provider_receipt_digest) VALUES ('$t','$k',2,'$s','PROVIDER_DELIVERED_REPORTED',clock_timestamp(),'$e','$m')"
pass 'direct superuser INSERT cannot skip provider state'
# Create a provider acceptance and delivery report only after claim. This
# is still NOT independently authenticated delivery.
execsql "INSERT INTO public.empire_prime_voice_timer_events(tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest,provider_receipt_digest) VALUES ('$t','$a',3,'$s','PROVIDER_ACCEPTED_REPORTED',clock_timestamp(),'$e','$m')"
execsql "INSERT INTO public.empire_prime_voice_timer_events(tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest,provider_receipt_digest) VALUES ('$t','$a',4,'$b','PROVIDER_DELIVERED_REPORTED',clock_timestamp(),'$e','$m')"
pass 'ordered synthetic provider reports stored, authenticity still unverified'
reject TIMER058_ILLEGAL_OR_UNDUE_TRANSITION "INSERT INTO public.empire_prime_voice_timer_events(tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest,provider_receipt_digest) VALUES ('$t','$a',5,'$c','PROVIDER_DELIVERED_REPORTED',clock_timestamp(),'$e','$m')"
reject TIMER058_INSERT_UNKNOWN_TENANT_OR_SOURCE "INSERT INTO public.empire_prime_voice_timer_events(tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest) VALUES ('$t','$b',2,'$s','TIMER_CANCELLED',clock_timestamp(),'$n')"
# Race: first worker holds the request-row lock until COMMIT; second worker
# waits then observes it is already claimed. No notification provider exists.
# Use unique digest values for each independent worker; the ledger's
# tenant-wide unique event fingerprint prevents accidental reuse elsewhere.
worker_event_one="$(printf '%064d' 0 | tr 0 0)"
worker_event_two="$(printf '%064d' 0 | tr 0 f)"
(
 psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "BEGIN; SET ROLE empiredb_migrator; SELECT seq,state_code FROM $fn('$t','$d','DISPATCH_CLAIMED','$worker_event_one','$e'); SELECT pg_sleep(1.5); COMMIT;" >"$tmp/worker1.log" 2>&1
) &
worker1=$!
sleep 0.35
if psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "SET ROLE empiredb_migrator; SELECT seq,state_code FROM $fn('$t','$d','DISPATCH_CLAIMED','$worker_event_two','$e')" >"$tmp/worker2.log" 2>&1; then
 echo 'SECOND_WORKER_WON_DUPLICATE_CLAIM'; wait "$worker1"; exit 6
fi
wait "$worker1"
grep -Fq 'HELD_CLAIM_NO_EXTERNAL_DISPATCH' "$tmp/worker1.log"
grep -Fq 'TIMER058_ALREADY_TRANSITIONED_OR_CLOSED' "$tmp/worker2.log"
pass 'two concurrent workers yield one atomic claim and one refused replay'
must_eq "$(sql "select count(*) from public.empire_prime_voice_timer_events where tenant_id='$t' and timer_digest='$d' and event_kind='DISPATCH_CLAIMED'")" 1 'single DB event after concurrent claim'
must_eq "$(sql "select count(*) from public.empire_prime_voice_timer_events where event_kind='PROVIDER_DELIVERED_REPORTED'")" 1 'only intentionally ordered unverified provider report exists'
must_eq "$(sql "select count(*) from pg_policies where policyname like 'empire_prime_timer_held%' and roles::text not like '%empiredb_migrator%'")" 0 'no application role added to RLS policies'
echo "EPHEMERAL_PG058_ATOMIC_TRANSITIONS_PASS checks=$checks port=$PGPORT production_touched=false external_notifications=0 runtime_grants=0 original_empiredb_writes=false"
