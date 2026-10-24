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
# TEST-ONLY fixture login, NEVER part of held migration 060.
# An actual separate SCRAM-authenticated PostgreSQL session will write.
# The password exists only in this disposable shell process and the ephemeral
# PG cluster; it is never echoed, committed or passed to provider services.
export EMPIRE_FIXTURE_LOGIN_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(36))')"
# The temporary secret is sent via SQL stdin, never embedded in psql's
# process command-line arguments or printed to output.
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture <<FIXTURE_SQL
CREATE ROLE timer_fixture_gateway_login LOGIN PASSWORD '$EMPIRE_FIXTURE_LOGIN_PASSWORD'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE empire_timer_fixture TO timer_fixture_gateway_login;
GRANT USAGE ON SCHEMA public TO timer_fixture_gateway_login;
GRANT EXECUTE ON FUNCTION public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz) TO timer_fixture_gateway_login;
FIXTURE_SQL
# This exact SCRAM authentication rule is inserted only into temporary PG18.
# It must appear before pg_virtualenv's broad fixture trust rules.
hba="$(psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c 'SHOW hba_file')"
[[ "$hba" == /tmp/pg_virtualenv.*/postgresql/18/regress/pg_hba.conf ]] || {
  echo REFUSED_NON_EPHEMERAL_SCRAM_HBA_FILE; exit 9;
}
python3 - "$hba" <<'PYPGHBA'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
rule=('host empire_timer_fixture timer_fixture_gateway_login 127.0.0.1/32 scram-sha-256\n'
      'host all timer_fixture_gateway_login 127.0.0.1/32 reject\n'
      'host all timer_fixture_gateway_login ::1/128 reject\n'
      'local all timer_fixture_gateway_login reject\n')
assert rule not in s
p.write_text(rule+s)
PYPGHBA
psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c 'SELECT pg_reload_conf()' | grep -Fxq t
psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 SELECT count(*) FROM pg_hba_file_rules
 WHERE database::text LIKE '%empire_timer_fixture%'
   AND user_name::text LIKE '%timer_fixture_gateway_login%'
   AND address='127.0.0.1' AND auth_method='scram-sha-256'
   AND error IS NULL" | grep -Fxq 1 || { echo SCRAM_FIXTURE_AUTH_RULE_HOLD; exit 6; }
# Confirm passwordless authentication fails for the newly created login,
# then a genuine separate password-based network authentication succeeds.
if env -u PGPASSWORD psql -X -w -h 127.0.0.1 -p "$PGPORT" -U timer_fixture_gateway_login \
   -d empire_timer_fixture -Atq -c 'SELECT 1' >/dev/null 2>&1; then
  echo SCRAM_PASSWORDLESS_LOGIN_WRONGLY_ACCEPTED; exit 6;
fi
PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w -h 127.0.0.1 \
  -p "$PGPORT" -U timer_fixture_gateway_login -d empire_timer_fixture -Atq \
  -v ON_ERROR_STOP=1 -c 'SELECT session_user,current_user' \
  | grep -Fxq 'timer_fixture_gateway_login|timer_fixture_gateway_login' || {
    echo SCRAM_INDEPENDENT_LOGIN_HOLD; exit 6;
  }
# A wrong password must fail on the actual loopback SCRAM connection.
if PGPASSWORD='definitely_invalid_disposable_secret' psql -X -w \
  -h 127.0.0.1 -p "$PGPORT" -U timer_fixture_gateway_login \
  -d empire_timer_fixture -Atq -c 'SELECT 1' >/dev/null 2>&1; then
  echo 'SCRAM_WRONG_PASSWORD_WRONGLY_ACCEPTED'; exit 6
fi
# The live test identity must never inherit migrator, superuser or bypass.
psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,
        (SELECT count(*) FROM pg_auth_members WHERE member=r.oid)
 FROM pg_roles r WHERE rolname='timer_fixture_gateway_login';" \
  | grep -Fxq 't|f|f|f|f|0' || { echo 'SCRAM_FIXTURE_LOGIN_PRIVILEGE_HOLD'; exit 6; }
echo SCRAM_WRONG_PASSWORD_AND_HIGH_PRIVILEGES_DENIED=true
# No password grants this login access to unrelated fixture databases.
if PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w \
  -h 127.0.0.1 -p "$PGPORT" -U timer_fixture_gateway_login \
  -d postgres -Atq -c 'SELECT 1' >/dev/null 2>&1; then
  echo 'SCRAM_CROSS_DATABASE_ACCESS_WRONGLY_ACCEPTED'; exit 6
fi
echo SCRAM_OTHER_DATABASES_REJECTED=true
echo EPHEMERAL_SCRAM_LOGIN_AUTHENTICATED=true
# Prove the fixture role has only the one specific function, no direct table access.
psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 SELECT has_table_privilege('timer_fixture_gateway_login','public.empire_prime_timer_provider_receipts','INSERT'),
        has_table_privilege('timer_fixture_gateway_login','public.empire_prime_timer_provider_receipts','SELECT'),
        has_function_privilege('timer_fixture_gateway_login',
          'public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz)','EXECUTE');" \
  | grep -Fxq 'f|f|t' || { echo RESTRICTED_WRITER_ROLE_PERMISSION_FAILURE; exit 6; }
echo REAL_SCRAM_LOGIN_NO_TABLE_PERMISSIONS=true
export PGDATABASE=empire_timer_fixture
export EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED=ephemeral
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
    scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py
# A fresh, restricted SQL worker must NOT read or directly INSERT into 059.
if PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w -h 127.0.0.1 \
   -p "$PGPORT" -U timer_fixture_gateway_login -v ON_ERROR_STOP=1 \
   -d empire_timer_fixture -c \
   'SELECT count(*) FROM public.empire_prime_timer_provider_receipts' \
   >/tmp/empire_timer_060_denied_$$.log 2>&1; then
  echo 'UNEXPECTED_060_RUNTIME_TABLE_READ'; exit 6
fi
grep -Fq 'permission denied for table empire_prime_timer_provider_receipts'   /tmp/empire_timer_060_denied_$$.log || { cat /tmp/empire_timer_060_denied_$$.log; exit 6; }
rm -f /tmp/empire_timer_060_denied_$$.log
echo 'SCRAM_LOGIN_DIRECT_TABLE_SELECT_DENIED=true'
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
 PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w -h 127.0.0.1 \
   -p "$PGPORT" -U timer_fixture_gateway_login -Atq -v ON_ERROR_STOP=1 \
   -d empire_timer_fixture -c  "BEGIN;
 $(callback "$(hex 717)" "$(hex 718)")
 SELECT pg_sleep(1.4); COMMIT;" >"$tmp/first.log" 2>&1
) &
worker=$!
sleep 0.35
if PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w -h 127.0.0.1 \
  -p "$PGPORT" -U timer_fixture_gateway_login -Atq -v ON_ERROR_STOP=1 \
  -d empire_timer_fixture -c "$(callback "$(hex 719)" "$(hex 720)")" \
  >"$tmp/second.log" 2>&1; then
 echo 'UNEXPECTED_060_DUPLICATE_ACCEPTED_CALLBACK'; wait "$worker"; exit 6
fi
wait "$worker"
grep -Fq 'HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED' "$tmp/first.log"
grep -Fq 'TIMER059_ILLEGAL_OR_REPLAYED_RECEIPT_TRANSITION' "$tmp/second.log"
[[ "$(psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c  "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer'")" == '1' ]] || {
 echo '060_CONCURRENT_RECEIPT_COUNT_MISMATCH'; exit 6;
}
echo 'SCRAM_LOGIN_TWO_WORKERS_ONE_CALLBACK=true'

echo "SIGNED_GATEWAY_060_RESTRICTED_PG_FIXTURE_FINISHED production_touched=false provider_network_calls=0"
