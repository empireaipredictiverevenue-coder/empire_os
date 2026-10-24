#!/usr/bin/env bash
# Disposable original EmpireDB 061 deny-by-default consent write gate.
# Invoked ONLY inside verified pg_virtualenv original 057-060 fixture.
# Consent source and authority replacement here are ENTIRELY FICTIONAL.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?disposable port required}"
: "${PGHOST:?disposable host required}"
: "${EMPIRE_FIXTURE_LOGIN_PASSWORD:?ephemeral SCRAM login required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && ((PGPORT >= 5433)) || exit 9
[[ "$PGDATABASE" == empire_timer_fixture ]] || exit 9
directory="$(psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c 'SHOW data_directory')"
[[ "$directory" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
tmp="$(mktemp -d /tmp/empire_original_061.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
sql(){ psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
admin(){ psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1" >/dev/null; }
writer(){ PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w \
  -h 127.0.0.1 -p "$PGPORT" -U timer_fixture_gateway_login \
  -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
bad(){
  local marker="$1"; shift
  if "$@" >"$tmp/reject.log" 2>&1; then
    echo "061_UNEXPECTED_SUCCESS $marker"; exit 6
  fi
  grep -Fq "$marker" "$tmp/reject.log" || {
    echo "061_WRONG_FAILURE $marker"; tail -16 "$tmp/reject.log"; exit 6;
  }
  echo "061_REJECTED=$marker"
}
# Apply the actual HELD 061 migration only in temporary original test DB.
bad TIMER061_WRONG_DATABASE psql -X -q -v ON_ERROR_STOP=1 -d postgres \
    -f migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture \
    -f migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql
[[ "$(sql "SELECT count(*) FROM pg_trigger WHERE tgname='empire_prime_timer_consent_insert_hold_061' AND NOT tgisinternal")" == 1 ]]
[[ "$(sql "SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.proname IN ('empire_prime_timer_consent_authority_held','empire_prime_timer_consent_insert_guard_held') AND a.grantee=0")" == 0 ]]
bad TIMER061_ALREADY_PRESENT_OWNER_REVIEW_REQUIRED psql -X -q -v ON_ERROR_STOP=1 \
  -d empire_timer_fixture -f migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql
echo "PG061_DEFAULT_DENY_TRIGGER_NO_PUBLIC_GRANTS=PASS"

t='123e4567-e89b-42d3-a456-426614174000'
hex(){ printf '%064d' "$1"; }
actor="$(hex 831)"; consent="$(hex 832)"; dev="$(hex 833)"; source="$(hex 834)"
seed(){
 local timer="$1" first="$2" claim="$3"
 admin "WITH moment AS (SELECT clock_timestamp()-interval '12 seconds' AS created),
 request AS (
 INSERT INTO public.empire_prime_voice_timer_requests(
 tenant_id,timer_digest,actor_digest,source_attestation_digest,
 consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at)
 SELECT '$t','$timer','$actor','$source','$consent','pilot.v1',3,
        created,created+interval '3 seconds' FROM moment
 RETURNING tenant_id,timer_digest,created_at,source_attestation_digest)
 INSERT INTO public.empire_prime_voice_timer_events(
 tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)
 SELECT tenant_id,timer_digest,1,'$first','TIMER_CREATED',created_at,
 source_attestation_digest FROM request;"
 [[ "$(sql "SELECT seq FROM public.empire_prime_voice_timer_transition_held(
 '$t','$timer','DISPATCH_CLAIMED','$claim','$source')")" == 2 ]]
}
call(){
 local timer="$1" claim="$2" ref="$3" nonce="$4" receipt="$5" stage="${6:-ACCEPTED}"
 echo "SELECT held_receipt_seq,held_status FROM public.empire_prime_timer_receipt_record_held(
 '$t','$timer','synthetic_local_receipt_fixture','$nonce','$receipt',
 '$claim','$ref','$source','$stage',clock_timestamp())"
}
timer_a="$(hex 841)"; claim_a="$(hex 842)"; ref_a="$(hex 843)"
seed "$timer_a" "$(hex 844)" "$claim_a"
# The default gate is DENY even for the authenticated limited login.
bad TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer \
  "$(call "$timer_a" "$claim_a" "$ref_a" "$(hex 845)" "$(hex 846)")"
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_a'")" == 0 ]]
bad TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "INSERT INTO public.empire_prime_timer_provider_receipts(
 tenant_id,timer_digest,provider_code,callback_nonce_digest,receipt_digest,
 claim_event_digest,delivery_reference_digest,source_attestation_digest,
 callback_stage,callback_seq,provider_reported_at)
 VALUES ('$t','$timer_a','synthetic_local_receipt_fixture','$(hex 847)',
 '$(hex 848)','$claim_a','$ref_a','$source','ACCEPTED',1,clock_timestamp())"
echo "PG061_DENY_WITHOUT_ORIGINAL_CONSENT_AUTHORITY=PASS"

# FICTITIOUS owner adapter: installed only in temporary test database.
# Never install/copy to canonical EmpireDB or call this real user consent.
# The immutable migration 061 is intentionally not rewritten.
admin "CREATE POLICY fixture_migrator_consent_061 ON public.fixture_authorised_device
 FOR ALL TO empiredb_migrator USING (true) WITH CHECK (true);
 GRANT SELECT,UPDATE ON public.fixture_authorised_device TO empiredb_migrator;"
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture <<'FICTIONAL_OWNER_ADAPTER'
SET ROLE empiredb_migrator;
CREATE OR REPLACE FUNCTION public.empire_prime_timer_consent_authority_held(
 p_tenant uuid,p_timer_digest text,p_source_attestation_digest text
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path='' SET row_security=on
AS $fixture_owner$
DECLARE
 v_actor text; v_consent text;
 v_active boolean;
BEGIN
 -- The true original Identity/Privacy authority is NOT connected.
 -- Fixture-specific original tenant and independent SCRAM writer only.
 IF session_user <> 'timer_fixture_gateway_login'
    OR p_tenant <> '123e4567-e89b-42d3-a456-426614174000'::uuid THEN
   RETURN FALSE;
 END IF;
 SELECT r.actor_digest,r.consent_evidence_digest INTO v_actor,v_consent
 FROM public.empire_prime_voice_timer_requests r
 WHERE r.tenant_id=p_tenant AND r.timer_digest=p_timer_digest
   AND r.source_attestation_digest=p_source_attestation_digest;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 SELECT a.active INTO v_active
 FROM public.fixture_authorised_device a
 WHERE a.tenant_id=p_tenant AND a.timer_digest=p_timer_digest
   AND a.actor_digest=v_actor AND a.consent_digest=v_consent
 FOR SHARE;
 RETURN COALESCE(v_active,FALSE);
END;
$fixture_owner$;
RESET ROLE;
FICTIONAL_OWNER_ADAPTER

# Still DENY if the identity owner has not attested a CURRENT consent row.
bad TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer \
  "$(call "$timer_a" "$claim_a" "$ref_a" "$(hex 849)" "$(hex 850)")"
admin "INSERT INTO public.fixture_authorised_device(
 tenant_id,timer_digest,actor_digest,device_digest,consent_digest,active)
 VALUES ('$t','$timer_a','$actor','$dev','$consent',true)"
[[ "$(writer "$(call "$timer_a" "$claim_a" "$ref_a" "$(hex 851)" "$(hex 852)")")" == 1\|HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED ]]
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_a'")" == 1 ]]
echo "PG061_CONSENT_CHECK_ENFORCED_INSIDE_SQL_WRITER=PASS"

# Even if ASTRA preflight were skipped, withdrawing fictional consent makes
# an ordered follow-up DELIVERED report fail at DB INSERT boundary.
admin "UPDATE public.fixture_authorised_device SET active=false
 WHERE tenant_id='$t' AND timer_digest='$timer_a'"
bad TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer \
  "$(call "$timer_a" "$claim_a" "$ref_a" "$(hex 853)" "$(hex 854)" DELIVERED)"
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_a'")" == 1 ]]
echo "PG061_REVOKED_CONSENT_REFUSES_WRITER_WITHOUT_ASTRA_PREFLIGHT=PASS"

# Actual SQL concurrent revocation: UPDATE obtains row lock first.
# Restricted 060 writer must wait on 061's FOR SHARE then fail after COMMIT.
timer_b="$(hex 861)"; claim_b="$(hex 862)"; ref_b="$(hex 863)"
seed "$timer_b" "$(hex 864)" "$claim_b"
admin "INSERT INTO public.fixture_authorised_device(
 tenant_id,timer_digest,actor_digest,device_digest,consent_digest,active)
 VALUES ('$t','$timer_b','$actor','$dev','$consent',true)"
(
 psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 BEGIN; UPDATE public.fixture_authorised_device SET active=false
 WHERE tenant_id='$t' AND timer_digest='$timer_b';
 SELECT pg_sleep(1.5); COMMIT;" >"$tmp/revoker.log" 2>&1
) &
revoker=$!
sleep .3
bad TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer \
  "$(call "$timer_b" "$claim_b" "$ref_b" "$(hex 865)" "$(hex 866)")"
wait "$revoker"
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_b'")" == 0 ]]
echo "PG061_REVOKE_FIRST_RESTRICTED_WRITER_BLOCKED_AND_REFUSED=PASS"
echo "ORIGINAL_EMPIREDB_061_FIXTURE_PASS production_touched=false provider_calls=0 real_alerts=0 fake_consent=true"
