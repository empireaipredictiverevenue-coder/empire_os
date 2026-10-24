"""Original ASTRA/PRIME notification gateway: 2 signed synthetic authorities."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import pytest

from empire_os.prime_flagship_notification_gateway_shadow import (
    OriginalNotificationGatewayShadow,NotificationGatewayHold,
    PROVIDER_SCHEMA,OWNER_SCHEMA,PROVIDER_AUDIENCE,OWNER_AUDIENCE,
    PROVIDER_DOMAIN,OWNER_DOMAIN,PROVIDER,
    _signed_bytes,founder_notification_gateway_shadow,
)

NOW=datetime(2026,10,24,15,0,0,tzinfo=timezone.utc)
TENANT="123e4567-e89b-42d3-a456-426614174000"
ANOTHER="123e4567-e89b-42d3-a456-426614174001"

def dg(phrase):
    return sha256(phrase.encode()).hexdigest()

TIMER=dg("fictional unique original timer")
CLAIM=dg("fictional claimed atomic event")
DEVICE=dg("fictional device binding")
ACTOR=dg("fictional permitted user")
CONSENT=dg("fictional explicit consent evidence")
OWNER_NONCE=dg("fictional signed identity nonce")
RECEIPT_NONCE=dg("fictional provider receipt nonce")
RECEIPT=dg("fictional provider receipt digest")
REFERENCE=dg("fictional provider delivery reference")

# Key material exists only inside test memory, never configured on production.
def material():
    provider=Ed25519PrivateKey.generate()
    owner=Ed25519PrivateKey.generate()
    def pub(k):
        return k.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    return provider,owner,{"fixture_provider_kid":pub(provider)},{"fixture_identity_kid":pub(owner)}


def fixture(*,provider_stage="ACCEPTED",consent_state="ACTIVE_EXPLICIT_TEST_OPT_IN"):
    pk,ok,pp,op=material()
    provider={
        "schema_version":PROVIDER_SCHEMA,"audience":PROVIDER_AUDIENCE,
        "provider_code":PROVIDER,
        "tenant_id":TENANT,"timer_digest":TIMER,
        "claim_event_digest":CLAIM,"delivery_reference_digest":REFERENCE,
        "device_digest":DEVICE,
        "callback_nonce_digest":RECEIPT_NONCE,
        "receipt_digest":RECEIPT,"callback_stage":provider_stage,
        "provider_reported_at":(NOW-timedelta(seconds=10)).isoformat(),
        "synthetic_only":True,
    }
    consent={
        "schema_version":OWNER_SCHEMA,"audience":OWNER_AUDIENCE,
        "tenant_id":TENANT,"timer_digest":TIMER,"claim_event_digest":CLAIM,
        "actor_digest":ACTOR,"device_digest":DEVICE,
        "consent_evidence_digest":CONSENT,"consent_decision":consent_state,
        "issued_at":(NOW-timedelta(minutes=1)).isoformat(),
        "expires_at":(NOW+timedelta(minutes=2)).isoformat(),
        "nonce_digest":OWNER_NONCE,"synthetic_only":True,
    }
    def signed(key,payload,kid,domain):
        signature=base64.urlsafe_b64encode(
            key.sign(_signed_bytes(payload,domain))
        ).rstrip(b"=").decode()
        return {"kid":kid,"payload":payload,"signature":signature}
    pe=signed(pk,provider,"fixture_provider_kid",PROVIDER_DOMAIN)
    oe=signed(ok,consent,"fixture_identity_kid",OWNER_DOMAIN)
    return pk,ok,pp,op,pe,oe,signed


def build(pp,op,*,scope=True,consent=True,claim=True,unseen=True,prior=True):
    def value(x):return lambda *args:x
    return OriginalNotificationGatewayShadow(
        provider_keys=pp,identity_owner_keys=op,
        scope_current=value(scope),consent_current=value(consent),
        claim_current=value(claim),callback_nonce_unseen=value(unseen),
        prior_provider_acceptance=value(prior),
    )


def gate(pe=None,oe=None,**state):
    pk,ok,pp,op,p,o,_=fixture()
    return build(pp,op,**state).review(
        provider_envelope=pe or p,consent_owner_envelope=oe or o,
        tenant_id=TENANT,as_of=NOW,
    )


def test_two_distinct_signed_fictional_authorities_pass_without_real_execution():
    out=gate()
    assert out["status"]=="TWO_SYNTHETIC_SIGNATURES_AND_SCOPE_CHECKS_PASS_LIVE_GATE_HELD"
    assert out["synthetic_provider_signature_valid"] is True
    assert out["synthetic_consent_owner_signature_valid"] is True
    assert out["mock_authority_reader_checks_passed"]==5
    assert out["real_provider_authenticated"] is False
    assert out["real_user_device_authorised"] is False
    assert out["durable_nonce_reserved_by_gateway"] is False
    assert out["original_empiredb_writes"] is False
    assert out["notification_outbound_sent"] is False
    assert out["webhook_listener_active"] is False
    assert out["real_device_delivery_verified"] is False
    assert out["execution_authority"]=="none"
    projected=founder_notification_gateway_shadow(out)
    assert projected["signature_checks_passed_in_fixture"]==2
    assert projected["verified_real_delivery"] is False
    assert TIMER not in str(projected)
    assert DEVICE not in str(projected)
    assert CONSENT not in str(projected)


@pytest.mark.parametrize("stage",["ACCEPTED","DELIVERED","FAILED"])
def test_signed_stages_still_require_real_delivery_owner(stage):
    _,_,pp,op,p,o,_=fixture(provider_stage=stage)
    out=build(pp,op).review(provider_envelope=p,
                            consent_owner_envelope=o,tenant_id=TENANT,as_of=NOW)
    assert out["synthetic_custody_stage"]==stage
    assert out["real_device_delivery_verified"] is False


@pytest.mark.parametrize("override,reason",[
    ({"scope":False},"tenant_device_scope_unverified"),
    ({"consent":False},"consent_current_unverified"),
    ({"claim":False},"atomic_claim_unverified"),
    ({"unseen":False},"nonce_replay_refused"),
    ({"prior":False},"previous_accepted_provider_custody_required"),
])
def test_separate_original_scope_and_custody_checks_gate_review(override,reason):
    pk,ok,pp,op,p,o,_=fixture(provider_stage="DELIVERED")
    with pytest.raises(NotificationGatewayHold,match=reason):
        build(pp,op,**override).review(
            provider_envelope=p,consent_owner_envelope=o,
            tenant_id=TENANT,as_of=NOW)


def test_wrong_pinned_provider_or_owner_key_is_refused():
    pk,ok,pp,op,p,o,_=fixture()
    _,_,pp2,op2,_,_,_=fixture()
    for trusted_p,trusted_o in [(pp2,op),(pp,op2)]:
        with pytest.raises(NotificationGatewayHold,match="original_notification_signature_invalid"):
            build(trusted_p,trusted_o).review(
                provider_envelope=p,consent_owner_envelope=o,
                tenant_id=TENANT,as_of=NOW)


@pytest.mark.parametrize("field,value,reason",[
    ("tenant_id",ANOTHER,"binding_mismatch"),
    ("device_digest",dg("different device"),"binding_mismatch"),
    ("claim_event_digest",dg("different original claim"),"binding_mismatch"),
    ("timer_digest",dg("different timer"),"binding_mismatch"),
    ("audience","different-audience","binding_mismatch"),
    ("provider_code","unknown_provider","binding_mismatch"),
    ("synthetic_only",False,"binding_mismatch"),
    ("callback_stage","SENT_TO_CUSTOMER","supported_signed_notification_stage"),
    ("receipt_digest","bad","distinct_opaque"),
    ("provider_reported_at",(NOW+timedelta(hours=1)).isoformat(),"stale_or_future"),
])
def test_provider_signed_change_cannot_escape_binding_and_time_checks(field,value,reason):
    pk,ok,pp,op,p,o,signed=fixture()
    tampered=dict(p["payload"])
    tampered[field]=value
    p=signed(pk,tampered,p["kid"],PROVIDER_DOMAIN)
    with pytest.raises(NotificationGatewayHold,match=reason):
        build(pp,op).review(provider_envelope=p,consent_owner_envelope=o,
                            tenant_id=TENANT,as_of=NOW)


@pytest.mark.parametrize("field,value,reason",[
    ("tenant_id",ANOTHER,"binding_mismatch"),
    ("device_digest",dg("different device"),"binding_mismatch"),
    ("consent_decision","REVOKED","user_opt_in_not_active"),
    ("audience","not-identity-audience","binding_mismatch"),
    ("synthetic_only",False,"binding_mismatch"),
    ("expires_at",(NOW-timedelta(minutes=1)).isoformat(),"stale_or_future"),
    ("issued_at",(NOW+timedelta(minutes=1)).isoformat(),"stale_or_future"),
    ("actor_digest","invalid","distinct_opaque"),
])
def test_owner_signed_change_cannot_escape_consent_and_identity_checks(field,value,reason):
    pk,ok,pp,op,p,o,signed=fixture()
    changed=dict(o["payload"])
    changed[field]=value
    o=signed(ok,changed,o["kid"],OWNER_DOMAIN)
    with pytest.raises(NotificationGatewayHold,match=reason):
        build(pp,op).review(provider_envelope=p,consent_owner_envelope=o,
                            tenant_id=TENANT,as_of=NOW)


def test_signed_payload_tamper_fails_signature_before_scope_reader():
    _,_,pp,op,p,o,_=fixture()
    p["payload"]["receipt_digest"]=dg("tampered in transit")
    with pytest.raises(NotificationGatewayHold,match="original_notification_signature_invalid"):
        build(pp,op).review(provider_envelope=p,consent_owner_envelope=o,
                            tenant_id=TENANT,as_of=NOW)


def test_callback_cannot_supply_own_pinned_key_or_undocumented_private_fields():
    _,_,pp,op,p,o,_=fixture()
    p["new_provider_public_key"]="attacker-key"
    with pytest.raises(NotificationGatewayHold,match="untrusted_signed_notification_envelope"):
        build(pp,op).review(provider_envelope=p,consent_owner_envelope=o,
                            tenant_id=TENANT,as_of=NOW)
    _,_,pp,op,p,o,_=fixture()
    p["payload"]["phone"]="private"
    with pytest.raises(NotificationGatewayHold,match="untrusted_signed_notification_envelope"):
        build(pp,op).review(provider_envelope=p,consent_owner_envelope=o,
                            tenant_id=TENANT,as_of=NOW)


def test_provider_key_cannot_impersonate_identity_owner_even_with_same_key_id():
    _,_,pp,_,_,_,_=fixture()
    with pytest.raises(NotificationGatewayHold,match="separate_provider_and_identity_owner_key_ids_required"):
        build(pp,pp)


def test_unavailable_consent_reader_fails_closed():
    pk,ok,pp,op,p,o,_=fixture()
    def down(*a):raise RuntimeError("fixture original custody reader down")
    gateway=OriginalNotificationGatewayShadow(
        provider_keys=pp,identity_owner_keys=op,
        scope_current=lambda *a:True,
        consent_current=down,
        claim_current=lambda *a:True,
        callback_nonce_unseen=lambda *a:True,
        prior_provider_acceptance=lambda *a:True,
    )
    with pytest.raises(NotificationGatewayHold,match="authority_reader_unavailable"):
        gateway.review(provider_envelope=p,consent_owner_envelope=o,
                       tenant_id=TENANT,as_of=NOW)


def test_no_original_executor_permission_even_on_complete_fixture_signature_pass(monkeypatch):
    from empire_os import agi_capabilities
    out=gate()
    assert out["notification_outbound_sent"] is False
    assert out["original_empiredb_writes"] is False


@pytest.mark.parametrize("tamper",[
    {"real_provider_authenticated":True},
    {"real_user_device_authorised":True},
    {"real_device_delivery_verified":True},
    {"original_empiredb_writes":True},
    {"durable_nonce_reserved_by_gateway":True},
    {"notification_outbound_sent":True},
    {"execution_authority":"unrestricted"},
    {"mock_authority_reader_checks_passed":True},
    {"synthetic_provider_signature_valid":False},
    {"webhook_listener_active":True},
    {"request_data":"private"},
])
def test_founder_rejects_fake_real_world_or_private_claims(tamper):
    packet=gate()
    packet.update(tamper)
    with pytest.raises(NotificationGatewayHold,match="untrusted_original_notification_gateway_founder_projection"):
        founder_notification_gateway_shadow(packet)


def test_founder_default_does_not_claim_connected_gateway():
    status=founder_notification_gateway_shadow(None)
    assert status["status"]=="NOT_CONNECTED"
    assert status["real_device_delivery_verified"] is False
    assert status["execution_authority"]=="none"


def test_original_founder_cockpit_gateway_remains_read_only_unconnected():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    with TestClient(build_founder_dashboard_service()) as client:
        response=client.get("/v1/founder-dashboard/prime-digital-twin")
        assert response.status_code==200
        packet=response.json()
        assert packet["original_notification_gateway"]["status"]=="NOT_CONNECTED"
        assert packet["original_notification_gateway"]["real_device_delivery_verified"] is False
        assert packet["original_timer_recovery"]["status"]=="NOT_CONNECTED"
        assert packet["provider_receipt_reconciliation"]["status"]=="NOT_CONNECTED"
        assert packet["flagship_release_readiness"]["launch_approved"] is False
        assert client.post("/v1/founder-dashboard/prime-digital-twin").status_code==405


def test_offline_ephemeral_two_signature_demo_emits_no_identifiers_or_live_action():
    from pathlib import Path
    import json
    import subprocess
    import sys
    script=(Path(__file__).resolve().parents[1] /
            "scripts/rehearse_prime_notification_gateway_20261024.py")
    result=subprocess.run([sys.executable,"-B",str(script)],
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    packet=json.loads(result.stdout)
    assert packet["status"]=="TWO_EPHEMERAL_ED25519_SIGNATURES_PASSED_LIVE_GATE_HELD"
    assert packet["provider_synthetic_signature_verified"] is True
    assert packet["owner_synthetic_signature_verified"] is True
    assert packet["mock_authority_checks_passed"]==5
    assert packet["original_empiredb_writes"] is False
    assert packet["real_notifications_sent"] is False
    assert packet["real_provider_connected"] is False
    assert packet["execution_authority"]=="none"
    assert TENANT not in result.stdout
    assert TIMER not in result.stdout
    assert DEVICE not in result.stdout
