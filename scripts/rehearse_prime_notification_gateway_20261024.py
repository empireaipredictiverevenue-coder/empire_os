#!/usr/bin/env python3
"""Manual isolated original ASTRA/PRIME gateway signature test.

Generates two ephemeral ED25519 keys in-memory; no production custody,
outside provider, contact, database, network, scheduler or notification.
Only sanitized booleans/statuses printed. Synthetic approval NEVER grants
a live action; callback readers here are explicit fictional fixtures.
"""
from __future__ import annotations

import base64
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from empire_os.prime_flagship_notification_gateway_shadow import (
    OriginalNotificationGatewayShadow,PROVIDER_AUDIENCE,OWNER_AUDIENCE,
    PROVIDER_SCHEMA,OWNER_SCHEMA,PROVIDER_DOMAIN,OWNER_DOMAIN,PROVIDER,
    _signed_bytes,founder_notification_gateway_shadow,
)

NOW=datetime(2026,10,24,15,0,0,tzinfo=timezone.utc)
TENANT="123e4567-e89b-42d3-a456-426614174000"
def dg(s: str)->str:
    return sha256(s.encode()).hexdigest()


def signing(key:Ed25519PrivateKey,payload:dict,kid:str,domain:bytes)->dict:
    return {
        "kid":kid,"payload":payload,
        "signature":base64.urlsafe_b64encode(
            key.sign(_signed_bytes(payload,domain))
        ).rstrip(b"=").decode("ascii"),
    }


def public(key:Ed25519PrivateKey)->bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def main()->int:
    provider_private=Ed25519PrivateKey.generate()
    consent_private=Ed25519PrivateKey.generate()
    timer=dg("fictional-original-prime-speech-timer")
    claim=dg("fictional-empiredb-058-claim")
    device=dg("fictional-consenting-test-device")
    p={
        "schema_version":PROVIDER_SCHEMA,"audience":PROVIDER_AUDIENCE,
        "provider_code":PROVIDER,"tenant_id":TENANT,
        "timer_digest":timer,"claim_event_digest":claim,
        "delivery_reference_digest":dg("fictional-delivery-reference"),
        "device_digest":device,"callback_nonce_digest":dg("fictional-receipt-nonce"),
        "receipt_digest":dg("fictional-provider-receipt"),
        "callback_stage":"ACCEPTED",
        "provider_reported_at":(NOW-timedelta(seconds=15)).isoformat(),
        "synthetic_only":True,
    }
    o={
        "schema_version":OWNER_SCHEMA,"audience":OWNER_AUDIENCE,
        "tenant_id":TENANT,"timer_digest":timer,
        "claim_event_digest":claim,"actor_digest":dg("fictional-actor"),
        "device_digest":device,"consent_evidence_digest":dg("fictional-consent"),
        "consent_decision":"ACTIVE_EXPLICIT_TEST_OPT_IN",
        "issued_at":(NOW-timedelta(minutes=1)).isoformat(),
        "expires_at":(NOW+timedelta(minutes=2)).isoformat(),
        "nonce_digest":dg("fictional-owner-signed-nonce"),
        "synthetic_only":True,
    }
    gateway=OriginalNotificationGatewayShadow(
        provider_keys={"synthetic_provider_key":public(provider_private)},
        identity_owner_keys={"synthetic_owner_key":public(consent_private)},
        scope_current=lambda *args:True,
        consent_current=lambda *args:True,
        claim_current=lambda *args:True,
        callback_nonce_unseen=lambda *args:True,
        prior_provider_acceptance=lambda *args:True,
    )
    packet=gateway.review(
        provider_envelope=signing(
            provider_private,p,"synthetic_provider_key",PROVIDER_DOMAIN,
        ),
        consent_owner_envelope=signing(
            consent_private,o,"synthetic_owner_key",OWNER_DOMAIN,
        ),
        tenant_id=TENANT,as_of=NOW,
    )
    founder=founder_notification_gateway_shadow(packet)
    success=(
        founder["status"]=="SYNTHETIC_SIGNED_PREFLIGHT_PASS_REAL_PROVIDER_ON_HOLD"
        and founder["signature_checks_passed_in_fixture"]==2
        and packet["mock_authority_reader_checks_passed"]==5
        and packet["real_provider_authenticated"] is False
        and packet["notification_outbound_sent"] is False
        and packet["original_empiredb_writes"] is False
        and packet["execution_authority"]=="none"
    )
    print(json.dumps({
        "schema_version":"empire.prime.original_notification_gateway_offline_demo.v1",
        "status":"TWO_EPHEMERAL_ED25519_SIGNATURES_PASSED_LIVE_GATE_HELD" if success
                 else "OFFLINE_SIGNATURE_GATE_HOLD",
        "provider_synthetic_signature_verified":packet["synthetic_provider_signature_valid"],
        "owner_synthetic_signature_verified":packet["synthetic_consent_owner_signature_valid"],
        "mock_authority_checks_passed":packet["mock_authority_reader_checks_passed"],
        "original_empiredb_writes":False,
        "real_notifications_sent":False,
        "real_provider_connected":False,
        "consenting_real_user_verified":False,
        "execution_authority":"none",
    },sort_keys=True,indent=2))
    return 0 if success else 1

if __name__=="__main__":
    raise SystemExit(main())
