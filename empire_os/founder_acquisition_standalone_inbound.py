"""Read-only, bounded Gmail review for NEW THREADS from already-contacted companies.

The original nine sent-message anchors remain the sole prospect authority.
A new message from a domain is only a header candidate, never a qualified
buyer, affirmative consent, verified SMTP reply, or an outbound instruction.
No message body, subject, sender address, token or RFC Message-ID is stored.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from empire_os.workspace_solar_reply_tracking import (
    EvidenceHeld, _email_from, _headers, _labels, _occurred,
    _rfc_relation, _valid_rfc_id, _workspace_recipient_routing,
)
from empire_os.founder_acquisition_autopilot import GMAIL_ID

# Search Gmail metadata only; exact sender-domain matching is done AFTER
# retrieval. A query match alone does not establish organisational identity.
START = "2026/10/22"
MAX_RESULTS = 50
INBOUND_METADATA_HEADERS = ["From", "To", "Message-ID", "In-Reply-To", "References"]
STATE = "STANDALONE_INBOUND_HEADERS_REVIEW_ONLY"


def discover(
    service: Any, anchors: list[tuple[str, str, str]],
    original_threads: Mapping[str, Any], *, now: datetime,
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(now, datetime) or not now.tzinfo or now.utcoffset() is None:
        raise EvidenceHeld("STANDALONE_TRUSTED_NOW_REQUIRED")
    by_domain = {}
    sent_at = {}
    original_rfc = {}
    thread_ids = set()
    for company, address, tid in anchors:
        domain = address.rsplit("@", 1)[-1].lower()
        if domain in by_domain or tid in thread_ids or not GMAIL_ID.fullmatch(tid):
            raise EvidenceHeld("STANDALONE_ANCHOR_DUPLICATE")
        by_domain[domain] = (company, address)
        thread_ids.add(tid)
        messages = original_threads[tid]["messages"]
        sent = next((m for m in messages if m.get("id") == tid), None)
        if not sent:
            raise EvidenceHeld("STANDALONE_SENT_ANCHOR_MISSING")
        sent_at[domain] = _occurred(sent, now=now)
        original_rfc[domain] = _valid_rfc_id(_headers(sent).get("message-id", ""))
    # A bounded static search avoids scanning any unrelated mailbox contacts.
    # Explicitly exclude sent/draft/trash/spam; anything else must be inspected.
    domains = sorted(by_domain)
    q = (
        "after:" + START + " -in:sent -in:trash -in:spam -in:drafts "
        + "{" + " ".join("from:" + domain for domain in domains) + "}"
    )
    listing = service.users().messages().list(
        userId="me", q=q, maxResults=MAX_RESULTS,
    ).execute()
    if (not isinstance(listing, Mapping)
            or listing.get("nextPageToken")):
        raise EvidenceHeld("STANDALONE_GMAIL_SEARCH_INCOMPLETE")
    messages = listing.get("messages", [])
    if not isinstance(messages, list) or len(messages) > MAX_RESULTS:
        raise EvidenceHeld("STANDALONE_GMAIL_LIST_INVALID")
    old = {}
    if previous is not None:
        previous_candidates = previous.get("standalone_inbound_header_candidates", [])
        if not isinstance(previous_candidates, list) or len(previous_candidates) > MAX_RESULTS:
            raise EvidenceHeld("STANDALONE_PREVIOUS_SNAPSHOT_INVALID")
        for item in previous_candidates:
            if (not isinstance(item, dict)
                    or item.get("gmail_message_id") in old
                    or item.get("company") not in set(by_domain[d][0] for d in by_domain)
                    or not isinstance(item.get("gmail_message_id"), str)
                    or not GMAIL_ID.fullmatch(item["gmail_message_id"])):
                raise EvidenceHeld("STANDALONE_PREVIOUS_CANDIDATE_UNTRUSTED")
            old[item["gmail_message_id"]] = item
    seen = set()
    current = []
    for ref in messages:
        if not isinstance(ref, Mapping):
            raise EvidenceHeld("STANDALONE_MESSAGE_REFERENCE_UNTRUSTED")
        mid, tid = ref.get("id"), ref.get("threadId")
        if (not isinstance(mid, str) or not GMAIL_ID.fullmatch(mid)
                or not isinstance(tid, str) or not GMAIL_ID.fullmatch(tid)
                or mid in seen):
            raise EvidenceHeld("STANDALONE_GMAIL_REFERENCE_INVALID")
        seen.add(mid)
        if tid in thread_ids:
            # Original thread replies are handled by the nine-thread monitor.
            continue
        msg = service.users().messages().get(
            userId="me", id=mid, format="metadata",
            metadataHeaders=INBOUND_METADATA_HEADERS,
        ).execute()
        if (not isinstance(msg, Mapping) or msg.get("id") != mid
                or msg.get("threadId") != tid):
            raise EvidenceHeld("STANDALONE_MESSAGE_IDENTITY_MISMATCH")
        labels = _labels(msg)
        if labels & {"SENT", "DRAFT", "TRASH", "SPAM"}:
            continue
        headers = _headers(msg)
        sender = _email_from(headers.get("from", ""))
        domain = sender.rsplit("@", 1)[-1]
        if domain not in by_domain:
            # Broad Gmail search results are not identities. Never import them.
            continue
        company, original_contact = by_domain[domain]
        received_at = _occurred(msg, now=now)
        if received_at <= sent_at[domain]:
            # Earlier existing correspondence is not a response to this send.
            continue
        if _workspace_recipient_routing(headers) != "EXPECTED_WORKSPACE_TO":
            continue
        current.append({
            "gmail_message_id": mid, "company": company,
            "gmail_thread_id": tid, "received_at_utc": received_at.isoformat(),
            "sender_correspondence": (
                "EXACT_ORIGINAL_RECIPIENT" if sender == original_contact
                else "SAME_DOMAIN_DIFFERENT_ADDRESS"
            ),
            "rfc_parent_relation": _rfc_relation(
                outbound_id=original_rfc[domain], incoming=headers,
            ),
            "status": "INBOUND_HEADER_CANDIDATE_REQUIRES_HUMAN_REVIEW",
            "buyer_intent_verified": False,
            "automatic_reply_authorized": False,
        })
    ids = {item["gmail_message_id"] for item in current}
    if not set(old).issubset(ids):
        raise EvidenceHeld("STANDALONE_PRIOR_CANDIDATE_DISAPPEARED")
    return {
        "status": STATE,
        "standalone_search_coverage_complete": True,
        "standalone_inbound_header_candidates": sorted(current, key=lambda r: r["gmail_message_id"]),
        "standalone_inbound_candidate_count": len(current),
        "new_standalone_inbound_candidates": len(ids - set(old)),
        "buyer_intent_verified": False,
        "outbound_sent": False,
        "crm_writes": False,
        "automatic_reply_authorized": False,
    }
