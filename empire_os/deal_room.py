"""Governed Deal Room / Documenso agreement evidence bridge.

Provider execution is intentionally separated from evidence normalization.
Nothing here sends an envelope, accepts terms, creates a payment request,
moves funds, or recognizes revenue.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

DOCUMENSO_V2_BASE_URL = "https://app.documenso.com/api/v2"
SIGNING_ROLES = frozenset({"SIGNER", "APPROVER"})


@dataclass(frozen=True)
class AgreementRecipient:
    email: str
    name: str
    role: str = "SIGNER"
    signing_order: int | None = None

    def validate(self) -> None:
        if "@" not in str(self.email or ""):
            raise ValueError("recipient email required")
        if not str(self.name or "").strip():
            raise ValueError("recipient name required")
        if self.role not in {"SIGNER", "APPROVER", "VIEWER", "CC", "ASSISTANT"}:
            raise ValueError("unsupported recipient role")
        if self.signing_order is not None and self.signing_order < 1:
            raise ValueError("signing_order must be >= 1")


@dataclass(frozen=True)
class AgreementDraft:
    external_id: str
    title: str
    document_sha256: str
    recipients: tuple[AgreementRecipient, ...]
    source_evidence_refs: tuple[str, ...]
    commercial_terms_ref: str
    redirect_url: str | None = None

    def validate(self) -> None:
        if not str(self.external_id or "").strip():
            raise ValueError("external_id required")
        if not str(self.title or "").strip():
            raise ValueError("title required")
        digest = str(self.document_sha256 or "").strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("document_sha256 must be 64 lowercase hex characters")
        if not self.recipients:
            raise ValueError("at least one recipient required")
        for recipient in self.recipients:
            recipient.validate()
        if not self.source_evidence_refs:
            raise ValueError("source evidence required")
        if not str(self.commercial_terms_ref or "").strip():
            raise ValueError("commercial_terms_ref required")


@dataclass(frozen=True)
class AgreementWebhookEvidence:
    provider: str
    event: str
    envelope_id: str
    envelope_status: str
    external_id: str | None
    observed_at: str
    completed_at: str | None
    recipient_statuses: tuple[dict[str, Any], ...]
    agreement_complete: bool
    agreement_rejected: bool
    evidence_ref: str
    canonical_commercial_mutation: bool = False
    payment_request_created: bool = False
    funds_movement: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_documenso_envelope_plan(draft: AgreementDraft) -> dict[str, Any]:
    draft.validate()
    recipients = []
    for recipient in draft.recipients:
        row: dict[str, Any] = {
            "email": recipient.email.strip(),
            "name": recipient.name.strip(),
            "role": recipient.role,
        }
        if recipient.signing_order is not None:
            row["signingOrder"] = recipient.signing_order
        recipients.append(row)

    return {
        "schema_version": "empire.deal_room.documenso_plan.v1",
        "provider": "documenso",
        "api_base_url": DOCUMENSO_V2_BASE_URL,
        "create_endpoint": "/envelope/create",
        "distribute_endpoint": "/envelope/distribute",
        "payload": {
            "type": "DOCUMENT",
            "title": draft.title.strip(),
            "externalId": draft.external_id.strip(),
            "recipients": recipients,
            "meta": (
                {"redirectUrl": draft.redirect_url}
                if draft.redirect_url else {}
            ),
        },
        "document_sha256": draft.document_sha256.lower(),
        "source_evidence_refs": list(draft.source_evidence_refs),
        "commercial_terms_ref": draft.commercial_terms_ref,
        "provider_execution": False,
        "distribution_execution": False,
        "binding_acceptance": False,
        "payment_request_created": False,
        "funds_movement": False,
        "revenue_recognition": False,
        "human_approval_required": True,
        "execution_authority": "none",
    }


def verify_documenso_webhook_secret(
    supplied_secret: str | None,
    expected_secret: str | None,
) -> bool:
    if not supplied_secret or not expected_secret:
        return False
    return hmac.compare_digest(str(supplied_secret), str(expected_secret))


def normalize_documenso_webhook(
    payload: Mapping[str, Any],
) -> AgreementWebhookEvidence:
    event = str(payload.get("event") or "").strip().upper()
    body = payload.get("payload")
    if not event or not isinstance(body, Mapping):
        raise ValueError("invalid Documenso webhook payload")

    envelope_id = str(body.get("envelopeId") or "").strip()
    if not envelope_id:
        raise ValueError("envelopeId required")

    status = str(body.get("status") or "").strip().upper()
    observed_at = str(payload.get("createdAt") or "").strip()
    if not observed_at:
        raise ValueError("createdAt required")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("createdAt must be ISO-8601") from exc

    recipient_statuses: list[dict[str, Any]] = []
    required_actions = 0
    required_complete = 0
    for row in body.get("recipients") or body.get("Recipient") or []:
        if not isinstance(row, Mapping):
            continue
        role = str(row.get("role") or "").upper()
        signing_status = str(row.get("signingStatus") or "").upper()
        if role in SIGNING_ROLES:
            required_actions += 1
            if signing_status in {"SIGNED", "APPROVED"}:
                required_complete += 1
        recipient_statuses.append({
            "recipient_id": row.get("id"),
            "role": role or None,
            "read_status": row.get("readStatus"),
            "signing_status": signing_status or None,
            "send_status": row.get("sendStatus"),
            "signed_at": row.get("signedAt"),
            "rejection_reason": row.get("rejectionReason"),
        })

    completed = (
        event == "DOCUMENT_COMPLETED"
        and status == "COMPLETED"
        and required_actions > 0
        and required_complete == required_actions
    )
    rejected = (
        event in {"DOCUMENT_REJECTED", "DOCUMENT_CANCELLED"}
        or status in {"REJECTED", "CANCELLED"}
    )

    stable = json.dumps(
        {
            "event": event,
            "envelope_id": envelope_id,
            "status": status,
            "external_id": body.get("externalId"),
            "observed_at": observed_at,
            "completed_at": body.get("completedAt"),
            "recipients": recipient_statuses,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return AgreementWebhookEvidence(
        provider="documenso",
        event=event,
        envelope_id=envelope_id,
        envelope_status=status,
        external_id=(
            str(body.get("externalId"))
            if body.get("externalId") is not None else None
        ),
        observed_at=observed_at,
        completed_at=(
            str(body.get("completedAt"))
            if body.get("completedAt") is not None else None
        ),
        recipient_statuses=tuple(recipient_statuses),
        agreement_complete=completed,
        agreement_rejected=rejected,
        evidence_ref="documenso:" + hashlib.sha256(stable).hexdigest(),
    )


def agreement_evidence_is_verified(
    evidence: AgreementWebhookEvidence,
) -> bool:
    return (
        evidence.provider == "documenso"
        and evidence.agreement_complete
        and not evidence.agreement_rejected
        and bool(evidence.evidence_ref)
    )


def canonical_agreement_record(
    evidence: AgreementWebhookEvidence,
) -> dict[str, Any]:
    verified = agreement_evidence_is_verified(evidence)
    return {
        "agreement_id": evidence.envelope_id,
        "provider": evidence.provider,
        "provider_event": evidence.event,
        "provider_evidence_ref": evidence.evidence_ref,
        "status": "signed" if verified else evidence.envelope_status.lower(),
        "verified_at": evidence.observed_at if verified else None,
        "signed_at": evidence.completed_at if verified else None,
        "evidence_verified": verified,
        "external_id": evidence.external_id,
        "canonical_commercial_mutation": False,
        "payment_request_created": False,
        "revenue_recognition": False,
    }
