#!/usr/bin/env bash
# Execute ONLY inside pg_virtualenv -t. No production DB access/mutations.
# Runs original held EmpireDB 057 DDL in disposable PostgreSQL and proves
# rollbacks, FORCE RLS, constraints, immutability and denied runtime authority.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?Requires an isolated pg_virtualenv cluster}"
: "${PGHOST:?Requires a temporary local postgres socket}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || {
  echo 'REFUSED_NON_EPHEMERAL_PGPORT'; exit 9;
}
export PGDATABASE=postgres
dir="$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'SHOW data_directory;')"
[[ "$dir" == /tmp/pg_virtualenv.*/data/* ]] || {
  echo 'REFUSED_NON_TEMPORARY_PG_DATA_DIRECTORY'; exit 9;
}
[[ "$(psql -X -Atq -c 'SELECT inet_server_port()')" == "$PGPORT" ]] || {
  echo 'REFUSED_MISMATCHED_POSTGRES_CLUSTER'; exit 9;
}
tmp="$(mktemp -d /tmp/empire_prime_timer_fixture_057.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
sql="$(pwd)/migrations/empiredb/057_flagship_voice_timer_ledger_held.sql"
observations=0
ok() { observations=$((observations+1)); echo "FIXTURE_PASS [$observations] $*"; }
query() { psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
doit() { psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1" >/dev/null; }
expect_fail() {
  local needle="$1"; shift
  if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$*" >"$tmp/fail.log" 2>&1; then
     echo "UNEXPECTED_SQL_SUCCESS [$needle]"; exit 6
  fi
  grep -Fq "$needle" "$tmp/fail.log" || {
     echo "WRONG_SQL_FAILURE [$needle]"; cat "$tmp/fail.log"; exit 6;
  }
  ok "rejected: $needle"
}
assert_eq() {
  local actual="$1" expected="$2" label="$3"
  [[ "$actual" == "$expected" ]] || {
    printf "FIXTURE_ASSERTION_FAILED [%s] expected='%s' actual='%s'\n" "$label" "$expected" "$actual"; exit 7;
  }
  ok "$label"
}
createdb empire_timer_fixture
# Safety guard: no role, wrong DB, or already-applied structures.
if psql -X -v ON_ERROR_STOP=1 -d postgres -f "$sql" >"$tmp/wrong-db.log" 2>&1; then
  echo "UNEXPECTED_DDL_WRONG_DB_SUCCESS"; exit 6;
fi
grep -Fq 'TIMER057_WRONG_DATABASE' "$tmp/wrong-db.log"
ok 'nonallowlisted database rejects migration'
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "$sql" >"$tmp/no-role.log" 2>&1; then
  echo "UNEXPECTED_DDL_WITHOUT_MIGRATOR"; exit 6;
fi
grep -Fq 'TIMER057_CANONICAL_MIGRATOR_UNVERIFIED' "$tmp/no-role.log"
assert_eq "$(query "select count(*) from pg_class where relname in ('empire_prime_voice_timer_requests','empire_prime_voice_timer_events')")" '0' 'role guard cannot leave partial tables'
doit "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;"
doit "GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;"
# Deliberately force an error AFTER all DDL in a single transaction: prove rollback.
python3 - "$sql" "$tmp/late-abort.sql" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
assert s.endswith("COMMIT;\n")
Path(sys.argv[2]).write_text(s[:-8] + "SELECT 1 / 0;\nCOMMIT;\n")
PY
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "$tmp/late-abort.sql" >"$tmp/forced-abort.log" 2>&1; then
 echo 'UNEXPECTED_LATE_ABORT_SUCCESS'; exit 6;
fi
grep -Fq 'division by zero' "$tmp/forced-abort.log"
assert_eq "$(query "select count(*) from pg_class where relname in ('empire_prime_voice_timer_requests','empire_prime_voice_timer_events')")" '0' 'late DDL error rolls back all tables'
assert_eq "$(query "select count(*) from pg_proc where proname = 'empire_prime_voice_timer_immutable'")" '0' 'late DDL error rolls back trigger function'
# Execute the actual canonical held migration against this isolated fixture only.
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "$sql" >"$tmp/migration.log"
assert_eq "$(query "select count(*) from pg_class where relname in ('empire_prime_voice_timer_requests','empire_prime_voice_timer_events')")" '2' '057 DDL applied to disposable PostgreSQL'
assert_eq "$(query "select count(*) from pg_class where relname in ('empire_prime_voice_timer_requests','empire_prime_voice_timer_events') and relrowsecurity and relforcerowsecurity")" '2' 'both tables have FORCE RLS'
assert_eq "$(query "select count(*) from pg_policies where tablename like 'empire_prime_voice_timer_%'")" '0' 'no RLS access policy created'
assert_eq "$(query "select count(*) from pg_roles where rolname='empiredb_migrator' and not rolcanlogin and not rolsuper and not rolbypassrls and not rolcreatedb and not rolcreaterole")" '1' 'migrator remains NOLOGIN and nonprivileged'
assert_eq "$(query "select count(*) from information_schema.role_table_grants where table_name like 'empire_prime_voice_timer_%' and grantee='PUBLIC'")" '0' 'no PUBLIC table grants'
# Existing-object guard: repeat apply must fail with no mutation.
if psql -X -v ON_ERROR_STOP=1 -d empire_timer_fixture -f "$sql" >"$tmp/repeat.log" 2>&1; then
 echo 'UNEXPECTED_REPEATED_MIGRATION_SUCCESS'; exit 6;
fi
grep -Fq 'TIMER057_EXISTING_OBJECTS_REQUIRE_OWNER_RECONCILIATION' "$tmp/repeat.log"
ok 'second migration invocation blocked'
# Synthetic opaque fixture: no customer data, no real consent.
t='123e4567-e89b-42d3-a456-426614174000'
t2='123e4567-e89b-42d3-a456-426614174001'
a="$(printf '%064d' 0 | tr 0 a)"
b="$(printf '%064d' 0 | tr 0 b)"
c="$(printf '%064d' 0 | tr 0 c)"
e="$(printf '%064d' 0 | tr 0 e)"
f="$(printf '%064d' 0 | tr 0 f)"
req_values="'$t','$a','$b','$c','$e','pilot.v1',2,'2026-10-24 12:00:00+00','2026-10-24 12:00:02+00'"
doit "INSERT INTO public.empire_prime_voice_timer_requests(tenant_id,timer_digest,actor_digest,source_attestation_digest,consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at) VALUES ($req_values)"
assert_eq "$(query 'select count(*) from public.empire_prime_voice_timer_requests')" '1' 'fixture-only canonical timer request row inserted by superuser'
expect_fail 'duplicate key value violates unique constraint' "INSERT INTO public.empire_prime_voice_timer_requests(tenant_id,timer_digest,actor_digest,source_attestation_digest,consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at) VALUES ($req_values)"
expect_fail 'violates check constraint' "INSERT INTO public.empire_prime_voice_timer_requests(tenant_id,timer_digest,actor_digest,source_attestation_digest,consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at) VALUES ('$t','$b','$b','$c','$e','pilot.v1',2,'2026-10-24 12:00:00+00','2026-10-24 12:00:03+00')"
expect_fail 'violates check constraint' "INSERT INTO public.empire_prime_voice_timer_requests(tenant_id,timer_digest,actor_digest,source_attestation_digest,consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at) VALUES ('$t','$b','$b','$c','$e','pilot.v1',3601,'2026-10-24 12:00:00+00','2026-10-24 13:00:01+00')"
ev="INSERT INTO public.empire_prime_voice_timer_events(tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)"
doit "$ev VALUES ('$t','$a',1,'$b','TIMER_CREATED','2026-10-24 12:00:00+00','$c')"
assert_eq "$(query 'select count(*) from public.empire_prime_voice_timer_events')" '1' 'synthetic CREATE event accepted with FK'
expect_fail 'duplicate key value violates unique constraint' "$ev VALUES ('$t','$a',1,'$f','DISPATCH_CLAIMED','2026-10-24 12:00:02+00','$c')"
expect_fail 'duplicate key value violates unique constraint' "$ev VALUES ('$t','$a',2,'$b','DISPATCH_CLAIMED','2026-10-24 12:00:02+00','$c')"
expect_fail 'violates foreign key constraint' "$ev VALUES ('$t2','$a',1,'$f','TIMER_CREATED','2026-10-24 12:00:00+00','$c')"
expect_fail 'violates check constraint' "$ev VALUES ('$t','$a',2,'$f','PROVIDER_ACCEPTED_REPORTED','2026-10-24 12:00:02+00','$c')"
expect_fail 'TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE' "UPDATE public.empire_prime_voice_timer_requests SET duration_seconds=3 WHERE tenant_id='$t' AND timer_digest='$a'"
expect_fail 'TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE' "DELETE FROM public.empire_prime_voice_timer_requests WHERE tenant_id='$t' AND timer_digest='$a'"
expect_fail 'TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE' "UPDATE public.empire_prime_voice_timer_events SET event_kind='DISPATCH_CLAIMED' WHERE tenant_id='$t' AND timer_digest='$a'"
expect_fail 'TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE' "DELETE FROM public.empire_prime_voice_timer_events WHERE tenant_id='$t' AND timer_digest='$a'"
# A deliberately unprivileged fixture role gets GRANTs *only in this disposable
# database* to test forced RLS; the migration itself supplies no runtime GRANT.
doit "CREATE ROLE timer_fixture_probe NOLOGIN NOSUPERUSER NOBYPASSRLS;"
doit "GRANT USAGE ON SCHEMA public TO timer_fixture_probe;"
doit "GRANT SELECT,INSERT,UPDATE,DELETE ON public.empire_prime_voice_timer_requests,public.empire_prime_voice_timer_events TO timer_fixture_probe;"
assert_eq "$(query "SET ROLE timer_fixture_probe; SELECT count(*) FROM public.empire_prime_voice_timer_requests; RESET ROLE;")" '0' 'FORCE RLS hides existing request from fixture role'
assert_eq "$(query "SET ROLE timer_fixture_probe; SELECT count(*) FROM public.empire_prime_voice_timer_events; RESET ROLE;")" '0' 'FORCE RLS hides existing events from fixture role'
expect_fail 'new row violates row-level security policy' "SET ROLE timer_fixture_probe; INSERT INTO public.empire_prime_voice_timer_requests(tenant_id,timer_digest,actor_digest,source_attestation_digest,consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at) VALUES ('$t2','$a','$b','$c','$e','pilot.v1',2,'2026-10-24 12:00:00+00','2026-10-24 12:00:02+00')"
# Limitations: SQL itself does NOT enforce the event state machine.
# A hypothetical runtime writer must be owner-gated via a separate atomic
# function which validates due time, consent and previous legal transition.
assert_eq "$(query "select count(*) from pg_proc where proname like 'empire_prime_voice_timer_claim%'")" '0' 'no atomic claim RPC silently installed'
assert_eq "$(query "select count(*) from pg_trigger where tgname like 'empire_prime_timer_%_immutable' and not tgisinternal")" '2' 'both append-only triggers installed'
# Deliberately demonstrate the known *semantic* gap, inside a transaction
# that is ALWAYS rolled back: an unrestricted superuser can write a
# structurally valid DELIVERED event without any prior CLAIM or ACCEPTANCE.
# 057 does not provide runtime writer grants; the original DBA/security
# owners must provide an atomic authorised state-transition writer before
# any production activation. This test never contacts a notification provider.
gap_count="$(query "BEGIN;
  INSERT INTO public.empire_prime_voice_timer_events(
    tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,
    source_attestation_digest,provider_receipt_digest)
  VALUES ('$t','$a',2,'$f','PROVIDER_DELIVERED_REPORTED',
          '2026-10-24 12:00:04+00','$c','$e');
  SELECT count(*) FROM public.empire_prime_voice_timer_events
    WHERE seq=2 AND event_kind='PROVIDER_DELIVERED_REPORTED';
  ROLLBACK;")"
assert_eq "$gap_count" '1' 'known gap demonstrated: raw SQL accepts reported delivery without prior claim'
assert_eq "$(query "select count(*) from public.empire_prime_voice_timer_events")" '1' 'semantic-gap transaction rolled back, no bogus event persisted'
echo "EPHEMERAL_POSTGRES_FIXTURE_PASS count=$observations pg_port=$PGPORT production_touched=false events_sent=false provider_transition_writer=NOT_IMPLEMENTED"
