"""Conservative recipient opt-out detection from incomplete canonical previews."""
import pytest

from empire_os.reply_opt_out_evidence import explicit_opt_out_from_preview
from empire_os.empire_mailbox import normalise_received_email, build_mailbox


@pytest.mark.parametrize("subject, body,expected", [
    ("Re: David — opportunity intelligence for Gastley Law",
     "Opt out\nOn Mon, Sep 28, 2026 at 8:04 PM Phil wrote:\n> Hi,\n> If you'd rather not hear from me, reply opt out", True),
    ("Re: Roofing / HVAC inbound call supply — current buy box?",
     "Hi, Thanks for reaching out. Please remove me from your mailing list.", True),
    ("opt out", "[provider body unavailable]", True),
    ("Re: James — quick idea for Tarrytown Roofing",
     "[provider body unavailable]", False),
    ("Re: hello", "Thanks for the information.\nOn Mon, Sep 28 wrote:\n> To unsubscribe, reply opt out", False),
    ("Re: hello", "Don't want to opt out. Please tell me more.", False),
    ("Subject: marketing", "This proposal includes an unsubscribe mechanism.", False),
    ("Re: subscribe?", "What does opt out mean?", False),
    ("Re: Hello", "Please do not contact me again.", True),
])
def test_unambiguous_optout_only(subject, body, expected):
    result = explicit_opt_out_from_preview(subject, body)
    assert result["explicit_opt_out_observed"] is expected
    assert result["suppression_write_verified"] is False
    assert result["auto_apply"] is False


def _incoming(subject, body):
    return normalise_received_email({
        "id": "canonical-reply:07396f1e-f182-416d-b3de-3e5942cbbfa3",
        "intent_id": "b14bd6c9-e801-4de0-9b6b-232142c6c1a2",
        "from": "david@gastleylaw.com",
        "to": ["david@gastleylaw.com"],
        "subject": subject,
        "text": body,
        "body_preview_only": True,
        "received_at": "2026-09-29T00:31:01+00:00",
    }, provider="empiredb_canonical_replies")


def test_canonical_inbound_optout_held_even_when_body_is_preview_only():
    event = _incoming("Re: Gastley", "Opt out\nOn Monday Phil wrote:\n> marketing")
    assert event["classification"] == "unsubscribe"
    assert event["suppressed"] is True
    assert event["canonical_suppression_write_verified"] is False
    assert event["classification_confidence"] is None
    mailbox = build_mailbox([], [{
        "id": "canonical-reply:07396f1e-f182-416d-b3de-3e5942cbbfa3",
        "intent_id": "b14bd6c9-e801-4de0-9b6b-232142c6c1a2",
        "from": "david@gastleylaw.com",
        "to": ["david@gastleylaw.com"],
        "subject": "Re: Gastley", "text": "Opt out",
        "body_preview_only": True,
        "received_at": "2026-09-29T00:31:01+00:00",
    }], provider="empiredb_canonical_replies", suppression_evidence_complete=False)
    thread = mailbox["threads"][0]
    assert thread["classification"] == "unsubscribe"
    assert thread["suppressed"] is True
    assert thread["next_action"] == "suppress_and_close"
    assert mailbox["summary"]["positive"] == 0
    assert mailbox["summary"]["verified_canonical_buyer_replies"] == 0


def test_ambiguous_preview_does_not_become_positive_or_suppressed():
    event = _incoming("Re: Tarrytown Roofing", "[provider body unavailable]")
    assert event["classification"] == "unknown"
    assert event["suppressed"] is False
    assert event["canonical_suppression_write_verified"] is False


def test_positive_preview_never_triggers_sales_approval():
    event = _incoming("Re: business", "I'm interested. Send the price.")
    assert event["classification"] == "unknown"
    assert event["suppressed"] is False
