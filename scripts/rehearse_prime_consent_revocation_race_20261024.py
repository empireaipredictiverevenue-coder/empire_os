#!/usr/bin/env python3
"""Original PRIME/ASTRA consent revocation vs callback custody race fixture.

Use ONLY after pg_virtualenv original 057-060 fixture has installed both
separate SCRAM logins and a locked fictional consent reader. No production
database/provider/customer/device/scheduler. All test identities are fake.

This tests the *ordering* of original synthetic consent revocation against
held 060 callback write, NOT real consent or permission to send alerts.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import time

from scripts.rehearse_prime_signed_gateway_db_receipt_20261024 import (
    TENANT, _safe_connection, _actual_fixture_identity_reader,
    _actual_fixture_login, dg,
)

READER_WAIT = "prime_synthetic_consent_reader_wait"
REVOKER_WAIT = "prime_synthetic_consent_revoker_wait"


def _row(row):
    return [v.decode("ascii") if isinstance(v, bytes) else v for v in row]


def _seed(tag: str):
    timer=dg("concurrent-timer-"+tag)
    source=dg("concurrent-source-"+tag)
    actor=dg("concurrent-actor-"+tag)
    device=dg("concurrent-device-"+tag)
    consent=dg("concurrent-consent-"+tag)
    claim=dg("concurrent-claim-"+tag)
    created=datetime.now(timezone.utc)-timedelta(seconds=20)
    with _safe_connection() as db:
        db.execute("""INSERT INTO public.empire_prime_voice_timer_requests
          (tenant_id,timer_digest,actor_digest,source_attestation_digest,
           consent_evidence_digest,policy_revision,duration_seconds,
           created_at,due_at)
          VALUES (%s,%s,%s,%s,%s,'pilot.v1',3,%s,%s)""",
          (TENANT,timer,actor,source,consent,created,
           created+timedelta(seconds=3)))
        db.execute("""INSERT INTO public.empire_prime_voice_timer_events
          (tenant_id,timer_digest,seq,event_digest,event_kind,
           occurred_at,source_attestation_digest)
          VALUES (%s,%s,1,%s,'TIMER_CREATED',%s,%s)""",
          (TENANT,timer,dg("concurrent-created-"+tag),created,source))
        claimed=db.execute("""SELECT seq FROM
          public.empire_prime_voice_timer_transition_held
          (%s,%s,'DISPATCH_CLAIMED',%s,%s)""",
          (TENANT,timer,claim,source)).fetchone()
        assert claimed[0]==2
        db.execute("""INSERT INTO public.fixture_authorised_device
          (tenant_id,timer_digest,actor_digest,device_digest,
           consent_digest,active) VALUES (%s,%s,%s,%s,%s,true)""",
          (TENANT,timer,actor,device,consent))
    return timer,actor,device,consent,claim,source


def _locked_consent(db,row):
    timer,actor,device,consent,_,_=row
    result=db.execute("""SELECT public.fixture_lock_current_test_consent
        (%s,%s,%s,%s,%s)""",
        (TENANT,timer,actor,device,consent)).fetchone()
    assert result is not None
    return result[0] is True


def _blocked_on(app: str) -> bool:
    # The disposable fixture administrator may inspect test PG locks;
    # independent reader/writer roles are never granted monitoring powers.
    with _safe_connection() as db:
        return db.execute("""SELECT EXISTS(
          SELECT 1 FROM pg_stat_activity
          WHERE application_name=%s AND wait_event_type='Lock'
            AND datname='empire_timer_fixture')""",(app,)).fetchone()[0] is True


def _wait_for_block(app: str):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        if _blocked_on(app):
            return
        time.sleep(0.04)
    raise AssertionError("EXPECTED_TEST_TRANSACTION_LOCK_NOT_OBSERVED_"+app)


def _count_receipts(timer: str) -> int:
    with _safe_connection() as db:
        return db.execute("""SELECT count(*) FROM
          public.empire_prime_timer_provider_receipts
          WHERE tenant_id=%s AND timer_digest=%s""",
          (TENANT,timer)).fetchone()[0]


def _reader_try_after_revocation(row):
    with _actual_fixture_identity_reader() as reader:
        reader.execute("SELECT set_config('application_name',%s,false)",(READER_WAIT,))
        return _locked_consent(reader,row)


def _revoker_waiting_for_reader(row):
    with _safe_connection() as db:
        db.execute("SELECT set_config('application_name',%s,false)",(REVOKER_WAIT,))
        db.execute("""UPDATE public.fixture_authorised_device
            SET active=false
            WHERE tenant_id=%s AND timer_digest=%s""",(TENANT,row[0]))
    return True


def _store_first_callback(row):
    timer,_,_,_,claim,source=row
    with _actual_fixture_login() as writer:
        result=writer.execute("""SELECT held_receipt_seq, held_status FROM
          public.empire_prime_timer_receipt_record_held(
            %s,%s,%s,%s,%s,%s,%s,%s,'ACCEPTED',%s)""",
            (TENANT,timer,"synthetic_local_receipt_fixture",
             dg("one-receipt-nonce-"+timer),
             dg("one-receipt-digest-"+timer),claim,
             dg("one-reference-"+timer),source,
             datetime.now(timezone.utc))).fetchone()
        assert result is not None
        seq,status=_row(result)
        assert seq==1
        assert status=="HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED"


def main():
    # 1. Revocation gets the PostgreSQL UPDATE lock first.
    # Reader's fixed-tenant consent-lock function then blocks; once the
    # committed revoke becomes visible it must return false.
    revoked=_seed("revoke-first")
    with ThreadPoolExecutor(max_workers=2) as pool:
        with _safe_connection() as revoker:
            affected=revoker.execute("""UPDATE public.fixture_authorised_device
              SET active=false WHERE tenant_id=%s AND timer_digest=%s
              RETURNING active""",(TENANT,revoked[0])).fetchone()
            assert affected[0] is False
            waiting=pool.submit(_reader_try_after_revocation,revoked)
            _wait_for_block(READER_WAIT)
        assert waiting.result(timeout=5) is False
    assert _count_receipts(revoked[0])==0

    # 2. Reader gets the consent row lock FIRST, then a separate fixture
    # administrative transaction attempts to revoke. It must wait.
    # A restricted authenticated writer can complete metadata custody
    # BEFORE revocation commits. This is correct lock order, not a claim
    # that a real message was delivered.
    before=_seed("callback-first")
    with ThreadPoolExecutor(max_workers=2) as pool:
        with _actual_fixture_identity_reader() as reader:
            assert _locked_consent(reader,before) is True
            waiting=pool.submit(_revoker_waiting_for_reader,before)
            _wait_for_block(REVOKER_WAIT)
            _store_first_callback(before)
            assert _count_receipts(before[0])==1
        assert waiting.result(timeout=5) is True
    with _actual_fixture_identity_reader() as reader:
        assert _locked_consent(reader,before) is False
    assert _count_receipts(before[0])==1

    result={
      "schema_version":"empire.prime.synthetic_revocation_pg_race.v1",
      "status":"TWO_REAL_POSTGRESQL_REVOCATION_ORDERINGS_PASS",
      "observed_revocation_first_reader_blocked":True,
      "revocation_first_callback_admitted":False,
      "observed_callback_first_revoker_blocked":True,
      "callback_first_receipt_rows_before_revocation":1,
      "revocation_after_callback_preserved_old_receipt":True,
      "original_empiredb_production_writes":False,
      "real_provider_network_calls":0,
      "real_device_alerts":0,
      "synthetic_identity_only":True,
      "execution_authority":"fixture_only",
    }
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
