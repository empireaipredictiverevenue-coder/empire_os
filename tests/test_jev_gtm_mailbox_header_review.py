"""Isolated synthetic tests for first-party IMAP -> JEV review, no sends."""
from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import UUID

import pytest

from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider
from empire_os.jev_gtm_mailbox_header_review import (
    review_owned_mailbox_headers, compare_owned_mailbox_to_crm_candidates,
)

KEY = b"operator test key, not used in production 0000000000000"
INTENT = str(UUID(int=100))
REPLY = str(UUID(int=101))
SENT_MESSAGE = "<sent-demo-1@empire.example>"
INBOUND = "<inbound-demo-1@buyer.example>"


def original_mail(*, is_reply, message_id=None, in_reply_to=None, intent=INTENT):
    msg = EmailMessage()
    msg["Message-ID"] = message_id or (INBOUND if is_reply else SENT_MESSAGE)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    msg["From"] = "PRIVATE BUYER <private@example.invalid>" if is_reply else "phil@mail.empire-ai.co.uk"
    msg["To"] = (
        f"reply+{intent}@mail.empire-ai.co.uk"
        if is_reply else "person@example.invalid"
    )
    msg["Date"] = "Wed, 14 Oct 2026 10:00:00 +0000"
    msg["Subject"] = "Secret private details"
    msg.set_content("SECRET BUYER BODY: please send quote!")
    return msg.as_bytes()


def extracted(*, is_reply, uid, message_id=None, parent=None, intent=INTENT):
    return OwnedIMAPMailboxProvider._extract(
        original_mail(is_reply=is_reply, message_id=message_id,
                      in_reply_to=parent, intent=intent),
        identity=f"imap:{'inbox' if is_reply else 'sent'}:77:{uid}",
        direction="inbox" if is_reply else "sent",
        server_internal_date="2026-10-14T11:00:00+00:00",
    )


class FakeReadOnlyOwnedIMAP(OwnedIMAPMailboxProvider):
    def __init__(self, inbox, sent):
        super().__init__(
            host="mail.empire-ai.co.uk", username="phil@mail.empire-ai.co.uk",
            password="OFFLINE_FAKE_NEVER_NETWORK",
        )
        self.inbox, self.sent = inbox, sent
        self.calls = []

    def list_received(self, *, limit):
        self.calls.append(("INBOX_READONLY", limit))
        return self.inbox

    def list_sent(self, *, limit):
        self.calls.append(("SENT_READONLY", limit))
        return self.sent


def safe_case(*, inbox=None, sent=None):
    return FakeReadOnlyOwnedIMAP(
        inbox if inbox is not None else [
            extracted(is_reply=True, uid=4, parent=SENT_MESSAGE)
        ],
        sent if sent is not None else [
            extracted(is_reply=False, uid=3)
        ],
    )


def candidate(intent=INTENT):
    return {
        "schema_version": "empire.jev.reply_candidate_review.v1",
        "execution_authority": "none",
        "send_authorized": False,
        "genuine_buying_conversations_verified": None,
        "items": [{
            "intent_ref": intent,
            "reply_ref": REPLY,
            "outbound_authorized": False,
        }],
    }


def test_matching_original_rfc_pair_is_only_structural():
    provider = safe_case()
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert provider.calls == [("INBOX_READONLY", 25), ("SENT_READONLY", 25)]
    assert result["structurally_reviewable_count"] == 1
    assert result["rows"][0]["sent_rfc_parent_unique"] is True
    assert result["rows"][0]["original_provider_authenticated"] is False
    assert result["rows"][0]["positive_buyer_intent_verified"] is False
    assert result["provider_receipts_authenticated"] is False
    assert result["commercial_buyer_reply_count"] is None
    assert result["mailbox_mutations"] is False
    assert result["execution_authority"] == "none"
    rendered = repr(result)
    for private in (
        "private@example.invalid", "SECRET BUYER BODY",
        "Secret private details", SENT_MESSAGE, INBOUND, INTENT,
        "phil@mail.empire-ai.co.uk",
    ):
        assert private not in rendered


def test_alias_matches_only_as_unverified_candidate_hint():
    review = review_owned_mailbox_headers(safe_case(), key=KEY)
    report = compare_owned_mailbox_to_crm_candidates(review, candidate(), key=KEY)
    assert report["candidate_count"] == 1
    assert report["rows"][0]["linkage_status"] == "ALIAS_UNIQUE_UNAUTHENTICATED"
    assert report["tenant_binding_proven_across_sources"] is False
    assert report["buyer_conversation_count_verified"] is None
    assert report["contact_permission_granted"] is False
    assert INTENT not in repr(report)


def test_missing_reply_parent_never_structurally_matches():
    provider = safe_case(inbox=[extracted(is_reply=True, uid=4)])
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert result["structurally_reviewable_count"] == 0
    assert "ORIGINAL_RFC_PARENT_MISSING" in result["rows"][0]["blockers"]


def test_no_sent_pair_is_not_a_verified_conversation():
    provider = safe_case(sent=[])
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert result["rows"][0]["status"] == "QUARANTINED"
    assert "ORIGINAL_SENT_PARENT_NOT_IN_BOUNDED_SAMPLE" in result["rows"][0]["blockers"]
    assert result["commercial_buyer_reply_count"] is None


def test_duplicate_sent_rfc_id_does_not_choose_one_arbitrarily():
    provider = safe_case(sent=[
        extracted(is_reply=False, uid=3),
        extracted(is_reply=False, uid=5),
    ])
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert "ORIGINAL_SENT_PARENT_AMBIGUOUS" in result["rows"][0]["blockers"]


def test_duplicate_received_rfc_id_quarantined():
    provider = safe_case(inbox=[
        extracted(is_reply=True, uid=4, parent=SENT_MESSAGE),
        extracted(is_reply=True, uid=5, parent=SENT_MESSAGE),
    ])
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert result["structurally_reviewable_count"] == 0
    assert all("DUPLICATE_INBOUND_RFC_MESSAGE_ID" in r["blockers"]
               for r in result["rows"])


def test_duplicate_uid_quarantined():
    msg = extracted(is_reply=True, uid=4, parent=SENT_MESSAGE)
    provider = safe_case(inbox=[msg, dict(msg)])
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert result["structurally_reviewable_count"] == 0
    assert all("DUPLICATE_IMAP_INBOX_UID" in r["blockers"]
               for r in result["rows"])


def test_missing_alias_keeps_unknown_contact():
    fake = extracted(is_reply=True, uid=4, parent=SENT_MESSAGE)
    fake["to"] = ["not-an-alias@example.invalid"]
    result = review_owned_mailbox_headers(safe_case(inbox=[fake]), key=KEY)
    assert result["rows"][0]["intent_alias_ref"] is None
    assert "CANONICAL_REPLY_ALIAS_MISSING" in result["rows"][0]["blockers"]


def test_bounded_reads_invalid_limit_fail_before_mailbox():
    provider = safe_case()
    for bad in (0, 26, -1, True, "10", 2.2):
        with pytest.raises(ValueError, match="bounded"):
            review_owned_mailbox_headers(provider, key=KEY, limit=bad)
    assert provider.calls == []


def test_hmac_secret_required_and_no_secret_in_packet():
    provider = safe_case()
    with pytest.raises(ValueError, match="HMAC"):
        review_owned_mailbox_headers(provider, key=b"weak")
    a = review_owned_mailbox_headers(provider, key=KEY)
    b = review_owned_mailbox_headers(provider, key=KEY)
    assert a == b
    assert KEY.hex() not in repr(a)


def test_hmac_changes_for_different_owner_key():
    provider = safe_case()
    a = review_owned_mailbox_headers(provider, key=KEY)
    b = review_owned_mailbox_headers(provider, key=b"DIFFERENT_TEST_OPERATOR_SECRET_00000000")
    assert a["rows"][0]["record_ref"] != b["rows"][0]["record_ref"]


def test_ambiguous_crm_alias_hints_remain_unverified():
    same_alias = [
        extracted(is_reply=True, uid=4, parent=SENT_MESSAGE),
        extracted(is_reply=True, uid=5, message_id="<second@buyer.example>",
                  parent=SENT_MESSAGE),
    ]
    review = review_owned_mailbox_headers(safe_case(inbox=same_alias), key=KEY)
    result = compare_owned_mailbox_to_crm_candidates(review, candidate(), key=KEY)
    assert result["rows"][0]["mailbox_alias_matching_rows"] == 2
    assert result["rows"][0]["linkage_status"] == "ALIAS_AMBIGUOUS_UNAUTHENTICATED"
    assert result["rows"][0]["positive_buyer_reply_verified"] is False


def test_wrong_alias_does_not_cross_promote():
    review = review_owned_mailbox_headers(safe_case(), key=KEY)
    result = compare_owned_mailbox_to_crm_candidates(review, candidate(
        intent=str(UUID(int=999)),
    ), key=KEY)
    assert result["rows"][0]["linkage_status"] == "NO_ALIAS_MATCH_IN_BOUNDED_INBOX"


def test_untrusted_mailbox_and_crm_packets_fail_closed():
    review = review_owned_mailbox_headers(safe_case(), key=KEY)
    for mutation in (
        {"provider_receipts_authenticated": True},
        {"canonical_identity_authenticated": True},
        {"outbound_authorized": True},
    ):
        tainted = {**review, **mutation}
        with pytest.raises(ValueError, match="trusted"):
            compare_owned_mailbox_to_crm_candidates(tainted, candidate(), key=KEY)
    with pytest.raises(ValueError, match="trusted"):
        compare_owned_mailbox_to_crm_candidates(review, {
            **candidate(), "genuine_buying_conversations_verified": 1,
        }, key=KEY)


def test_mailbox_invalid_source_proves_nothing():
    provider = safe_case()
    invalid = provider.inbox[0]
    invalid["canonical_contact_identity_verified"] = True
    result = review_owned_mailbox_headers(provider, key=KEY)
    assert "MAILBOX_CONTACT_AUTHORITY_CONTRACT_INVALID" in result["rows"][0]["blockers"]
    assert result["structurally_reviewable_count"] == 0
