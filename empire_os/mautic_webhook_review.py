"""Mautic 7 signed-webhook evidence adapter for the existing Smart CRM.

Read-only and opt-in: no HTTP listener, CRM write, subscription creation,
send, contact import, or production dependency on Mautic. The caller must
supply a server-authenticated tenant and a trusted, tenant-scoped contact map.
Mautic contact data (which may include PII) is never copied to the output.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import UUID

SCHEMA = "empire.mautic_signed_webhook_review.v1"
MAX_BODY_BYTES = 131072
MAX_BATCH_EVENTS = 40
EVENTS = frozenset({
    "mautic.form_on_submit",
    "mautic.email_on_open",
    "mautic.lead_channel_subscription_changed",
})


class MauticWebhookReviewError(ValueError):
    """Invalid, unauthenticated or unbound Mautic event evidence."""


def _canonical_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise MauticWebhookReviewError("canonical tenant/prospect identity required") from None


def _contact_id(event_name: str, event: Mapping[str, Any]) -> int:
    if event_name == "mautic.form_on_submit":
        submission = event.get("submission")
        contact = submission.get("lead") if isinstance(submission, Mapping) else None
    elif event_name == "mautic.email_on_open":
        # Verified against Mautic 7.x EmailBundle/WebhookSubscriber.php:
        # onEmailOpen() queues {'stat': $event->getStat()}, whose serialized
        # Stat::loadApiMetadata includes the nested 'lead' association.
        # Retain contact-shaped legacy synthetic fixtures only when 'stat'
        # is wholly absent; never infer a contact from email addresses.
        stat = event.get("stat")
        contact = stat.get("lead") if isinstance(stat, Mapping) else (
            event.get("contact") if stat is None else None
        )
    else:
        contact = event.get("contact")
    result = contact.get("id") if isinstance(contact, Mapping) else None
    if type(result) is not int or result <= 0:
        raise MauticWebhookReviewError("event lacks a valid Mautic contact ID")
    return result


def _event_timestamp(event: Mapping[str, Any], *, now: datetime) -> str:
    value = event.get("timestamp")
    if not isinstance(value, str) or len(value) > 64:
        return "UNVERIFIED"
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "UNVERIFIED"
    if observed.tzinfo is None:
        return "UNVERIFIED"
    delta = now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
    if delta < -timedelta(minutes=5):
        return "FUTURE_UNVERIFIED"
    if delta > timedelta(days=30):
        return "STALE_OVER_30_DAYS"
    return "RECENT_OBSERVED"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MauticWebhookReviewError("ambiguous duplicated JSON key")
        result[key] = value
    return result


def preview_signed_mautic_webhook(
    *,
    raw_body: bytes,
    signature: str,
    secret: bytes,
    authenticated_tenant_id: str,
    trusted_contact_bindings: Mapping[int, Mapping[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Verify signed Mautic webhook and emit bounded non-executable CRM signals.

    trusted_contact_bindings maps Mautic integer IDs to server-side
    {tenant_id, prospect_id}. Never build it from the webhook, public request
    headers, unverified email matches or a Mautic-provided tenant claim.
    The HMAC evidence refs are stable for a given secret/event; persistence
    and replay rejection remain responsibilities of the canonical owner.
    """
    if not isinstance(raw_body, bytes) or not 1 <= len(raw_body) <= MAX_BODY_BYTES:
        raise MauticWebhookReviewError("invalid or oversized webhook body")
    if not isinstance(secret, bytes) or len(secret) < 16:
        raise MauticWebhookReviewError("server-side webhook secret required")
    if not isinstance(signature, str) or len(signature) > 128:
        raise MauticWebhookReviewError("invalid webhook signature")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise MauticWebhookReviewError("timezone-aware clock required")
    if not isinstance(trusted_contact_bindings, Mapping):
        raise MauticWebhookReviewError("trusted server-side contact bindings required")
    tenant = _canonical_uuid(authenticated_tenant_id)

    try:
        supplied = base64.b64decode(signature, validate=True)
    except (binascii.Error, ValueError):
        raise MauticWebhookReviewError("invalid webhook signature") from None
    expected = hmac.new(secret, raw_body, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied, expected):
        raise MauticWebhookReviewError("invalid webhook signature")

    try:
        parsed = json.loads(raw_body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError) as exc:
        raise MauticWebhookReviewError("invalid signed JSON payload") from exc
    if not isinstance(parsed, dict) or not parsed or not set(parsed) <= EVENTS:
        raise MauticWebhookReviewError("unsupported Mautic event type")

    total = 0
    results: list[dict[str, Any]] = []
    unbound = 0
    for event_name, entries in parsed.items():
        if not isinstance(entries, list) or not entries:
            raise MauticWebhookReviewError("Mautic event collection required")
        total += len(entries)
        if total > MAX_BATCH_EVENTS:
            raise MauticWebhookReviewError("event batch exceeds safety limit")
        for event in entries:
            if not isinstance(event, dict):
                raise MauticWebhookReviewError("malformed Mautic event")
            contact_id = _contact_id(event_name, event)
            bound = trusted_contact_bindings.get(contact_id)
            if bound is None:
                unbound += 1
                continue
            if not isinstance(bound, Mapping):
                raise MauticWebhookReviewError("invalid canonical contact binding")
            if _canonical_uuid(bound.get("tenant_id")) != tenant:
                raise MauticWebhookReviewError("cross-tenant Mautic contact binding")
            prospect_id = _canonical_uuid(bound.get("prospect_id"))
            timestamp_state = _event_timestamp(event, now=now)
            if event_name == "mautic.lead_channel_subscription_changed":
                channel = event.get("channel")
                status = event.get("new_status")
                if channel not in ("email", "sms") or status not in (
                    "contactable", "bounced", "manual", "unsubscribed"
                ):
                    raise MauticWebhookReviewError("unrecognized subscription transition")
                # Mautic 7's MANUAL status is a do-not-contact reason,
                # never proof that a contact is available for marketing.
                # Only 'contactable' receives a neutral review label, which
                # still grants no consent and cannot clear CRM suppression.
                signal = (
                    "CONTACTABILITY_REVIEW_NOT_CONSENT" if status == "contactable"
                    else "SUPPRESSION_REVIEW_REQUIRED"
                )
            elif event_name == "mautic.form_on_submit":
                signal = "FORM_SUBMISSION_REVIEW_NOT_CONSENT"
            else:
                signal = "LOW_CONFIDENCE_EMAIL_OPEN_REVIEW"
            # Never demote a do-not-contact observation because delivery
            # was delayed. Delayed events still require human suppression
            # reconciliation; timestamp trust is separately retained.
            # Only non-suppression evidence loses engagement confidence.
            if (timestamp_state != "RECENT_OBSERVED"
                    and signal != "SUPPRESSION_REVIEW_REQUIRED"):
                signal = "STALE_OR_UNVERIFIED_EVENT_REVIEW"
            # Keyed fingerprint avoids exposing names, emails, IPs, form answers
            # or reversible unsalted hashes of Mautic's contact identifiers.
            event_key = json.dumps(
                [tenant, event_name, event], sort_keys=True, ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
            evidence_ref = hmac.new(secret, event_key, hashlib.sha256).hexdigest()
            results.append({
                "tenant_id": tenant,
                "prospect_id": prospect_id,
                "source_event": event_name,
                "signal": signal,
                "timestamp_state": timestamp_state,
                "event_evidence_hmac": evidence_ref,
                "contact_pii_disclosed": False,
                "marketing_consent_verified": False,
                "canonical_suppression_cleared": False,
                "send_authorized": False,
            })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "read_only": True,
        "signature_verified": True,
        "tenant_id": tenant,
        "event_count": total,
        "bound_event_count": len(results),
        "unbound_event_count": unbound,
        "signals": results,
        "source_contact_details_stored": False,
        "canonical_replay_rejection_integrated": False,
        "canonical_crm_written": False,
        "external_network_calls": False,
        "sender_enabled": False,
        "subscription_created": False,
        "execution_authority": "none",
    }
