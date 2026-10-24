"""Original EmpireOS ASTRA/PRIME notification ingress: signed synthetic preflight.

Reuse the original Ed25519 signed-owner domain-separated verification model
and original AGI capability gate; no untrusted callback gains execution.
No network, HTTP listener, provider connection, database, sender, device,
model inference, credentials on disk or production approval. The injected
key registry and authority readers are TEST dependencies, not attestations
that any production provider/consent/owner has been integrated.
"""
from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.agi_capabilities import review_capability_request

SCHEMA = "empire.prime.notification_gateway_synthetic_preflight.v1"
PROVIDER_SCHEMA = "empire.prime.notification_provider_signed_callback.v1"
OWNER_SCHEMA = "empire.prime.notification_consent_signed_owner.v1"
PROVIDER_AUDIENCE = "empire-original-notification-provider-test"
OWNER_AUDIENCE = "empire-original-notification-identity-test"
PROVIDER_DOMAIN = b"empire-prime-notification-provider-synthetic-ed25519-v1:"
OWNER_DOMAIN = b"empire-prime-notification-consent-synthetic-ed25519-v1:"
HEX = re.compile(r"^[a-f0-9]{64}$")
UUID = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
KID = re.compile(r"^[a-z][a-z0-9_-]{2,47}$")
PROVIDER = "synthetic_local_receipt_fixture"
PROVIDER_FIELDS = frozenset({
    "schema_version", "audience", "provider_code", "tenant_id",
    "timer_digest", "claim_event_digest", "delivery_reference_digest",
    "device_digest", "callback_nonce_digest", "receipt_digest",
    "callback_stage", "provider_reported_at", "synthetic_only",
})
OWNER_FIELDS = frozenset({
    "schema_version", "audience", "tenant_id", "timer_digest",
    "claim_event_digest", "actor_digest", "device_digest",
    "consent_evidence_digest", "consent_decision", "issued_at",
    "expires_at", "nonce_digest", "synthetic_only",
})
ENVELOPE_FIELDS = frozenset({"kid", "payload", "signature"})


class NotificationGatewayHold(ValueError):
    pass


def _utc(raw: Any) -> datetime:
    if type(raw) is not str or not 20 <= len(raw) <= 40:
        raise NotificationGatewayHold("bounded_UTC_original_notification_timestamp_required")
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise NotificationGatewayHold("invalid_original_notification_timestamp") from None
    if t.utcoffset() != timedelta(0):
        raise NotificationGatewayHold("original_notification_UTC_required")
    return t.astimezone(timezone.utc)


def _signed_bytes(payload: Mapping[str, Any], domain: bytes) -> bytes:
    return domain + json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def _signature(encoded: Any) -> bytes:
    if type(encoded) is not str or re.fullmatch(r"[A-Za-z0-9_-]{86}",encoded) is None:
        raise NotificationGatewayHold("canonical_original_notification_Ed25519_signature_required")
    try:
        raw = base64.b64decode(encoded+"==", altchars=b"-_", validate=True)
    except (ValueError,binascii.Error):
        raise NotificationGatewayHold("canonical_original_notification_Ed25519_signature_required") from None
    if (len(raw)!=64
        or base64.urlsafe_b64encode(raw).rstrip(b"=").decode()!=encoded):
        raise NotificationGatewayHold("canonical_original_notification_Ed25519_signature_required")
    return raw


class OriginalNotificationGatewayShadow:
    """Preflight only; all authority callbacks come from injected test doubles.

    No method writes receipts or sends messages. Trust registry is injected
    and cannot be constructed from the untrusted callback's claimed issuer.
    """

    def __init__(
        self, *, provider_keys: Mapping[str, bytes],
        identity_owner_keys: Mapping[str, bytes],
        scope_current: Callable[[str,str,str,datetime],bool],
        consent_current: Callable[[str,str,str,str,datetime],bool],
        claim_current: Callable[[str,str,str,datetime],bool],
        callback_nonce_unseen: Callable[[str,str,datetime],bool],
        prior_provider_acceptance: Callable[[str,str,str,datetime],bool],
    ) -> None:
        if any(not callable(x) for x in (
            scope_current,consent_current,claim_current,
            callback_nonce_unseen,prior_provider_acceptance
        )):
            raise NotificationGatewayHold("separate_original_authority_reader_contracts_required")
        self._provider_keys=self._validate_keys(provider_keys)
        self._owner_keys=self._validate_keys(identity_owner_keys)
        if set(self._provider_keys)&set(self._owner_keys):
            raise NotificationGatewayHold("separate_provider_and_identity_owner_key_ids_required")
        self._scope=scope_current
        self._consent=consent_current
        self._claim=claim_current
        self._nonce=callback_nonce_unseen
        self._prior=prior_provider_acceptance

    @staticmethod
    def _validate_keys(keys: Mapping[str,bytes]) -> dict[str,Ed25519PublicKey]:
        if not isinstance(keys,Mapping) or not 1<=len(keys)<=4:
            raise NotificationGatewayHold("original_pinned_nonempty_notification_key_registry_required")
        found={}
        for kid,key in keys.items():
            if (type(kid) is not str or KID.fullmatch(kid) is None
                or type(key) is not bytes or len(key)!=32):
                raise NotificationGatewayHold("invalid_original_pinned_notification_key")
            try:
                found[kid]=Ed25519PublicKey.from_public_bytes(key)
            except ValueError:
                raise NotificationGatewayHold("invalid_original_pinned_notification_key") from None
        return found

    @staticmethod
    def _verify(
        envelope: Mapping[str,Any], keys: Mapping[str,Ed25519PublicKey],
        *, required: frozenset[str], domain: bytes,
    ) -> dict[str,Any]:
        if (type(envelope) is not dict or set(envelope)!=ENVELOPE_FIELDS
            or type(envelope.get("kid")) is not str
            or envelope["kid"] not in keys
            or type(envelope.get("payload")) is not dict
            or set(envelope["payload"])!=required):
            raise NotificationGatewayHold("untrusted_signed_notification_envelope")
        body=envelope["payload"]
        try:
            keys[envelope["kid"]].verify(
                _signature(envelope["signature"]),_signed_bytes(body,domain),
            )
        except (InvalidSignature,ValueError,TypeError,OverflowError):
            raise NotificationGatewayHold("original_notification_signature_invalid") from None
        return body

    @staticmethod
    def _digest(value: Any) -> bool:
        return type(value) is str and HEX.fullmatch(value) is not None

    def review(
        self, *, provider_envelope: Mapping[str,Any],
        consent_owner_envelope: Mapping[str,Any],
        tenant_id: str, as_of: datetime,
    ) -> dict[str,Any]:
        if (type(tenant_id) is not str or UUID.fullmatch(tenant_id) is None
            or not isinstance(as_of,datetime) or as_of.utcoffset() is None):
            raise NotificationGatewayHold("trusted_original_tenant_and_review_clock_required")
        now=as_of.astimezone(timezone.utc)
        # Do NOT process provider data until both independent signatures pass.
        p=self._verify(provider_envelope,self._provider_keys,
                       required=PROVIDER_FIELDS,domain=PROVIDER_DOMAIN)
        o=self._verify(consent_owner_envelope,self._owner_keys,
                       required=OWNER_FIELDS,domain=OWNER_DOMAIN)
        if (p["schema_version"]!=PROVIDER_SCHEMA or p["audience"]!=PROVIDER_AUDIENCE
            or o["schema_version"]!=OWNER_SCHEMA or o["audience"]!=OWNER_AUDIENCE
            or p["provider_code"]!=PROVIDER
            or p["synthetic_only"] is not True
            or o["synthetic_only"] is not True
            or p["tenant_id"]!=tenant_id or o["tenant_id"]!=tenant_id
            or p["timer_digest"]!=o["timer_digest"]
            or p["claim_event_digest"]!=o["claim_event_digest"]
            or p["device_digest"]!=o["device_digest"]):
            raise NotificationGatewayHold("signed_original_provider_consent_binding_mismatch")
        values=[
            p["timer_digest"],p["claim_event_digest"],
            p["delivery_reference_digest"],p["device_digest"],
            p["callback_nonce_digest"],p["receipt_digest"],
            o["actor_digest"],o["consent_evidence_digest"],o["nonce_digest"],
        ]
        if any(not self._digest(x) for x in values) or len(set(values))!=len(values):
            raise NotificationGatewayHold("distinct_opaque_original_notification_digests_required")
        if p["callback_stage"] not in ("ACCEPTED","DELIVERED","FAILED"):
            raise NotificationGatewayHold("supported_signed_notification_stage_required")
        issued=_utc(o["issued_at"])
        expires=_utc(o["expires_at"])
        occurred=_utc(p["provider_reported_at"])
        if (issued>now or expires<=now or expires<=issued
            or expires-issued>timedelta(minutes=5)
            or occurred>now+timedelta(minutes=1)
            or occurred<now-timedelta(minutes=5)):
            raise NotificationGatewayHold("stale_or_future_notification_authority_or_callback")
        if (o["consent_decision"]!="ACTIVE_EXPLICIT_TEST_OPT_IN"):
            raise NotificationGatewayHold("user_opt_in_not_active_or_revoked")
        # These are original-owner interface CONTRACTS, not production trust
        # claims. Real owners must provide authenticated readers, key custody,
        # revocation checking and a durable EmpireDB nonce reservation.
        try:
            scoped=self._scope(tenant_id,p["timer_digest"],p["device_digest"],now) is True
            consented=self._consent(
                tenant_id,o["actor_digest"],p["device_digest"],
                o["consent_evidence_digest"],now,
            ) is True
            claimed=self._claim(tenant_id,p["timer_digest"],p["claim_event_digest"],now) is True
            unused=self._nonce(p["provider_code"],p["callback_nonce_digest"],now) is True
            previous=(self._prior(
                tenant_id,p["timer_digest"],p["delivery_reference_digest"],now,
            ) is True) if p["callback_stage"]=="DELIVERED" else True
        except Exception:
            raise NotificationGatewayHold("original_notification_authority_reader_unavailable") from None
        if not scoped:
            raise NotificationGatewayHold("original_notification_tenant_device_scope_unverified")
        if not consented:
            raise NotificationGatewayHold("original_notification_consent_current_unverified")
        if not claimed:
            raise NotificationGatewayHold("original_notification_atomic_claim_unverified")
        if not unused:
            raise NotificationGatewayHold("original_callback_nonce_replay_refused")
        if not previous:
            raise NotificationGatewayHold("previous_accepted_provider_custody_required")
        # Existing capability registry has NO live notification executor.
        agi=review_capability_request({
            "agent_id":"original_astra_notification_shadow",
            "capability":"__original_notification_send_unregistered__",
            "authority_mode":"OBSERVE",
            "approval_present":False,"granted_capabilities":[],
        })
        if agi["permitted"] is True:
            raise NotificationGatewayHold("original_notification_execution_must_remain_closed")
        return {
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"TWO_SYNTHETIC_SIGNATURES_AND_SCOPE_CHECKS_PASS_LIVE_GATE_HELD",
            "synthetic_provider_signature_valid":True,
            "synthetic_consent_owner_signature_valid":True,
            "mock_authority_reader_checks_passed":5,
            "synthetic_custody_stage":p["callback_stage"],
            "real_provider_authenticated":False,
            "real_user_device_authorised":False,
            "original_canonical_empiredb_readback_verified":False,
            "durable_nonce_reserved_by_gateway":False,
            "original_empiredb_writes":False,
            "notification_outbound_sent":False,
            "real_device_delivery_verified":False,
            "webhook_listener_active":False,
            "execution_authority":"none",
        }


def founder_notification_gateway_shadow(value: Mapping[str,Any]|None) -> dict[str,Any]:
    if value is None:
        return {
            "schema_version":"empire.prime.founder_notification_gateway.v1",
            "mode":"OBSERVE","status":"NOT_CONNECTED",
            "real_device_delivery_verified":False,
            "execution_authority":"none",
        }
    expected={
        "schema_version","mode","status","synthetic_provider_signature_valid",
        "synthetic_consent_owner_signature_valid","mock_authority_reader_checks_passed",
        "synthetic_custody_stage","real_provider_authenticated",
        "real_user_device_authorised","original_canonical_empiredb_readback_verified",
        "durable_nonce_reserved_by_gateway","original_empiredb_writes",
        "notification_outbound_sent","real_device_delivery_verified",
        "webhook_listener_active","execution_authority",
    }
    if (type(value) is not dict or set(value)!=expected
        or value["schema_version"]!=SCHEMA or value["mode"]!="OBSERVE"
        or value["status"]!="TWO_SYNTHETIC_SIGNATURES_AND_SCOPE_CHECKS_PASS_LIVE_GATE_HELD"
        or value["synthetic_provider_signature_valid"] is not True
        or value["synthetic_consent_owner_signature_valid"] is not True
        or type(value["mock_authority_reader_checks_passed"]) is not int
        or value["mock_authority_reader_checks_passed"]!=5
        or value["synthetic_custody_stage"] not in ("ACCEPTED","DELIVERED","FAILED")
        or any(value[x] is not False for x in (
            "real_provider_authenticated","real_user_device_authorised",
            "original_canonical_empiredb_readback_verified",
            "durable_nonce_reserved_by_gateway","original_empiredb_writes",
            "notification_outbound_sent","real_device_delivery_verified",
            "webhook_listener_active",
        ))
        or value["execution_authority"]!="none"):
        raise NotificationGatewayHold("untrusted_original_notification_gateway_founder_projection")
    return {
        "schema_version":"empire.prime.founder_notification_gateway.v1",
        "mode":"OBSERVE",
        "status":"SYNTHETIC_SIGNED_PREFLIGHT_PASS_REAL_PROVIDER_ON_HOLD",
        "signature_checks_passed_in_fixture":2,
        "verified_real_delivery":False,
        "real_device_delivery_verified":False,
        "execution_authority":"none",
    }
