"""Exact heat-pump partner replies in the ORIGINAL Workspace Gmail observer.

Metadata-only, read-only and advisory: sends and potential replies are not
commercial acceptance, named buyer capacity, signed terms or earned cash.
Use the already authenticated GoogleWorkspaceMailboxProvider and existing timer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.workspace_priority_payer_reply import _sent_recipient
from empire_os.workspace_solar_reply_tracking import (
    EvidenceHeld, HEADERS, HEX, MAX_THREAD_MESSAGES,
    WORKSPACE_RECEIVE_ADDRESSES, _email_from, _headers, _labels,
    _occurred, _rfc_relation, _valid_rfc_id, _workspace_recipient_routing,
)

SCHEMA = "empire.workspace_heat_pump_reply_tracking.v1"
ANCHORS = (
    ("C12 Energy", "1a1705b1d9f33a87", "1a1706c151413097"),
    ("BB Heat Pumps", "1a16f767f6f16ef9", "1a16ff83bfe38afa"),
    ("Q Smart", "1a1702fc95adff31", "1a170522b199dcbe"),
    ("ARC Climate Solutions", "1a16e06a516278e7", "1a16e116c3c3d50b"),
)
EXPECTED = frozenset(a[1] for a in ANCHORS)


def review_heat_pump_threads(
    results: Mapping[str, Any], *, now: datetime
) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise EvidenceHeld("HEAT_PUMP_AWARE_CLOCK_REQUIRED")
    at = now.astimezone(timezone.utc)
    if not isinstance(results, Mapping) or set(results) != EXPECTED:
        raise EvidenceHeld("HEAT_PUMP_ANCHOR_COVERAGE_INCOMPLETE")
    reviewed = []
    for company, tid, anchor in ANCHORS:
        thread = results[tid]
        if not isinstance(thread, Mapping) or thread.get("id") != tid:
            raise EvidenceHeld("HEAT_PUMP_PROVIDER_THREAD_MISMATCH")
        messages = thread.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_THREAD_MESSAGES:
            raise EvidenceHeld("HEAT_PUMP_PROVIDER_MESSAGES_INCOMPLETE")
        ids = set()
        original_to, original_when, original_rfc = None, None, ""
        potential = []
        for message in messages:
            if not isinstance(message, Mapping):
                raise EvidenceHeld("HEAT_PUMP_PROVIDER_MESSAGE_INVALID")
            mid = message.get("id")
            if (not isinstance(mid, str) or not HEX.fullmatch(mid)
                    or mid in ids or message.get("threadId") != tid):
                raise EvidenceHeld("HEAT_PUMP_DUPLICATE_OR_WRONG_THREAD_MESSAGE")
            ids.add(mid)
            headers = _headers(message)
            sender = _email_from(headers.get("from", ""))
            when = _occurred(message, now=at)
            labels = _labels(message)
            if mid == anchor:
                if ("SENT" not in labels or
                        labels & {"DRAFT", "TRASH", "SPAM"} or
                        sender not in WORKSPACE_RECEIVE_ADDRESSES):
                    raise EvidenceHeld("HEAT_PUMP_ORIGINAL_SENT_ANCHOR_UNVERIFIED")
                original_to = _sent_recipient(headers.get("to", ""))
                original_when = when
                original_rfc = _valid_rfc_id(headers.get("message-id", ""))
                continue
            if labels & {"SENT", "DRAFT", "TRASH", "SPAM"}:
                continue
            potential.append((mid, when, sender, headers))
        if original_when is None or original_to is None:
            raise EvidenceHeld("HEAT_PUMP_ORIGINAL_SENT_ANCHOR_MISSING")
        candidates = []
        for mid, when, sender, headers in potential:
            if when <= original_when:
                raise EvidenceHeld("HEAT_PUMP_INBOUND_BEFORE_ORIGINAL_SEND")
            if (sender in WORKSPACE_RECEIVE_ADDRESSES or
                    (sender != original_to and
                     sender.split("@")[-1] != original_to.split("@")[-1])):
                continue
            if _workspace_recipient_routing(headers) != "EXPECTED_WORKSPACE_TO":
                continue
            candidates.append({
                "gmail_message_id": mid,
                "received_at": when.isoformat(),
                "rfc_parent_relation": _rfc_relation(
                    outbound_id=original_rfc, incoming=headers),
                "sender_correspondence": (
                    "EXACT_ORIGINAL_RECIPIENT" if sender == original_to
                    else "SAME_DOMAIN_DIFFERENT_ADDRESS"),
                "status": "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED",
            })
        reviewed.append({
            "company": company,
            "gmail_thread_id": tid,
            "original_sent_message_id": anchor,
            "original_sent_verified": True,
            "sent_at": original_when.isoformat(),
            "inbound_header_candidates": sorted(
                candidates, key=lambda row:
                (row["received_at"], row["gmail_message_id"])),
            "buyer_terms_verified": False,
            "buyer_acceptance_verified": False,
            "payable_capacity_verified": False,
            "crm_promotion_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "HEAT_PUMP_WORKSPACE_THREADS_REVIEW_ONLY",
        "mode": "OBSERVE",
        "scanned_at": at.isoformat(),
        "monitored_threads": len(reviewed),
        "verified_original_sends": len(reviewed),
        "inbound_header_candidate_count": sum(
            len(row["inbound_header_candidates"]) for row in reviewed),
        "threads": reviewed,
        "mailbox_full_coverage_verified": False,
        "message_bodies_or_subjects_retained": False,
        "commercial_buyer_acceptance_verified": False,
        "source_and_consent_rights_verified": False,
        "payment_reconciled": False,
        "economic_memory_authorized": False,
        "database_writes": False,
        "outbound_sent": False,
        "automatic_reply_authorized": False,
        "execution_authority": "none",
    }


def collect_heat_pump_threads(service: Any, *, now: datetime) -> dict[str, Any]:
    results = {}
    for _, tid, _ in ANCHORS:
        results[tid] = service.users().threads().get(
            userId="me", id=tid, format="metadata",
            metadataHeaders=HEADERS,
        ).execute()
    return review_heat_pump_threads(results, now=now)


def newly_observed_heat_pump_candidates(
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
) -> int:
    def candidates(snapshot: Mapping[str, Any]) -> dict[str, set[str]]:
        if (not isinstance(snapshot, Mapping)
                or snapshot.get("schema_version") != SCHEMA
                or snapshot.get("status") != "HEAT_PUMP_WORKSPACE_THREADS_REVIEW_ONLY"
                or snapshot.get("monitored_threads") != len(ANCHORS)
                or snapshot.get("verified_original_sends") != len(ANCHORS)
                or snapshot.get("outbound_sent") is not False
                or snapshot.get("database_writes") is not False):
            raise EvidenceHeld("HEAT_PUMP_PREVIOUS_SNAPSHOT_INVALID")
        rows = snapshot.get("threads")
        if not isinstance(rows, list) or len(rows) != len(ANCHORS):
            raise EvidenceHeld("HEAT_PUMP_PREVIOUS_SNAPSHOT_INCOMPLETE")
        expected = {tid: (company, anchor) for company, tid, anchor in ANCHORS}
        found = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise EvidenceHeld("HEAT_PUMP_PREVIOUS_ROW_INVALID")
            tid = row.get("gmail_thread_id")
            expected_values = expected.get(tid)
            if (expected_values is None or tid in found
                    or (row.get("company"), row.get("original_sent_message_id"))
                       != expected_values
                    or row.get("original_sent_verified") is not True):
                raise EvidenceHeld("HEAT_PUMP_PREVIOUS_ANCHOR_DRIFT")
            msgs = row.get("inbound_header_candidates")
            if not isinstance(msgs, list):
                raise EvidenceHeld("HEAT_PUMP_PREVIOUS_CANDIDATES_INVALID")
            ids = []
            for msg in msgs:
                if (not isinstance(msg, Mapping) or
                        msg.get("status") !=
                        "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED" or
                        not isinstance(msg.get("gmail_message_id"), str) or
                        not HEX.fullmatch(msg["gmail_message_id"])):
                    raise EvidenceHeld("HEAT_PUMP_PREVIOUS_CANDIDATE_INVALID")
                ids.append(msg["gmail_message_id"])
            if len(ids) != len(set(ids)):
                raise EvidenceHeld("HEAT_PUMP_PREVIOUS_CANDIDATE_DUPLICATE")
            found[tid] = set(ids)
        if set(found) != EXPECTED:
            raise EvidenceHeld("HEAT_PUMP_PREVIOUS_COVERAGE_DRIFT")
        return found

    new = candidates(current)
    old = candidates(previous) if previous is not None else {
        tid: set() for tid in EXPECTED}
    if any(not old[tid].issubset(new[tid]) for tid in EXPECTED):
        raise EvidenceHeld("HEAT_PUMP_PREVIOUS_CANDIDATE_DROPPED")
    return sum(len(new[tid] - old[tid]) for tid in EXPECTED)
