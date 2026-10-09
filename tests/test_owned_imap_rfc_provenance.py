"""Original RFC message headers are evidence hints, not a verified buyer receipt."""
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime

from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider


def sample():
    m = EmailMessage()
    m["Message-ID"] = "<received-42@buyer.example>"
    m["In-Reply-To"] = "<original-38@empire.example>"
    m["References"] = "<earlier-1@empire.example> <original-38@empire.example>"
    m["Date"] = format_datetime(datetime(2020, 1, 1, tzinfo=timezone.utc))
    m["From"] = "Buyer <buyer@example.test>"
    m["To"] = "reply+11111111-2222-3333-4444-555555555555@mail.empire-ai.co.uk"
    m["Subject"] = "Re: Quote"
    m.set_content("Please send pricing.")
    return m.as_bytes()


def test_original_header_chain_is_preserved_without_authentication():
    row = OwnedIMAPMailboxProvider._extract(
        sample(), identity="imap:inbox:77:42", direction="inbox"
    )
    assert row["id"] == "imap:inbox:77:42"
    assert row["message_id"] == "<received-42@buyer.example>"
    assert row["in_reply_to"] == "<original-38@empire.example>"
    assert row["references"] == "<earlier-1@empire.example> <original-38@empire.example>"
    assert row["canonical_thread_identity_verified"] is False
    assert row["canonical_contact_identity_verified"] is False
    assert row["source_received_at_verified"] is False


def test_sender_controlled_date_cannot_count_as_provider_receipt():
    row = OwnedIMAPMailboxProvider._extract(
        sample(), identity="imap:inbox:77:42", direction="inbox"
    )
    assert row["message_date"] == "2020-01-01T00:00:00+00:00"
    assert row["received_at"] is None
    assert row["source_received_at_verified"] is False


def test_missing_rfc_headers_never_synthesizes_identity():
    m = EmailMessage()
    m["From"] = "buyer@example.test"
    m["Date"] = format_datetime(datetime(2026, 10, 9, tzinfo=timezone.utc))
    m.set_content("Hi")
    row = OwnedIMAPMailboxProvider._extract(
        m.as_bytes(), identity="imap:inbox:77:20", direction="inbox"
    )
    assert row["message_id"] is None
    assert row["in_reply_to"] is None
    assert row["references"] is None
    assert row["canonical_thread_identity_verified"] is False
    assert row["received_at"] is None


def test_imap_server_internaldate_is_separate_from_sender_header_date():
    from empire_os.owned_imap_mailbox import MAX_BYTES
    class Source:
        def uid(self, command, uid, query):
            assert (command, uid) == ("FETCH", "42")
            assert "INTERNALDATE" in query
            assert "BODY.PEEK" in query
            return "OK", [
                (b'42 (INTERNALDATE "09-Oct-2026 12:34:56 +0000" BODY[] {350}',
                 sample()),
                b')',
            ]
    own = OwnedIMAPMailboxProvider(
        host="mail.example.org", username="owner@example.org",
        password="fake-test-password",
    )
    result = own._fetch(Source(), folder_role="inbox", validity="77", uid="42")
    assert result["mailbox_internal_date"] == "2026-10-09T12:34:56+00:00"
    assert result["mailbox_internal_date_observed"] is True
    assert result["message_date"] == "2020-01-01T00:00:00+00:00"
    # Internaldate may be set on IMAP APPEND; not SMTP receipt proof.
    assert result["received_at"] is None
    assert result["source_received_at_verified"] is False
    assert result["message_id"] == "<received-42@buyer.example>"


def test_missing_or_malformed_internaldate_never_becomes_delivery_evidence():
    own = OwnedIMAPMailboxProvider(
        host="mail.example.org", username="owner@example.org",
        password="fake-test-password",
    )
    for raw in (
        b"42 (BODY[] {100}",
        b'42 (INTERNALDATE "malicious 3000-10-05" BODY[] {100}',
        b'42 (INTERNALDATE "99-Oct-2026 12:34:56 +0000" BODY[] {100}',
    ):
        assert own._imap_internaldate(raw) is None
    assert own._imap_internaldate(
        b'42 (INTERNALDATE "09-Oct-2026 23:35:42 +0100" BODY[] {100}'
    ) == "2026-10-09T22:35:42+00:00"
