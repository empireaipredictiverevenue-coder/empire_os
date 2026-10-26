"""Two real UK solar payer prospects in the EXISTING Workspace metadata cycle.

Only Gmail metadata from the already identity-checked Workspace read scope.
No new Gmail client, timer, CRM, contact promotion or autonomous outreach.
A provider thread candidate is NOT buyer acceptance, a payable contract or cash.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import getaddresses
from typing import Any, Mapping

from empire_os.workspace_solar_reply_tracking import (
    EvidenceHeld, HEADERS, HEX, MAX_THREAD_MESSAGES,
    WORKSPACE_RECEIVE_ADDRESSES, _email_from, _headers, _labels,
    _occurred, _rfc_relation, _valid_rfc_id, _workspace_recipient_routing,
)

SCHEMA = "empire.workspace_priority_payer_threads.v1"
ANCHORS = (
    ("Newpower Advanced", "1a14198c18924c8d", "1a1419d4e33eff52"),
    ("HPO Homes", "1a1419da604076da", "1a1419da604076da"),
)
IDS = frozenset(a[1] for a in ANCHORS)


def _sent_recipient(to_header: str) -> str:
    """One original recipient, derived from authenticated sent metadata."""
    if not isinstance(to_header, str) or not 1 <= len(to_header) <= 512:
        raise EvidenceHeld("PRIORITY_ORIGINAL_RECIPIENT_UNVERIFIED")
    try:
        parsed = getaddresses([to_header], strict=True)
        if len(parsed) != 1:
            raise EvidenceHeld("PRIORITY_ORIGINAL_RECIPIENT_UNVERIFIED")
        recipient = _email_from(parsed[0][1])
    except (ValueError, TypeError, IndexError) as exc:
        raise EvidenceHeld("PRIORITY_ORIGINAL_RECIPIENT_UNVERIFIED") from exc
    if recipient in WORKSPACE_RECEIVE_ADDRESSES:
        raise EvidenceHeld("PRIORITY_ORIGINAL_RECIPIENT_UNVERIFIED")
    return recipient


def review_priority_payer_threads(results: Mapping[str, Any], *,
                                  now: datetime) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise EvidenceHeld("PRIORITY_TRUSTED_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if not isinstance(results, Mapping) or set(results) != IDS:
        raise EvidenceHeld("PRIORITY_TWO_THREADS_INCOMPLETE")
    output = []
    for name, tid, anchor in ANCHORS:
        thread = results[tid]
        if not isinstance(thread, Mapping) or thread.get("id") != tid:
            raise EvidenceHeld("PRIORITY_THREAD_ID_MISMATCH")
        messages = thread.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_THREAD_MESSAGES:
            raise EvidenceHeld("PRIORITY_THREAD_INCOMPLETE")
        seen = set()
        sent_at = None
        sent_rfc_id = ""
        original_recipient = None
        potential = []
        for msg in messages:
            if not isinstance(msg, Mapping):
                raise EvidenceHeld("PRIORITY_MESSAGE_INVALID")
            mid = msg.get("id")
            if not isinstance(mid, str) or not HEX.fullmatch(mid) or mid in seen:
                raise EvidenceHeld("PRIORITY_MESSAGE_ID_INVALID_OR_DUPLICATE")
            seen.add(mid)
            if msg.get("threadId") != tid:
                raise EvidenceHeld("PRIORITY_MESSAGE_THREAD_MISMATCH")
            headers = _headers(msg)
            sender = _email_from(headers.get("from", ""))
            when = _occurred(msg, now=now)
            labels = _labels(msg)
            if mid == anchor:
                if ("SENT" not in labels or "DRAFT" in labels or
                        sender not in WORKSPACE_RECEIVE_ADDRESSES):
                    raise EvidenceHeld("PRIORITY_ORIGINAL_SENT_UNVERIFIED")
                original_recipient = _sent_recipient(headers.get("to", ""))
                sent_rfc_id = _valid_rfc_id(headers.get("message-id", ""))
                sent_at = when
                continue
            if labels & {"SENT", "DRAFT", "SPAM", "TRASH"}:
                continue
            potential.append((mid, when, sender, headers))
        if sent_at is None or original_recipient is None:
            raise EvidenceHeld("PRIORITY_SENT_ANCHOR_MISSING")
        candidates = []
        for mid, when, sender, headers in potential:
            if when <= sent_at:
                raise EvidenceHeld("PRIORITY_INBOUND_BEFORE_ANCHOR")
            # A same-domain different address may be a colleague, not a
            # verified contact; preserve as an unqualified header candidate.
            if sender in WORKSPACE_RECEIVE_ADDRESSES or (
                sender != original_recipient
                and sender.split("@")[-1] != original_recipient.split("@")[-1]
            ):
                continue
            if _workspace_recipient_routing(headers) != "EXPECTED_WORKSPACE_TO":
                continue
            candidates.append({
                "gmail_message_id": mid,
                "received_at": when.isoformat(),
                "rfc_parent_relation": _rfc_relation(
                    outbound_id=sent_rfc_id, incoming=headers,
                ),
                "sender_correspondence": (
                    "EXACT_ORIGINAL_RECIPIENT" if sender == original_recipient
                    else "SAME_DOMAIN_DIFFERENT_ADDRESS"
                ),
                "status": "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED",
            })
        output.append({
            "company": name,
            "gmail_thread_id": tid,
            "sent_message_id": anchor,
            "original_sent_proven_in_workspace": True,
            "sent_at": sent_at.isoformat(),
            "inbound_header_candidates": sorted(
                candidates, key=lambda item: (item["received_at"], item["gmail_message_id"])
            ),
            "buyer_contact_authority_verified": False,
            "payable_terms_verified": False,
            "crm_promotion_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "TWO_PRIORITY_PAYER_THREADS_REVIEWED",
        "mode": "OBSERVE",
        "scope": "exact_two_uk_residential_solar_payer_prospect_threads",
        "scanned_at": now.isoformat(),
        "monitored_threads": len(output),
        "verified_original_sends": len(output),
        "inbound_header_candidate_count": sum(
            len(item["inbound_header_candidates"]) for item in output
        ),
        "threads": output,
        "mailbox_full_coverage_verified": False,
        "message_bodies_or_subjects_retained": False,
        "contact_or_buyer_authority_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "automatic_reply_authorized": False,
        "payment_action": False,
        "recognized_revenue": False,
        "execution_authority": "none",
    }


def collect_priority_payer_threads(service: Any, *, now: datetime) -> dict[str, Any]:
    results = {}
    for _, tid, _ in ANCHORS:
        results[tid] = service.users().threads().get(
            userId="me", id=tid, format="metadata", metadataHeaders=HEADERS,
        ).execute()
    return review_priority_payer_threads(results, now=now)


def newly_observed_priority_candidates(current: Mapping[str, Any],
                                        previous: Mapping[str, Any] | None) -> int:
    def ids(snapshot: Mapping[str, Any]) -> dict[str, set[str]]:
        if (not isinstance(snapshot, Mapping)
                or snapshot.get("schema_version") != SCHEMA
                or snapshot.get("status") != "TWO_PRIORITY_PAYER_THREADS_REVIEWED"
                or snapshot.get("monitored_threads") != 2
                or snapshot.get("verified_original_sends") != 2
                or snapshot.get("outbound_sent") is not False):
            raise EvidenceHeld("PRIORITY_PREVIOUS_SNAPSHOT_INVALID")
        rows = snapshot.get("threads")
        if not isinstance(rows, list) or len(rows) != 2:
            raise EvidenceHeld("PRIORITY_SNAPSHOT_COVERAGE_INVALID")
        seen = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise EvidenceHeld("PRIORITY_SNAPSHOT_ROW_INVALID")
            tid = row.get("gmail_thread_id")
            anchor = next((a for a in ANCHORS if a[1] == tid), None)
            if (anchor is None or tid in seen
                    or row.get("company") != anchor[0]
                    or row.get("sent_message_id") != anchor[2]
                    or row.get("original_sent_proven_in_workspace") is not True
                    or not isinstance(row.get("inbound_header_candidates"), list)):
                raise EvidenceHeld("PRIORITY_SENT_IDENTITY_DRIFT")
            candidate_rows = row["inbound_header_candidates"]
            identifiers = [c.get("gmail_message_id")
                           for c in candidate_rows if isinstance(c, Mapping)]
            if len(identifiers) != len(candidate_rows) or len(set(identifiers)) != len(identifiers):
                raise EvidenceHeld("PRIORITY_CANDIDATE_ID_INVALID")
            seen[tid] = set(identifiers)
        if set(seen) != IDS:
            raise EvidenceHeld("PRIORITY_COVERAGE_DRIFT")
        return seen
    new = ids(current)
    old = ids(previous) if previous is not None else {tid: set() for tid in IDS}
    if any(not old[tid].issubset(new[tid]) for tid in IDS):
        raise EvidenceHeld("PRIORITY_PREVIOUS_INBOUND_DROPPED")
    return sum(len(new[tid] - old[tid]) for tid in IDS)
