"""Documenso v2 envelope evidence observer; no HTTP, email or CRM writes.

Documenso webhook uses static X-Documenso-Secret, not an HMAC.
Independent authenticated Documenso read-back and signed PDF verification
are necessary before canonical commercial terms may be registered.
"""
from __future__ import annotations
from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
import json
import re

SCHEMA = "empire.contract_signing.documenso_event_observer.v1"
ENVELOPE = re.compile(r"^envelope_[A-Za-z0-9]{16}$")
ALLOWED = frozenset({"DOCUMENT_CREATED", "DOCUMENT_SENT", "DOCUMENT_OPENED",
                     "DOCUMENT_SIGNED", "DOCUMENT_RECIPIENT_COMPLETED",
                     "DOCUMENT_COMPLETED", "DOCUMENT_REJECTED", "DOCUMENT_CANCELLED",
                     "RECIPIENT_EXPIRED"})
TERMINAL = frozenset({"DOCUMENT_COMPLETED", "DOCUMENT_REJECTED", "DOCUMENT_CANCELLED"})


def timestamp(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def observe_webhook(event: Mapping, *, supplied_secret: str, known_secret: str,
                    expected_envelope_id: str, expected_agreement_binding: str,
                    expected_signer_count: int = 2,
                    prior_terminal_event: str | None = None) -> dict:
    if (not isinstance(known_secret, str) or len(known_secret) < 32
            or not isinstance(supplied_secret, str)
            or not compare_digest(supplied_secret, known_secret)):
        raise ValueError("UNAUTHENTICATED_WEBHOOK")
    if not isinstance(expected_envelope_id, str) or not ENVELOPE.fullmatch(expected_envelope_id):
        raise ValueError("INVALID_EXPECTED_ENVELOPE_ID")
    if not isinstance(expected_agreement_binding, str) or not expected_agreement_binding.strip():
        raise ValueError("INVALID_EXPECTED_AGREEMENT_ID")
    if not isinstance(event, Mapping):
        raise ValueError("BAD_EVENT")
    kind, payload = event.get("event"), event.get("payload")
    if kind not in ALLOWED or not isinstance(payload, Mapping):
        raise ValueError("UNSUPPORTED_EVENT")
    if payload.get("envelopeId") != expected_envelope_id:
        raise ValueError("ENVELOPE_MISMATCH")
    if payload.get("externalId") != expected_agreement_binding:
        raise ValueError("AGREEMENT_BINDING_MISMATCH")
    if not timestamp(event.get("createdAt")):
        raise ValueError("UNTRUSTED_TIMESTAMP")
    if prior_terminal_event is not None:
        if prior_terminal_event not in TERMINAL or kind != prior_terminal_event:
            raise ValueError("CONFLICTING_TERMINAL_EVENT")
    if kind == "DOCUMENT_COMPLETED":
        if payload.get("status") != "COMPLETED" or not timestamp(payload.get("completedAt")):
            raise ValueError("NOT_FULLY_COMPLETED")
        people = payload.get("recipients")
        if not isinstance(people, list):
            raise ValueError("MISSING_RECIPIENT_SIGNATURES")
        signers = [p for p in people if isinstance(p, Mapping) and p.get("role") == "SIGNER"]
        if (isinstance(expected_signer_count, bool) or expected_signer_count < 1
                or len(signers) != expected_signer_count
                or any(p.get("envelopeId") != expected_envelope_id
                       or p.get("signingStatus") != "SIGNED"
                       or not timestamp(p.get("signedAt")) for p in signers)):
            raise ValueError("NOT_ALL_SIGNERS_SIGNED")
        state = "COMPLETED_EVENT_AWAITING_INDEPENDENT_ARTIFACT_PROOF"
    elif kind in {"DOCUMENT_REJECTED", "DOCUMENT_CANCELLED"}:
        state = "SIGNING_STOPPED"
    else:
        state = "SIGNING_IN_PROGRESS"
    event_id = sha256(json.dumps({
        "envelope_id": expected_envelope_id, "agreement_binding": expected_agreement_binding,
        "event": kind, "created_at": event["createdAt"], "status": payload.get("status"),
    }, sort_keys=True).encode()).hexdigest()
    return {
        "schema": SCHEMA, "provider": "documenso", "mode": "OBSERVE",
        "envelope_id": expected_envelope_id, "agreement_binding": expected_agreement_binding,
        "event": kind, "event_fingerprint": event_id,
        "state": state, "requires_independent_documenso_api_readback": True,
        "signed_contract_verified": False, "commercial_terms_accepted": False,
        "revenue_recognized": False, "outbound_authorized": False,
        "execution_authority": "none",
    }


def verify_artifacts(observation: Mapping, proof: Mapping) -> dict:
    """Attestation review only. Does not validate an actual cryptographic PDF."""
    if not isinstance(observation, Mapping) or not isinstance(proof, Mapping):
        raise ValueError("BAD_ARTIFACT_INPUT")
    if observation.get("state") != "COMPLETED_EVENT_AWAITING_INDEPENDENT_ARTIFACT_PROOF":
        raise ValueError("COMPLETED_EVENT_REQUIRED")
    if (proof.get("envelope_id") != observation.get("envelope_id")
            or proof.get("agreement_binding") != observation.get("agreement_binding")):
        raise ValueError("ARTIFACT_BINDING_MISMATCH")
    if (proof.get("authenticated_documenso_api_readback") is not True
            or proof.get("provider_status") != "COMPLETED"
            or proof.get("signed_pdf_integrity_verified") is not True
            or proof.get("audit_trail_integrity_verified") is not True):
        raise ValueError("INDEPENDENT_ARTIFACT_VERIFICATION_MISSING")
    digest = proof.get("signed_pdf_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("INVALID_SIGNED_DOCUMENT_SHA256")
    return {
        "schema": "empire.contract_signing.artifact_review.v1",
        "provider": "documenso", "mode": "OBSERVE",
        "envelope_id": observation["envelope_id"],
        "agreement_binding": observation["agreement_binding"],
        "signed_pdf_sha256": digest, "upstream_artifact_attested": True,
        "canonical_registration_authorized": False,
        "commercial_terms_accepted": False, "revenue_recognized": False,
        "outbound_authorized": False, "execution_authority": "none",
    }
