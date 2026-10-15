"""Cryptographic *reviewer* evidence for Empire GTM, not buyer verification.

Follows the first-party CRM Ed25519 verifier design. Trusted reviewer key
bindings and tenant membership MUST be provisioned by a separate authorised
first-party service. Caller-provided attestations are never trusted keys or
membership. This read-only module does not bootstrap reviewers, write a replay
ledger, authenticate a public post, grant contact authority or train models.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Callable, Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ID = re.compile(r"^[A-Za-z0-9_:-]{3,96}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
CHOICES = frozenset((
    "PUBLIC_ASSOCIATION_RESEARCH_ONLY",
    "UNRESOLVED_AUTHOR_COMPANY_LINK",
    "PARTNERSHIP_NOT_A_BUYER_PROOF",
    "EXTERNAL_EVIDENCE_INSUFFICIENT",
    "REJECT_SOURCE_EVIDENCE",
))
PAYLOAD = frozenset((
    "schema_version", "audience", "tenant_id", "reviewer_id",
    "source_url_sha256", "source_content_version_sha256",
    "cohort_evidence_sha256", "decision", "issued_at",
    "expires_at", "nonce",
))
DOMAIN = b"empire-gtm-review-ed25519-v1:"
REVIEW_SCOPE = "gtm:independent-research-review"


def _clock(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid_review_clock")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_review_clock") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("aware_review_clock_required")
    return dt.astimezone(timezone.utc)


def _signature(encoded: Any) -> bytes:
    if (not isinstance(encoded, str) or len(encoded) != 86
            or re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None):
        raise ValueError("invalid_review_signature_encoding")
    try:
        raw = base64.b64decode(
            encoded + "==", altchars=b"-_", validate=True,
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("invalid_review_signature_encoding") from exc
    if (len(raw) != 64 or
            base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != encoded):
        raise ValueError("noncanonical_review_signature")
    return raw


def _payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return DOMAIN + json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


class GtmReviewerAttestationVerifier:
    """Read-only verifier; PINNED keys and scope loader are trusted inputs.

    The caller may not use public post content or agent-generated reviewer
    roles as a substitute for a separate authoritative membership lookup.
    Signature validation is not platform/content authentication.
    """

    def __init__(
        self, trusted_reviewer_keys: Mapping[str, tuple[str, bytes]],
        *, active_reviewer_scope: Callable[[str, str, str], bool],
    ) -> None:
        if not callable(active_reviewer_scope) or not trusted_reviewer_keys:
            raise ValueError("trusted_reviewer_authority_required")
        pinned: dict[str, tuple[str, Ed25519PublicKey]] = {}
        for kid, pair in trusted_reviewer_keys.items():
            if (not isinstance(kid, str) or not ID.fullmatch(kid)
                    or not isinstance(pair, tuple) or len(pair) != 2):
                raise ValueError("invalid_pinned_reviewer_binding")
            reviewer, public = pair
            if (not isinstance(reviewer, str) or not ID.fullmatch(reviewer)
                    or not isinstance(public, bytes) or len(public) != 32):
                raise ValueError("invalid_pinned_reviewer_binding")
            pinned[kid] = (reviewer, Ed25519PublicKey.from_public_bytes(public))
        self._pinned = pinned
        self._scope = active_reviewer_scope

    def verify(
        self, envelope: Mapping[str, Any], *,
        source: Mapping[str, Any], cohort_sha256: str,
        tenant_id: str, now: datetime,
    ) -> dict[str, Any]:
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("trusted_current_time_required")
        if (not isinstance(envelope, Mapping)
                or set(envelope) != {"kid", "payload", "signature"}
                or envelope.get("kid") not in self._pinned
                or not isinstance(envelope.get("payload"), Mapping)):
            raise ValueError("unknown_or_malformed_review_signer")
        body = envelope["payload"]
        if set(body) != PAYLOAD:
            raise ValueError("unexpected_signed_review_fields")
        if (body["schema_version"] != "empire.gtm_signed_research_review.v1"
                or body["audience"] != "empire-gtm-independent-review"
                or body["decision"] not in CHOICES):
            raise ValueError("unsupported_reviewer_decision_or_scope")
        reviewer, public = self._pinned[envelope["kid"]]
        if body["reviewer_id"] != reviewer:
            raise ValueError("signed_reviewer_identity_mismatch")
        try:
            canonical_tenant = str(UUID(tenant_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("canonical_tenant_id_required") from exc
        if (canonical_tenant != tenant_id
                or body["tenant_id"] != tenant_id
                or not isinstance(source, Mapping)
                or body["source_url_sha256"] != source.get("source_url_sha256")
                or body["source_content_version_sha256"] !=
                    source.get("source_content_version_sha256")
                or body["cohort_evidence_sha256"] != cohort_sha256
                or not isinstance(cohort_sha256, str)
                or not HEX.fullmatch(cohort_sha256)):
            raise ValueError("wrong_tenant_source_version_or_cohort")
        if (not isinstance(body["nonce"], str)
                or not NONCE.fullmatch(body["nonce"])):
            raise ValueError("invalid_review_nonce")
        issued = _clock(body["issued_at"])
        expires = _clock(body["expires_at"])
        current = now.astimezone(timezone.utc)
        if (issued > current + timedelta(minutes=5)
                or expires <= current or expires <= issued
                or expires - issued > timedelta(hours=24)):
            raise ValueError("expired_or_future_review")
        try:
            public.verify(_signature(envelope["signature"]), _payload_bytes(body))
        except InvalidSignature as exc:
            raise ValueError("invalid_reviewer_signature") from exc
        try:
            currently_authorised = self._scope(
                reviewer, tenant_id, REVIEW_SCOPE
            ) is True
        except Exception:
            currently_authorised = False
        if not currently_authorised:
            raise ValueError("current_canonical_review_membership_required")
        return {
            "reviewer_id":reviewer,
            "key_id":envelope["kid"],
            "nonce":body["nonce"],
            "source_url_sha256":body["source_url_sha256"],
            "source_content_version_sha256":body["source_content_version_sha256"],
            "decision":body["decision"],
            "signed_review_cryptographically_verified":True,
            "membership_attested_by_trusted_callback":True,
            "independent_platform_source_verified":False,
            "authenticated_buyer_verified":False,
            "outbound_authorized":False,
        }


def review_signed_gtm_case(
    manifest: Mapping[str, Any], envelopes: list[Mapping[str, Any]],
    *, verifier: GtmReviewerAttestationVerifier,
    tenant_id: str, now: datetime, source_url_sha256: str,
) -> dict[str, Any]:
    if (not isinstance(manifest, Mapping)
            or manifest.get("schema_version") != "empire.gtm_review_manifest.v1"
            or manifest.get("mode") != "OBSERVE"
            or manifest.get("authenticated_research_labels") != 0
            or manifest.get("execution_authority") != "NONE"
            or not isinstance(envelopes, list) or len(envelopes) > 5):
        raise ValueError("bounded_unpromoted_review_manifest_required")
    entries = manifest.get("requests")
    if not isinstance(entries, list) or len(entries) > 25:
        raise ValueError("bounded_review_requests_required")
    matches = [r for r in entries if isinstance(r, Mapping)
               and r.get("source_url_sha256") == source_url_sha256]
    if len(matches) != 1:
        raise ValueError("unknown_or_duplicate_manifest_source")
    approvals = []
    reviewers = set()
    nonces = set()
    for e in envelopes:
        result = verifier.verify(
            e, source=matches[0], cohort_sha256=manifest["cohort_evidence_sha256"],
            tenant_id=tenant_id, now=now,
        )
        if result["reviewer_id"] in reviewers or (
            result["key_id"], result["nonce"]
        ) in nonces:
            raise ValueError("duplicate_independent_reviewer_or_nonce")
        reviewers.add(result["reviewer_id"])
        nonces.add((result["key_id"], result["nonce"]))
        approvals.append(result["decision"])
    agreement = len(approvals) >= 2 and len(set(approvals)) == 1
    return {
        "schema_version":"empire.gtm_signed_research_adjudication.v1",
        "mode":"OBSERVE",
        "source_url_sha256":source_url_sha256,
        "cryptographically_valid_authorized_reviews":len(approvals),
        "independent_reviewer_count":len(reviewers),
        "reviewer_decision_agreement":agreement,
        "status":("TWO_SIGNED_REVIEWERS_AGREE_RESEARCH_ONLY" if agreement
                  else "REVIEWER_DISAGREEMENT_OR_INSUFFICIENT_REVIEWS"),
        "accepted_as_ground_truth":False,
        "independent_platform_authenticity_verified":False,
        "legal_company_representative_verified":False,
        "buyer_intent_verified":False,
        "real_research_labels_promoted":0,
        "model_retrained":False,
        "database_writes":False,
        "outbound_authorized":False,
        "source_attributed_revenue_cents":None,
        "execution_authority":"NONE",
    }
