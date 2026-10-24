"""Fake-provider receipt custody and no-resend handling (no network/provider)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from hmac import new as hmac_new
import json

import pytest

from empire_os.prime_flagship_provider_reconciliation_shadow import (
    FIELDS, PROVIDER, ProviderReconciliationHold, _canonical,
    reconcile_synthetic_provider_receipts, founder_provider_receipt_reconciliation,
)
from empire_os.prime_flagship_timer_recovery_shadow import replay_original_timer_shadow

NOW=datetime(2026,10,24,12,0,5,tzinfo=timezone.utc)
TENANT="123e4567-e89b-42d3-a456-426614174000"
TIMER=sha256(b"fictional purpose-scoped timer token").hexdigest()
CLAIM=sha256(b"fictional claimed event token").hexdigest()
REFERENCE=sha256(b"fictional receipt delivery ref").hexdigest()
KEY=sha256(b"fictional injected unit-test HMAC key, never real credential").digest()


def digest(text):
    return sha256(text.encode()).hexdigest()


def replay(*, state="CLAIMED"):
    created={
        "tenant_id":TENANT,"timer_digest":TIMER,"event_digest":digest("create-event"),
        "seq":1,"kind":"TIMER_CREATED","occurred_at":(NOW-timedelta(seconds=5)).isoformat(),
        "due_at":(NOW-timedelta(seconds=3)).isoformat(),
        "duration_seconds":2,"provider_receipt_digest":None,"synthetic_fixture_only":True,
    }
    claim={
        **created,"event_digest":CLAIM,"seq":2,"kind":"DISPATCH_CLAIMED",
        "occurred_at":(NOW-timedelta(seconds=3)).isoformat(),
        "due_at":None,"duration_seconds":None,
    }
    events=[created,claim]
    if state in ("ACCEPTED","DELIVERED","FAILED"):
        events.append({
            **claim, "event_digest":digest("accepted-or-failed"),
            "kind":"PROVIDER_ACCEPTED_REPORTED" if state!="FAILED" else "PROVIDER_FAILED_REPORTED",
            "seq":3, "occurred_at":(NOW-timedelta(seconds=2)).isoformat(),
            "provider_receipt_digest":digest("unverified provider report"),
        })
    if state=="DELIVERED":
        events.append({
            **claim,"event_digest":digest("delivered"),"seq":4,
            "kind":"PROVIDER_DELIVERED_REPORTED",
            "occurred_at":(NOW-timedelta(seconds=1)).isoformat(),
            "provider_receipt_digest":digest("unverified delivered report"),
        })
    return replay_original_timer_shadow(
        tenant_id=TENANT,timer_digest=TIMER,
        original_empiredb_event_rows=events,as_of=NOW,
    )


def synthetic_receipt(i,status,*,when=None):
    data={
        "schema_version":"empire.prime.synthetic_provider_receipt.v1",
        "provider":PROVIDER,"tenant_id":TENANT,"timer_digest":TIMER,
        "claim_event_digest":CLAIM,
        "delivery_reference_digest":REFERENCE,
        "receipt_nonce":digest("fictional_nonce_"+str(i)),
        "status_code":status,
        "occurred_at":(when or (NOW-timedelta(seconds=2-i))).isoformat(),
        "synthetic_only":True,
    }
    data["signature_hex"]=hmac_new(KEY,_canonical({**data,"signature_hex":None}),"sha256").hexdigest()
    return data


def check(rs, snapshot=None, **kwargs):
    return reconcile_synthetic_provider_receipts(
        original_timer_replay=snapshot or replay(),
        receipts=rs,fixture_hmac_key=KEY,
        expected_claim_event_digest=CLAIM,
        expected_delivery_reference_digest=REFERENCE,
        as_of=NOW,**kwargs,
    )


def test_acceptance_not_delivery_not_send_permission():
    receipt=synthetic_receipt(1,"ACCEPTED")
    out=check([receipt])
    assert out["status"]=="SYNTHETIC_PROVIDER_ACCEPTED_NOT_DELIVERED"
    assert out["synthetic_signature_checks_passed"]==1
    assert out["verified_real_provider_delivery"] is False
    assert out["verified_real_user_device_receipt"] is False
    assert out["automatic_retry_permitted"] is False
    assert out["actual_provider_contact_or_transport_used"] is False
    assert out["original_empiredb_writes"] is False
    assert out["execution_authority"]=="none"


def test_matching_two_stage_signed_synthetic_receipts_still_not_real_delivery():
    result=check([synthetic_receipt(1,"ACCEPTED"),synthetic_receipt(2,"DELIVERED")])
    assert result["status"]=="SYNTHETIC_RECEIPT_CHAIN_VALID_NOT_REAL_DELIVERY"
    safe=founder_provider_receipt_reconciliation(result)
    assert safe["synthetic_receipt_count"]==2
    assert safe["verified_real_provider_delivery"] is False
    assert safe["real_user_device_alert_delivered"] is False
    assert TENANT not in str(safe)
    assert TIMER not in str(safe)
    assert REFERENCE not in str(safe)


def test_no_receipts_is_unknown_not_delivery_failure_or_safe_resend():
    out=check([])
    assert out["status"]=="NO_RECEIPT_UNKNOWN_NOT_FAILED"
    assert out["nonexecuting_recovery_decision"]=="STOP_NO_RESEND_RECONCILE_ORIGINAL_PROVIDER"
    assert out["automatic_retry_permitted"] is False


def test_synthetic_failure_is_terminal_no_blind_retry():
    result=check([synthetic_receipt(1,"FAILED")],snapshot=replay(state="FAILED"))
    assert result["status"]=="SYNTHETIC_PROVIDER_FAILURE_TERMINAL_NO_RETRY"
    assert result["outbound_notification_sent"] is False
    assert result["nonexecuting_recovery_decision"]=="STOP_MANUAL_PROVIDER_REVIEW_NO_AUTO_RESEND"


def test_bad_signature_refused():
    r=synthetic_receipt(1,"ACCEPTED")
    r["signature_hex"]="0"*64
    with pytest.raises(ProviderReconciliationHold,match="signature_mismatch"):
        check([r])


@pytest.mark.parametrize("field,value,reason",[
    ("tenant_id","123e4567-e89b-42d3-a456-426614174099","binding_scope"),
    ("timer_digest",digest("another timer"),"binding_scope"),
    ("provider","untrusted_external_sender","binding_scope"),
    ("claim_event_digest",digest("replaced claim"),"binding_scope"),
    ("delivery_reference_digest",digest("wrong reference"),"binding_scope"),
    ("synthetic_only",False,"binding_scope"),
    ("status_code","PERSON_READ_THIS","unknown_fake_provider"),
    ("receipt_nonce","oops", "replayed_or_malformed"),
    ("occurred_at","tomorrow", "exact_utc_receipt_timestamp_required"),
])
def test_mismatched_or_malformed_provider_receipt_fails_before_reconciliation(field,value,reason):
    r=synthetic_receipt(1,"ACCEPTED")
    r[field]=value
    with pytest.raises(ProviderReconciliationHold,match=reason):
        check([r])


def test_duplicate_signed_receipt_nonce_rejected():
    a=synthetic_receipt(1,"ACCEPTED")
    b=deepcopy(a)
    b["status_code"]="DELIVERED"
    b["signature_hex"]=hmac_new(KEY,_canonical(b),"sha256").hexdigest()
    with pytest.raises(ProviderReconciliationHold,match="replayed_or_malformed"):
        check([a,b])


@pytest.mark.parametrize("sequence",[
    ["DELIVERED"],["ACCEPTED","ACCEPTED"],["FAILED","DELIVERED"],
    ["FAILED","ACCEPTED"],["DELIVERED","ACCEPTED"]
])
def test_out_of_order_or_illegal_delivery_transition_fails_closed(sequence):
    with pytest.raises(ProviderReconciliationHold,match="illegal_synthetic_provider_status_transition"):
        check([synthetic_receipt(i+1,s) for i,s in enumerate(sequence)])


def test_earlier_report_after_newer_acceptance_rejected():
    a=synthetic_receipt(1,"ACCEPTED",when=NOW-timedelta(seconds=1))
    b=synthetic_receipt(2,"DELIVERED",when=NOW-timedelta(seconds=3))
    with pytest.raises(ProviderReconciliationHold,match="out_of_order"):
        check([a,b])


def test_stale_fake_receipt_not_current_evidence():
    r=synthetic_receipt(1,"ACCEPTED",when=NOW-timedelta(days=2))
    with pytest.raises(ProviderReconciliationHold,match="outside_bounded"):
        check([r])


def test_real_person_or_extra_fields_not_admitted_to_reconciliation():
    r=synthetic_receipt(1,"ACCEPTED")
    r["contact_email"]="person@example.test"
    with pytest.raises(ProviderReconciliationHold,match="exact_privacy_minimal"):
        check([r])


def test_untrusted_hypothetical_replay_cannot_be_laundered():
    for tamper in [
        {"actual_provider_delivery_verified":True},
        {"original_empiredb_writes":True},
        {"execution_authority":"live"},
        {"source_owner_consent_verified":True},
    ]:
        original=replay()
        original.update(tamper)
        with pytest.raises(ProviderReconciliationHold,match="original_nonexecuting"):
            check([synthetic_receipt(1,"ACCEPTED")],snapshot=original)


def test_real_world_consent_and_owner_claims_cannot_be_forged_for_founder():
    out=check([synthetic_receipt(1,"ACCEPTED")])
    for key in [
        "verified_real_provider_delivery","verified_real_user_device_receipt",
        "current_user_consent_verified","actual_provider_contact_or_transport_used",
        "outbound_notification_sent","automatic_retry_permitted","original_empiredb_writes",
        "real_customer_data_seen"
    ]:
        altered=deepcopy(out)
        altered[key]=True
        with pytest.raises(ProviderReconciliationHold,match="untrusted_original_provider"):
            founder_provider_receipt_reconciliation(altered)
    assert founder_provider_receipt_reconciliation(None)["status"]=="NOT_CONNECTED"


def test_reconciliation_cannot_validate_cancelled_timer_as_delivery():
    original=replay()
    original["status"]="CANCELLED_BEFORE_DISPATCH"
    with pytest.raises(ProviderReconciliationHold,match="original_nonexecuting"):
        check([synthetic_receipt(1,"ACCEPTED")],snapshot=original)


def test_original_founder_api_reports_unconnected_reconciler_no_user_data():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    from empire_os.prime_digital_twin_cockpit import build_prime_digital_twin_cockpit
    safe=build_prime_digital_twin_cockpit()
    assert safe["provider_receipt_reconciliation"]["status"]=="NOT_CONNECTED"
    with TestClient(build_founder_dashboard_service()) as api:
        response=api.get("/v1/founder-dashboard/prime-digital-twin")
        assert response.status_code==200
        data=response.json()
        assert data["provider_receipt_reconciliation"]["status"]=="NOT_CONNECTED"
        assert data["original_timer_recovery"]["status"]=="NOT_CONNECTED"
        assert data["real_messages_sent"] is False
        assert api.post("/v1/founder-dashboard/prime-digital-twin").status_code==405


def test_original_one_shot_provider_reconciliation_demo_has_no_external_side_effects():
    from pathlib import Path
    import subprocess
    import sys
    path=Path(__file__).resolve().parents[1] / "scripts/rehearse_prime_provider_reconciliation_20261024.py"
    result=subprocess.run(
        [sys.executable, "-B",str(path)],
        capture_output=True,text=True,timeout=10,
    )
    assert result.returncode == 0,result.stderr
    packet=json.loads(result.stdout)
    assert packet["status"]=="FOUR_SYNTHETIC_PROVIDER_RECONCILIATIONS_PASS"
    assert len(packet["cases"])==4
    assert packet["provider_network_calls"]==0
    assert packet["notifications_sent"] is False
    assert packet["original_empiredb_writes"] is False
    assert packet["actual_user_device_alert"] is False
    assert packet["source_attestation_real"] is False
    assert packet["execution_authority"]=="none"
