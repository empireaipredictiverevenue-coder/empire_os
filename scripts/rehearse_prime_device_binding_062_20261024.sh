#!/usr/bin/env bash
# Original PRIME / EmpireDB 062. Disposable synthetic device binding ONLY.
# Invoked strictly AFTER isolated 057-061 fixture under pg_virtualenv -t.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGPORT:?temporary PG port required}"
: "${PGHOST:?temporary PG host required}"
: "${EMPIRE_FIXTURE_LOGIN_PASSWORD:?temporary SCRAM role required}"
[[ "$PGPORT" =~ ^[0-9]+$ ]] && ((PGPORT>=5433)) || exit 9
[[ "${PGDATABASE:-}" == "empire_timer_fixture" ]] || exit 9
[[ "${EMPIRE_REHEARSE_HELD_DEVICE_062:-}" == "disposable_only" ]] || exit 9
[[ "${EMPIRE_REHEARSE_HELD_CONSENT_061:-}" == "disposable_only" ]] || exit 9
dir="$(psql -X -Atq -v ON_ERROR_STOP=1 -c 'show data_directory')"
[[ "$dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
tmp="$(mktemp -d /tmp/empire_062_fixture.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
sql(){ psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
admin(){ psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1" >/dev/null; }
writer(){ PGPASSWORD="$EMPIRE_FIXTURE_LOGIN_PASSWORD" psql -X -w \
 -h 127.0.0.1 -p "$PGPORT" -U timer_fixture_gateway_login \
 -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "$1"; }
reject(){
 local marker="$1"; shift
 if "$@" >"$tmp/error" 2>&1; then echo "062_UNEXPECTED_SUCCESS $marker";exit 6;fi
 grep -Fq "$marker" "$tmp/error" || { echo "062_WRONG_ERROR $marker";tail -15 "$tmp/error";exit 6;}
 echo "062_REJECTED=$marker"
}
reject TIMER062_WRONG_DATABASE psql -X -q -v ON_ERROR_STOP=1 \
 -d postgres -f migrations/empiredb/062_flagship_device_binding_consent_events_held.sql
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture \
 -f migrations/empiredb/062_flagship_device_binding_consent_events_held.sql
reject TIMER062_ALREADY_PRESENT_OWNER_REVIEW_REQUIRED psql -X -q -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -f migrations/empiredb/062_flagship_device_binding_consent_events_held.sql
[[ "$(sql "SELECT count(*) FROM pg_class WHERE relname LIKE 'empire_prime_reminder_%_held' AND relrowsecurity AND relforcerowsecurity")" == 3 ]]
[[ "$(sql "SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.proname IN ('empire_prime_reminder_binding_guard_held','empire_prime_reminder_consent_event_guard_held') AND a.grantee=0")" == 0 ]]
[[ "$(sql "SELECT count(*) FROM pg_policies WHERE tablename IN ('empire_prime_reminder_devices_held','empire_prime_reminder_timer_devices_held','empire_prime_reminder_consent_events_held') AND roles::text LIKE '%empiredb_migrator%'")" == 3 ]]
[[ "$(sql "SELECT has_table_privilege('timer_fixture_gateway_login',
  'public.empire_prime_reminder_devices_held','INSERT'),
  has_table_privilege('timer_fixture_identity_reader_login',
  'public.empire_prime_reminder_consent_events_held','SELECT')")" == 'f|f' ]]
echo "PG062_HELD_SCHEMA_FORCE_RLS_NO_RUNTIME_GRANTS=PASS"

hex(){ printf '%064d' "$1"; }
t='123e4567-e89b-42d3-a456-426614174000'
actor="$(hex 831)"; source="$(hex 834)"; evidence="$(hex 832)"
device_a="$(hex 931)"; device_b="$(hex 932)"
timer_a="$(hex 941)"; claim_a="$(hex 942)"; ref_a="$(hex 943)"
# All records are fictional. A digest never proves who owns this device.
admin "INSERT INTO public.empire_prime_reminder_devices_held(
 tenant_id,actor_digest,device_digest,device_attestation_digest)
 VALUES ('$t','$actor','$device_a','$(hex 933)'),
        ('$t','$actor','$device_b','$(hex 934)')"
admin "WITH moment AS (SELECT clock_timestamp()-interval '12 seconds' AS created),
 req AS (INSERT INTO public.empire_prime_voice_timer_requests(
 tenant_id,timer_digest,actor_digest,source_attestation_digest,
 consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at)
 SELECT '$t','$timer_a','$actor','$source','$evidence','pilot.v1',3,
  created,created+interval '3 seconds' FROM moment
 RETURNING tenant_id,timer_digest,created_at,source_attestation_digest)
 INSERT INTO public.empire_prime_voice_timer_events(
 tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)
 SELECT tenant_id,timer_digest,1,'$(hex 944)','TIMER_CREATED',created_at,
 source_attestation_digest FROM req"
[[ "$(sql "SELECT seq FROM public.empire_prime_voice_timer_transition_held(
 '$t','$timer_a','DISPATCH_CLAIMED','$claim_a','$source')")" == 2 ]]

reject TIMER062_ORIGINAL_TIMER_ACTOR_SOURCE_CONSENT_MISMATCH psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "INSERT INTO public.empire_prime_reminder_timer_devices_held(
 tenant_id,timer_digest,actor_digest,device_digest,source_attestation_digest,
 consent_evidence_digest) VALUES('$t','$timer_a','$actor','$device_a',
 '$(hex 949)','$evidence')"
# A DIFFERENT enrolled actor's legitimate fictional device must not be
# substituted for the timer owner's device even with matching source.
actor_b="$(hex 935)"
admin "INSERT INTO public.empire_prime_reminder_devices_held(
 tenant_id,actor_digest,device_digest,device_attestation_digest)
 VALUES('$t','$actor_b','$device_b','$(hex 936)')"
reject TIMER062_ORIGINAL_TIMER_ACTOR_SOURCE_CONSENT_MISMATCH psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "INSERT INTO public.empire_prime_reminder_timer_devices_held(
 tenant_id,timer_digest,actor_digest,device_digest,source_attestation_digest,
 consent_evidence_digest) VALUES('$t','$timer_a','$actor_b','$device_b',
 '$source','$evidence')"
echo "PG062_DIFFERENT_ENROLLED_ACTOR_CANNOT_BIND_ORIGINAL_TIMER=PASS"
admin "INSERT INTO public.empire_prime_reminder_timer_devices_held(
 tenant_id,timer_digest,actor_digest,device_digest,source_attestation_digest,
 consent_evidence_digest) VALUES('$t','$timer_a','$actor','$device_a',
 '$source','$evidence')"
reject 'duplicate key value violates unique constraint' psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "INSERT INTO public.empire_prime_reminder_timer_devices_held(
 tenant_id,timer_digest,actor_digest,device_digest,source_attestation_digest,
 consent_evidence_digest) VALUES('$t','$timer_a','$actor','$device_b',
 '$source','$evidence')"
echo "PG062_TIMER_TO_ONE_MATCHING_ACTOR_DEVICE=PASS"

event_insert(){
 local target_dev="$1" seq="$2" digest="$3" decision="$4"
 echo "INSERT INTO public.empire_prime_reminder_consent_events_held(
 tenant_id,actor_digest,device_digest,event_seq,event_digest,
 consent_evidence_digest,identity_source_digest,purpose,channel,decision,occurred_at)
 VALUES ('$t','$actor','$target_dev',$seq,'$digest',
 '$evidence','$(hex 951)','TIMER_NOTIFICATION','PRIVATE_DEVICE',
 '$decision',clock_timestamp())"
}
reject TIMER062_FIRST_EVENT_MUST_GRANT psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "$(event_insert "$device_a" 1 "$(hex 952)" REVOKED)"
admin "$(event_insert "$device_a" 1 "$(hex 953)" GRANTED)"
reject TIMER062_CONSENT_EVENT_ORDER_OR_DUPLICATE psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "$(event_insert "$device_a" 2 "$(hex 954)" GRANTED)"
reject TIMER062_CONSENT_EVENT_ORDER_OR_DUPLICATE psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "$(event_insert "$device_a" 3 "$(hex 955)" REVOKED)"
reject TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE psql -X -Atq -v ON_ERROR_STOP=1 \
 -d empire_timer_fixture -c "UPDATE public.empire_prime_reminder_consent_events_held SET decision='REVOKED' WHERE device_digest='$device_a'"
# Crucial: creating those tables does not loosen the unchanged 061 DENY.
call(){
 local nonce="$1" receipt="$2" stage="${3:-ACCEPTED}"
 echo "SELECT held_receipt_seq,held_status FROM public.empire_prime_timer_receipt_record_held(
 '$t','$timer_a','synthetic_local_receipt_fixture','$nonce','$receipt',
 '$claim_a','$ref_a','$source','$stage',clock_timestamp())"
}
reject TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer \
 "$(call "$(hex 956)" "$(hex 957)")"
echo "PG062_NO_AUTO_PROMOTION_OF_UNVERIFIED_DEVICE_CONSENT=PASS"

# Fixture-only owner rewire: this is NOT original Identity signed authority.
# Retains 061's actual DB insert trigger but queries 062 proposed metadata
# with an explicit enrolment lock and latest append-only consent event.
psql -X -q -v ON_ERROR_STOP=1 -d empire_timer_fixture <<'TEST_ADAPTER'
SET ROLE empiredb_migrator;
CREATE OR REPLACE FUNCTION public.empire_prime_timer_consent_authority_held(
 p_tenant uuid,p_timer_digest text,p_source_attestation_digest text
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path='' SET row_security=on
AS $fake_identity_062$
DECLARE v_actor text; v_device text; v_evidence text;
 v_latest text; v_latest_evidence text;
BEGIN
 IF session_user<>'timer_fixture_gateway_login'
   OR p_tenant<>'123e4567-e89b-42d3-a456-426614174000'::uuid
 THEN RETURN FALSE; END IF;
 SELECT actor_digest,device_digest,consent_evidence_digest
 INTO v_actor,v_device,v_evidence
 FROM public.empire_prime_reminder_timer_devices_held
 WHERE tenant_id=p_tenant AND timer_digest=p_timer_digest
   AND source_attestation_digest=p_source_attestation_digest;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 -- Lock the SAME enrolment row taken FOR UPDATE by 062 consent writer:
 -- revocation-first cannot be followed by a stale callback.
 PERFORM 1 FROM public.empire_prime_reminder_devices_held
 WHERE tenant_id=p_tenant AND actor_digest=v_actor
   AND device_digest=v_device FOR SHARE;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 SELECT decision,consent_evidence_digest
 INTO v_latest,v_latest_evidence
 FROM public.empire_prime_reminder_consent_events_held
 WHERE tenant_id=p_tenant AND actor_digest=v_actor
   AND device_digest=v_device AND purpose='TIMER_NOTIFICATION'
   AND channel='PRIVATE_DEVICE'
 ORDER BY event_seq DESC LIMIT 1;
 RETURN COALESCE(v_latest='GRANTED'
   AND v_latest_evidence=v_evidence,FALSE);
END;
$fake_identity_062$;
RESET ROLE;
TEST_ADAPTER
[[ "$(writer "$(call "$(hex 958)" "$(hex 959)")")" == '1|HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED' ]]
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_a'")" == 1 ]]
echo "PG062_FIXTURE_ONLY_DEVICE_GRANT_ALLOW_VERIFIED_BY_DB=PASS"

# A second device's consent cannot authorise this timer.
admin "$(event_insert "$device_b" 1 "$(hex 960)" GRANTED)"
admin "$(event_insert "$device_a" 2 "$(hex 961)" REVOKED)"
reject TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer \
 "$(call "$(hex 962)" "$(hex 963)" DELIVERED)"
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_a'")" == 1 ]]
echo "PG062_REVOCATION_TIED_TO_BOUND_DEVICE_NOT_OTHER_DEVICE=PASS"
# Regrant with fresh owner event is allowed as a separate explicit event,
# never a silent reset or in-place UPDATE.
admin "$(event_insert "$device_a" 3 "$(hex 964)" GRANTED)"
[[ "$(writer "$(call "$(hex 965)" "$(hex 966)" DELIVERED)")" == '2|HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED' ]]
echo "PG062_EXPLICIT_NEW_GRANT_RESTORES_ONLY_FIXTURE_CUSTODY=PASS"
# 062's own append-only REVOKED event acquires the enrolled-device
# UPDATE lock first; the original 061 callback trigger must wait then deny.
# The proof uses two separate real PostgreSQL connections.
timer_b="$(hex 971)"; claim_b="$(hex 972)"; ref_b="$(hex 973)"
admin "WITH moment AS (SELECT clock_timestamp()-interval '12 seconds' AS created),
 req AS (INSERT INTO public.empire_prime_voice_timer_requests(
 tenant_id,timer_digest,actor_digest,source_attestation_digest,
 consent_evidence_digest,policy_revision,duration_seconds,created_at,due_at)
 SELECT '$t','$timer_b','$actor','$source','$evidence','pilot.v1',3,
 created,created+interval '3 seconds' FROM moment
 RETURNING tenant_id,timer_digest,created_at,source_attestation_digest)
 INSERT INTO public.empire_prime_voice_timer_events(
 tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,source_attestation_digest)
 SELECT tenant_id,timer_digest,1,'$(hex 974)','TIMER_CREATED',created_at,
 source_attestation_digest FROM req"
[[ "$(sql "SELECT seq FROM public.empire_prime_voice_timer_transition_held(
 '$t','$timer_b','DISPATCH_CLAIMED','$claim_b','$source')")" == 2 ]]
admin "INSERT INTO public.empire_prime_reminder_timer_devices_held(
 tenant_id,timer_digest,actor_digest,device_digest,source_attestation_digest,
 consent_evidence_digest) VALUES('$t','$timer_b','$actor','$device_a',
 '$source','$evidence')"
(
 psql -X -Atq -v ON_ERROR_STOP=1 -d empire_timer_fixture -c "
 BEGIN; $(event_insert "$device_a" 4 "$(hex 975)" REVOKED);
 SELECT pg_sleep(1.4); COMMIT;" >"$tmp/062_revoker.log" 2>&1
) &
revoker=$!
sleep .35
reject TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED writer  "SELECT held_receipt_seq,held_status FROM public.empire_prime_timer_receipt_record_held(
 '$t','$timer_b','synthetic_local_receipt_fixture','$(hex 976)',
 '$(hex 977)','$claim_b','$ref_b','$source','ACCEPTED',clock_timestamp())"
wait "$revoker"
[[ "$(sql "SELECT count(*) FROM public.empire_prime_timer_provider_receipts WHERE timer_digest='$timer_b'")" == 0 ]]
echo "PG062_REVOKE_EVENT_FIRST_PREVENTS_LATE_WRITER=PASS"
echo "ORIGINAL_PG062_DEVICE_BINDING_FIXTURE_PASS production_touched=false real_consent=false real_device_alerts=0"
