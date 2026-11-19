"""Contract tests for optional signed Mautic webhook observation.

Synthetic payloads only. No external Mautic, CRM, email or database access.
"""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone, timedelta

import pytest

from empire_os.mautic_webhook_review import (
    MAX_BODY_BYTES, MauticWebhookReviewError, preview_signed_mautic_webhook,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000201"
NOW = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
SECRET = b"only-an-illustrative-32-byte-secret"


def body_for(event_type, event):
    return json.dumps({event_type: [event]}, separators=(",", ":")).encode()


def review(body, **options):
    signature = base64.b64encode(hmac.new(SECRET, body, hashlib.sha256).digest()).decode()
    kwargs = {
        "raw_body": body, "signature": signature, "secret": SECRET,
        "authenticated_tenant_id": TENANT,
        "trusted_contact_bindings": {42: {"tenant_id": TENANT, "prospect_id": PROSPECT}},
        "now": NOW,
    }
    kwargs.update(options)
    return preview_signed_mautic_webhook(**kwargs)


def subscription(status="unsubscribed", **updates):
    event = {
        "contact": {"id": 42, "email": "private@example.test",
                    "firstname": "Not For Output"},
        "channel": "email", "old_status": "contactable", "new_status": status,
        "timestamp": NOW.isoformat(),
    }
    event.update(updates)
    return body_for("mautic.lead_channel_subscription_changed", event)


def test_signed_unsubscribe_is_review_signal_not_send_authority():
    result = review(subscription())
    assert result["signature_verified"]
    assert result["bound_event_count"] == 1
    assert result["signals"][0]["signal"] == "SUPPRESSION_REVIEW_REQUIRED"
    assert result["signals"][0]["prospect_id"] == PROSPECT
    assert result["signals"][0]["marketing_consent_verified"] is False
    assert result["signals"][0]["canonical_suppression_cleared"] is False
    assert result["signals"][0]["send_authorized"] is False
    assert result["canonical_crm_written"] is False
    assert result["canonical_replay_rejection_integrated"] is False
    assert "private@example.test" not in str(result)
    assert "Not For Output" not in str(result)


def test_contactable_never_turns_into_verified_marketing_opt_in():
    result = review(subscription("contactable"))
    assert result["signals"][0]["signal"] == "CONTACTABILITY_REVIEW_NOT_CONSENT"
    assert result["subscription_created"] is False
    assert result["execution_authority"] == "none"


def test_form_submit_records_interest_only_and_drops_form_pii():
    event = {
        "submission": {
            "id": 10, "lead": {"id": 42, "email": "private@example.test"},
            "results": {"health_notes": "sensitive form content"},
            "ipAddress": {"ipAddress": "192.0.2.1"},
        },
        "timestamp": NOW.isoformat(),
    }
    result = review(body_for("mautic.form_on_submit", event))
    assert result["signals"][0]["signal"] == "FORM_SUBMISSION_REVIEW_NOT_CONSENT"
    assert "sensitive form content" not in str(result)
    assert "192.0.2.1" not in str(result)


def test_email_open_is_low_confidence_and_cannot_count_as_conversion():
    event = {"contact": {"id": 42}, "timestamp": NOW.isoformat()}
    result = review(body_for("mautic.email_on_open", event))
    assert result["signals"][0]["signal"] == "LOW_CONFIDENCE_EMAIL_OPEN_REVIEW"
    assert result["sender_enabled"] is False


def test_unmatched_contact_is_skipped_without_identity_disclosure():
    event = {"contact": {"id": 999, "email": "someone@private.test"},
             "timestamp": NOW.isoformat()}
    result = review(body_for("mautic.email_on_open", event))
    assert result["unbound_event_count"] == 1
    assert result["signals"] == []
    assert "someone@private.test" not in str(result)


def test_cross_tenant_binding_rejected_not_relabelled():
    with pytest.raises(MauticWebhookReviewError, match="cross-tenant"):
        review(subscription(), trusted_contact_bindings={
            42: {"tenant_id": OTHER, "prospect_id": PROSPECT}
        })


def test_signature_is_mandatory_and_tampering_fails_before_parsing():
    body = subscription()
    with pytest.raises(MauticWebhookReviewError, match="signature"):
        review(body, signature="tampered")
    with pytest.raises(MauticWebhookReviewError, match="signature"):
        review(body, signature="")
    with pytest.raises(MauticWebhookReviewError, match="signature"):
        review(body + b" ", signature=base64.b64encode(
            hmac.new(SECRET, body, hashlib.sha256).digest()
        ).decode())


@pytest.mark.parametrize("bad", [
    b'{"mautic.untrusted_command":[{}]}',
    b'{"mautic.email_on_open":[]}',
    b'{"mautic.email_on_open":{}}',
    b'{"mautic.email_on_open":[{"contact":{"id":true}}]}',
    b'{"mautic.email_on_open":[{"contact":{"id":0}}]}',
    b'{"mautic.email_on_open":[{"contact":{"id":42}}],"mautic.email_on_open":[]}',
])
def test_unsupported_malformed_duplicate_json_keys_fail_closed(bad):
    with pytest.raises(MauticWebhookReviewError):
        review(bad)


def test_limits_secrets_and_clock_fail_closed():
    with pytest.raises(MauticWebhookReviewError, match="oversized"):
        review(b"x" * (MAX_BODY_BYTES + 1))
    with pytest.raises(MauticWebhookReviewError, match="secret"):
        review(subscription(), secret=b"short")
    with pytest.raises(MauticWebhookReviewError, match="clock"):
        review(subscription(), now=NOW.replace(tzinfo=None))
    event = {"contact": {"id": 42}, "timestamp": NOW.isoformat()}
    body = body_for("mautic.email_on_open", event)
    batch = json.dumps({"mautic.email_on_open": [event] * 41}).encode()
    with pytest.raises(MauticWebhookReviewError, match="batch"):
        review(batch)
    assert review(body)["event_count"] == 1


def test_stale_and_future_event_timestamp_not_engagement():
    for when in [NOW - timedelta(days=45), NOW + timedelta(days=2)]:
        event = {"contact": {"id": 42}, "timestamp": when.isoformat()}
        result = review(body_for("mautic.email_on_open", event))
        assert result["signals"][0]["signal"] == "STALE_OR_UNVERIFIED_EVENT_REVIEW"


def test_fingerprint_deterministic_for_owner_replay_dedupe_but_not_persistent():
    body = subscription()
    first = review(body)
    second = review(body)
    assert first["signals"][0]["event_evidence_hmac"] == second["signals"][0]["event_evidence_hmac"]
    assert len(first["signals"][0]["event_evidence_hmac"]) == 64
    assert first["canonical_replay_rejection_integrated"] is False
