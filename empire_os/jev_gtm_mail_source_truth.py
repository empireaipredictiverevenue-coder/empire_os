"""JEV first-party reply transport truth and reversible release gate.

Pure interpretation of existing Empire mail probes. This cannot authenticate
a buyer, sign a receipt, provision an inbound transport or modify routing.
When multiple providers disagree, UNKNOWN/HELD is the only valid answer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import re

SCHEMA = "empire.jev.mail_ingress_source_truth.v1"
MAX_MX = 20
_MX_RECORD = re.compile(r"^[0-9]{1,5} [A-Za-z0-9.-]{2,254}\.?$")


def _records(records: Any) -> tuple[str, ...]:
    if not isinstance(records, (list, tuple)) or len(records) > MAX_MX:
        raise ValueError("bounded MX record evidence required")
    output = []
    for raw in records:
        if not isinstance(raw, str):
            raise ValueError("valid MX record required")
        item = raw.strip().lower()
        if not _MX_RECORD.fullmatch(item):
            raise ValueError("invalid MX record evidence")
        output.append(item)
    return tuple(output)


def assess_jev_ingress_truth(
    *,
    relay_health: Mapping[str, Any] | None,
    founder_readiness: Mapping[str, Any] | None,
    inbound_health: Mapping[str, Any] | None,
    root_mx: Sequence[str],
    reply_mx: Sequence[str],
    canonical_release_dropin_present: bool | None,
    canonical_reader_credential_present: bool | None,
    probe_errors: Sequence[str] = (),
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Explicitly separate the delivery routes from independently audited proof.

    Absence of a particular vendor name is not proof of first-party ingress.
    No real message, secret, contact address or transaction is read here.
    """
    if not all(x is None or isinstance(x, Mapping) for x in (
        relay_health, founder_readiness, inbound_health
    )):
        raise ValueError("readiness contract must be a mapping")
    if (type(canonical_release_dropin_present) not in (bool, type(None))
            or type(canonical_reader_credential_present) not in (bool, type(None))):
        raise ValueError("canonical release file presence must be boolean or unknown")
    if (not isinstance(probe_errors, (list, tuple)) or len(probe_errors) > 12
            or any(not isinstance(x, str) or not re.fullmatch(r"[a-z_]{1,48}", x)
                   for x in probe_errors)):
        raise ValueError("bounded probe failure names required")
    now = observed_at or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("offset-aware observation clock required")
    roots, incoming = _records(root_mx), _records(reply_mx)
    relay = relay_health or {}
    mailbox = founder_readiness or {}
    inbound = inbound_health or {}
    google_relay = relay.get("ok") is True and relay.get("provider") == "gmail_api"
    relay_send_disabled = (
        google_relay and relay.get("mode") == "OBSERVE"
        and relay.get("send_authorized") is False
        and relay.get("mutation_authorized") is False
    )
    canonical_read = (
        mailbox.get("provider") == "empiredb_canonical_replies"
        and mailbox.get("configured") is True
        and mailbox.get("read_only") is True
        and mailbox.get("execution_authority") == "none"
    )
    old_imap_unconfigured = (
        mailbox.get("provider") == "owned_imap"
        and mailbox.get("configured") is False
    )
    resend_active = (
        inbound.get("ok") is True
        and inbound.get("provider") == "resend"
        and inbound.get("reply_transport_configured") is True
    )
    third_party_mx = any(
        "inbound-smtp" in row and "amazonaws.com" in row
        for row in incoming
    )
    google_root = any("smtp.google.com" in row for row in roots)
    # The separate (DNS -> receiver -> original signed receipt -> DB) chain
    # has NOT been audited by this metadata-only reader. Never infer yes.
    blockers: list[str] = []
    if probe_errors:
        blockers.append("REQUIRED_READONLY_EVIDENCE_PROBE_UNAVAILABLE")
    if not incoming:
        blockers.append("REPLY_DOMAIN_MX_NOT_VERIFIED")
    if third_party_mx:
        blockers.append("REPLY_MX_POINTS_TO_EXTERNAL_SES")
    if resend_active:
        blockers.append("ACTIVE_RESEND_INBOUND_SERVICE")
    if resend_active and third_party_mx:
        blockers.append("REPLY_MX_AND_WEBHOOK_PROVIDER_UNRECONCILED")
    if not google_relay:
        blockers.append("FOUNDER_GMAIL_RELAY_LIVENESS_UNVERIFIED")
    if not relay_send_disabled:
        blockers.append("OBSERVE_ONLY_RELAY_INVARIANT_UNVERIFIED")
    if old_imap_unconfigured:
        blockers.append("OWNED_IMAP_READER_NOT_CONFIGURED")
    if not canonical_read:
        blockers.append("CANONICAL_FOUNDER_REPLY_VIEW_NOT_LIVE")
    if canonical_release_dropin_present is not True:
        blockers.append("CANONICAL_VIEW_RELEASE_DROPIN_NOT_PROVEN")
    if canonical_reader_credential_present is not True:
        blockers.append("CANONICAL_VIEW_RESTRICTED_READER_NOT_PROVEN")
    blockers.extend([
        "FIRST_PARTY_INBOUND_TRANSPORT_OWNER_NOT_AUDITED",
        "ORIGINAL_SMTP_INGRESS_ATTESTATION_NOT_VERIFIED",
        "CANONICAL_TENANT_CONTACT_BINDING_NOT_VERIFIED",
        "CONSENT_AND_SUPPRESSION_CLEARANCE_NOT_VERIFIED",
        "ORIGINAL_BUYER_REPLY_OUTCOME_NOT_VERIFIED",
    ])
    blockers = sorted(set(blockers))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "captured_at": now.astimezone(timezone.utc).isoformat(),
        "status": "HOLD_FIRST_PARTY_REPLY_ACTIVATION",
        "google_root_mx_observed": google_root if roots else None,
        "reply_domain_mx_observed": bool(incoming) if incoming else None,
        "reply_mx_external_ses_observed": third_party_mx if incoming else None,
        "resend_webhook_reported_active": resend_active if inbound else None,
        "gmail_relay_observed": google_relay if relay else None,
        "gmail_relay_send_disabled": relay_send_disabled if relay else None,
        "founder_mailbox_provider": (
            mailbox.get("provider") if mailbox.get("provider") in (
                "owned_imap", "google_workspace", "empiredb_canonical_replies"
            ) else None
        ),
        "canonical_reply_view_live": canonical_read if mailbox else None,
        "canonical_view_release_dropin_present": canonical_release_dropin_present,
        "canonical_reader_credential_present": canonical_reader_credential_present,
        "signed_first_party_ingress_producer_present": None,
        "independently_verified_buyer_replies": None,
        "original_provider_receipt_identity_verified": False,
        "canonical_contact_verified": False,
        "verified_commercial_revenue": None,
        "first_party_inbound_transport_verified": False,
        "source_provider_mismatch_observed": bool(
            resend_active and third_party_mx
        ),
        "blocked_reasons": blockers,
        "release_sequence": [
            "identify_owner_and_verify_current_mail_receiving_route",
            "confirm_mail_reception_and_original_receipt_integrity",
            "provision_and_audit_first_party_ingress_before_mx_cutover",
            "reconcile_canonical_db_reader_and_migration_051_separately",
            "verify_tenant_contact_and_suppression_authority",
            "perform_founder_approved_controlled_end_to_end_reply_test",
            "calibrate_jev_against_real_independently_reviewed_buyer_outcomes",
        ],
        "production_changes_performed": False,
        "dns_modified": False,
        "mail_sent": False,
        "mailbox_reads": False,
        "database_reads": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
