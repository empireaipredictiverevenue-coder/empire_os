"""PRIME first ORIGINAL inbound buyer enquiry: source-owner proof preflight.

The input MUST be an original Buyer Acquisition signed metadata receipt
validated by the existing pinned issuer / tenant / custody gate, plus
independent original provider/thread/contact/privacy owner readback.

This is not a mail reader, classifier, production adapter, buyer activation,
new CRM, licence grant, issuer, replay store or genuine intent certification.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.commercial_buyer_source_health import SCHEMA as BUYER_HEALTH_SCHEMA
from empire_os.prime_signed_owner_evidence_gateway import (
    PrimeOwnerSignatureVerifier, OwnerSignatureHold,
)
from empire_os.prime_universal_evidence_fusion import APPROVED_PURPOSE, _digest, _hashref, _time

SCHEMA = "empire.prime.original_buyer_intent_preflight.v1"
PROOF_SCHEMA = "empire.buyer_acquisition.original_inbound_source_proof.v1"
PROOF_FIELDS = frozenset({
    "schema_version", "tenant_scope_sha256", "event_sha256", "origin_sha256",
    "entity_sha256", "source_sha256", "provider_received_at",
    "reviewed_at", "original_provider_authenticated", "original_inbound_direction_verified",
    "original_provider_thread_parent_verified", "canonical_contact_and_tenant_binding_verified",
    "privacy_purpose_permitted", "suppression_and_deletion_policy_clear",
    "human_read_original_buyer_enquiry_reviewed",
    "read_only_owner_proof",
})
AUTHENTICITY_FIELDS = (
    "original_provider_authenticated",
    "original_inbound_direction_verified",
    "original_provider_thread_parent_verified",
    "canonical_contact_and_tenant_binding_verified",
    "privacy_purpose_permitted",
    "suppression_and_deletion_policy_clear",
    "human_read_original_buyer_enquiry_reviewed",
    "read_only_owner_proof",
)


class PrimeBuyerIntentHold(ValueError):
    """The authentic buyer enquiry path is blocked, not a commercial signal."""


def _verified_proof(
    row: Mapping[str, Any], proof: Any, *, tenant_id: str, as_of: datetime,
) -> list[str]:
    if type(proof) is not dict or set(proof) != PROOF_FIELDS:
        raise PrimeBuyerIntentHold("exact_private_original_inbound_proof_required")
    if proof["schema_version"] != PROOF_SCHEMA:
        raise PrimeBuyerIntentHold("original_owner_proof_schema_required")
    for field, value in (
        ("tenant_scope_sha256", _digest(tenant_id)),
        ("event_sha256", row["event_sha256"]),
        ("origin_sha256", row["origin_sha256"]),
        ("entity_sha256", row["entity_sha256"]),
        ("source_sha256", row["source_sha256"]),
    ):
        if _hashref(proof[field], field) != value:
            raise PrimeBuyerIntentHold("original_provider_source_identity_conflict")
    received = _time(proof["provider_received_at"], "provider_received_at")
    reviewed = _time(proof["reviewed_at"], "reviewed_at")
    if not (received <= _time(row["received_at"], "received_at")
            and received <= reviewed <= as_of):
        raise PrimeBuyerIntentHold("noncausal_original_provider_proof")
    blocked = []
    for field in AUTHENTICITY_FIELDS:
        if type(proof[field]) is not bool:
            raise PrimeBuyerIntentHold("strict_original_buyer_proof_boolean_required")
        if proof[field] is False:
            blocked.append(field.upper() + "_NOT_PROVEN")
    return blocked


def _buyer_health_status(health: Mapping[str, Any] | None) -> str:
    if health is None:
        return "NOT_CONNECTED_NOT_VERIFIED"
    if (type(health) is not dict
        or health.get("schema_version") != BUYER_HEALTH_SCHEMA
        or health.get("mode") != "OBSERVE"
        or health.get("execution_authority") != "none"
        or health.get("database_writes") is not False
        or health.get("outbound_authorized") is not False
        or health.get("verified_purchase_events_claimed_by_this_report") is not None
        or health.get("realized_revenue_cents_claimed_by_this_report") is not None):
        raise PrimeBuyerIntentHold("unsafe_original_buyer_capacity_review")
    status = health.get("status")
    if status not in (
        "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD",
        "ORIGINAL_BUYER_SOURCE_REVIEW_REQUIRED",
        "ORIGINAL_BUYER_SOURCE_UNAVAILABLE",
    ):
        raise PrimeBuyerIntentHold("unknown_original_buyer_capacity_status")
    return status


class PrimeOriginalBuyerIntentVerifier:
    """This verifier composes original source owners; cannot provision trust.

    The original_owner_lookup MUST be an owner-managed independent read-only
    original inbound provider proof reader. Fixture callbacks are NOT
    authorisation to release, dispatch, train or write real evidence.
    """

    def __init__(
        self, *,
        signed_original_owner_gateway: PrimeOwnerSignatureVerifier,
        original_owner_lookup: Callable[[str, str, str, str, datetime], Mapping[str, Any] | None],
    ) -> None:
        if (type(signed_original_owner_gateway) is not PrimeOwnerSignatureVerifier
            or not callable(original_owner_lookup)):
            raise PrimeBuyerIntentHold("trusted_original_buyer_source_owners_required")
        self._gateway = signed_original_owner_gateway
        self._lookup = original_owner_lookup

    def uses_signed_owner_gateway(self, candidate: PrimeOwnerSignatureVerifier) -> bool:
        """The original signed gate must be the same pinned-key verifier."""
        return candidate is self._gateway

    def review(
        self, *,
        tenant_id: str, as_of: datetime,
        signed_envelope: Mapping[str, Any],
        buyer_source_health: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if type(tenant_id) is not str or not tenant_id.strip():
            raise PrimeBuyerIntentHold("authenticated_original_tenant_required")
        if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
            raise PrimeBuyerIntentHold("trusted_as_of_clock_required")
        if type(signed_envelope) is not dict:
            raise PrimeBuyerIntentHold("exact_original_signed_buyer_envelope_required")
        now = as_of.astimezone(timezone.utc)
        capacity_status = _buyer_health_status(buyer_source_health)
        try:
            signed = self._gateway.review(
                signed_envelopes=[signed_envelope], tenant_id=tenant_id, as_of=now,
            )
        except OwnerSignatureHold:
            raise PrimeBuyerIntentHold("original_signed_buyer_source_not_authenticated") from None
        if (signed.get("signature_and_owner_callback_preflight_count") != 1
            or signed.get("source_admission_authorized") is not False
            or signed.get("replay_ledger_durable_and_atomic") is not False):
            raise PrimeBuyerIntentHold("original_signed_source_gateway_contract_mismatch")
        row = signed_envelope["payload"]["receipt"]
        if (row["owner"] != "buyer_acquisition"
            or row["evidence_class"] != "EXPLICIT_ENQUIRY"
            or row["permitted_purpose"] != APPROVED_PURPOSE
            or row["supports_sha256"] or row["contradicts_sha256"]
            or row["prediction_as_of"] is not None):
            raise PrimeBuyerIntentHold("not_an_original_single_direct_inbound_enquiry")
        try:
            proof = self._lookup(
                tenant_id, row["event_sha256"], row["entity_sha256"],
                row["source_sha256"], now,
            )
        except Exception:
            raise PrimeBuyerIntentHold("original_private_inbound_reader_unavailable") from None
        missing = _verified_proof(row, proof, tenant_id=tenant_id, as_of=now)
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": (
                "SIGNED_OWNER_AND_INBOUND_PROOF_CALLBACK_PREFLIGHT_ONLY_RELEASE_HELD"
                if not missing else "ORIGINAL_INBOUND_BUYER_PROOF_INCOMPLETE_HOLD"
            ),
            "source_owner_signed_gate_shape_reviewed": True,
            "owner_readback_proof_fields_structurally_checked": True,
            "owner_proof_missing_assertions": missing,
            "original_buyer_capacity_owner_review_status": capacity_status,
            "buyer_capacity_is_not_evidence_of_a_direct_inbound_enquiry": True,
            "genuine_original_inbound_event_live_verified_by_this_module": False,
            "independent_canonical_provider_and_contact_authentication_in_production": False,
            "original_provider_rights_live_verified": False,
            "durable_atomic_replay_prevention_verified": False,
            "buyer_intent_independently_verified": False,
            "accepted_commercial_terms_verified": False,
            "verified_paid_order_count": None,
            "recognized_revenue_cents": None,
            "actual_buyer_identity_or_evidence_references_exposed": False,
            "crm_writes": False,
            "empiredb_writes": False,
            "outbound_sent": False,
            "payments_executed": False,
            "trading_executed": False,
            "model_training": False,
            "model_promotion_authorized": False,
            "source_admission_authorized": False,
            "production_release_authorized": False,
            "execution_authority": "none",
            "blockers": [
                "ORIGINAL_AUTHORITATIVE_PROVIDER_INBOUND_AND_CONTACT_READBACK_NOT_CONNECTED",
                "PRODUCTION_OWNER_ISSUER_AND_CUSTODY_NOT_VERIFIED",
                "ORIGINAL_EMPIREDB_ATOMIC_REPLAY_REGISTRY_NOT_DEPLOYED",
                "CANONICAL_BUYER_INTENT_AND_RIGHTS_INDEPENDENT_REVIEW_REQUIRED",
            ] + missing,
        }
