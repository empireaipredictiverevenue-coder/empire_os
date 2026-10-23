"""Private, read-only first-sale founder pipeline: source/ledger truth and Gmail header evidence.

Never creates contacts, sends messages, infers buyer demand, or mutates EmpireDB.
Uses existing signed Google Workspace mailbox identity and original seven sent IDs.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from email.utils import getaddresses
from pathlib import Path
import re
from typing import Any, Mapping

from empire_os.workspace_solar_reply_tracking import (
    _email_from, _headers, _labels, _occurred, EvidenceHeld,
)

SOURCE = Path("research_reviews/data/VC_FUNDED_FOUNDER_OUTREACH_BATCH_16_20261023.csv")
PLENA = ("Plena Health", "eyad@plena.health", "1a168a14f07e21d8")
GMAIL_ID = re.compile(r"^[a-f0-9]{16,32}$")
EXPECTED_SENT = {
    "Alloovium": ("zander@alloovium.com", "1a168c2481483041"),
    "Libra Robotics": ("founders@librabots.com", "1a168c26bc7aa199"),
    "Acolite": ("daniel@acolite.ai", "1a168c2928a56a87"),
    "Qlo": ("founders@getqlo.com", "1a168c2b0bbfefd7"),
    "Propaya": ("founders@propaya.com", "1a168c2d096a0dfc"),
    "Andco": ("founders@useandco.com", "1a168d642aa8e0a0"),
    "LunaBill": ("founders@lunabill.com", "1a169d6472ef70f1"),
    "ProhostAI": ("bill@prohost.ai", "1a169d67e9260fe6"),
}
# Only these original 23-Oct-2026 founder-approved sends may migrate the
# immutable legacy seven-thread metadata snapshot.
NEW_TWO_GMAIL_THREAD_IDS = frozenset({
    "1a169d6472ef70f1", "1a169d67e9260fe6",
})
# Alias is verified in the existing Workspace transport, never used to choose a token.
SENDER = frozenset({"phil@empire-ai.co.uk", "phil@mail.empire-ai.co.uk"})
HEADERS = ["From", "To", "Subject", "Message-ID", "In-Reply-To", "References"]


def load_ledger(root: Path) -> dict[str, Any]:
    path = (Path(root).resolve() / SOURCE).resolve()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 180_000:
        raise EvidenceHeld("FOUNDER_PIPELINE_LEDGER_MISSING_OR_UNSAFE")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # Preserve the original 16-person universe; permit bounded append-only
    # research candidates without inheriting any prior outreach authority.
    if not 16 <= len(rows) <= 500:
        raise EvidenceHeld("FOUNDER_PIPELINE_ROW_BUDGET_EXCEEDED")
    by_name: dict[str, dict[str, str]] = {}
    domains: set[str] = set()
    for row in rows:
        name = str(row.get("company") or "")
        email = str(row.get("published_contact") or "").casefold()
        domain = email.rsplit("@", 1)[-1]
        if (not name or name in by_name or "@" not in email
                or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,24}", domain)
                or domain in domains or not str(row.get("yc_original_source") or "").startswith("https://www.ycombinator.com/companies/")):
            raise EvidenceHeld("DUPLICATE_OR_UNVERIFIED_COMPANY_LEDGER")
        domains.add(domain)
        by_name[name] = row
        if row.get("canonical_crm_suppression") != "NOT_VERIFIED":
            raise EvidenceHeld("CANONICAL_AUTHORITY_UNEXPECTEDLY_CLAIMED")
    for name, row in by_name.items():
        if name not in EXPECTED_SENT and (
            row.get("gmail_sent_message_id") or row.get("gmail_sent_thread_id")
            or row.get("outbound_approval") not in ("NONE", "")
            or row.get("email_first_draft_status") not in ("NOT_DRAFTED", "DRAFTED_UNSENT")
        ):
            raise EvidenceHeld("UNREVIEWED_CANDIDATE_CANNOT_INHERIT_APPROVAL")
    for company, (address, anchor) in EXPECTED_SENT.items():
        row = by_name.get(company)
        if (not row or row.get("published_contact") != address
                or row.get("gmail_sent_message_id") != anchor
                or row.get("gmail_sent_thread_id") != anchor
                or row.get("email_first_draft_status") != "SENT_GMAIL_READBACK"):
            raise EvidenceHeld("SENT_PROVIDER_RECEIPT_MISMATCH")
    pending = sorted(
        ({"company": name, "priority": row["priority"],
          "source": row["yc_original_source"], "status": "DRAFT_REVIEW_ONLY"}
         for name, row in by_name.items() if name not in EXPECTED_SENT),
        key=lambda x: (x["priority"], x["company"]),
    )
    if len(pending) != len(rows) - len(EXPECTED_SENT):
        raise EvidenceHeld("PENDING_COHORT_NOT_RECONCILED")
    return {"anchors": [PLENA, *( (name, addr, mid) for name, (addr, mid) in EXPECTED_SENT.items())],
            "pending": pending}


def review_threads(
    ledger: Mapping[str, Any], results: Mapping[str, Any], *,
    now: datetime, previous: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    if not now.tzinfo or now.utcoffset() is None:
        raise EvidenceHeld("TRUSTED_AWARE_TIME_REQUIRED")
    anchors = ledger["anchors"]
    if (not isinstance(results, Mapping)
            or set(results) != {row[2] for row in anchors}):
        raise EvidenceHeld("INCOMPLETE_OR_EXTRA_THREAD_COVERAGE")
    prior: dict[str, set[str]] = {}
    if previous is not None:
        if (previous.get("schema_version") != "empire.founder_acquisition_autopilot.v1"
                or previous.get("status") != "SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY"
                or not isinstance(previous.get("threads"), list)
                or len(previous["threads"]) not in (7, len(anchors))):
            raise EvidenceHeld("UNTRUSTED_PREVIOUS_EVIDENCE")
        for row in previous["threads"]:
            allowed = {mid: company for company, _, mid in anchors}
            if (row.get("sent_message_id") not in allowed
                    or row.get("company") != allowed.get(row.get("sent_message_id"))
                    or row.get("sent_anchor_verified") is not True
                    or row.get("sent_message_id") in prior):
                raise EvidenceHeld("PREVIOUS_THREAD_ANCHOR_MISMATCH")
            values = row.get("inbound_header_candidates")
            if not isinstance(values, list) or len(values) != len(set(values)):
                raise EvidenceHeld("INVALID_PREVIOUS_CANDIDATE_IDENTITIES")
            prior[row["sent_message_id"]] = set(values)
        prior_ids = set(prior)
        current_ids = set(results)
        old_seven = current_ids - NEW_TWO_GMAIL_THREAD_IDS
        if not (prior_ids == current_ids or
                (len(prior_ids) == 7 and prior_ids == old_seven
                 and len(current_ids) == 9)):
            raise EvidenceHeld("PREVIOUS_THREAD_COVERAGE_CHANGED")
    reviewed = []
    new_count = 0
    for company, address, tid in anchors:
        result = results[tid]
        messages = result.get("messages")
        if (result.get("id") != tid or not isinstance(messages, list)
                or not 1 <= len(messages) <= 80):
            raise EvidenceHeld("INCOMPLETE_OR_INVALID_GMAIL_THREAD")
        anchor_when = None
        candidates = []
        seen = set()
        for msg in messages:
            mid = msg.get("id")
            if (not isinstance(mid, str) or not GMAIL_ID.fullmatch(mid)
                    or mid in seen or msg.get("threadId") != tid):
                raise EvidenceHeld("UNTRUSTED_GMAIL_MESSAGE_ID")
            seen.add(mid)
            headers = _headers(msg)
            sender = _email_from(headers.get("from", ""))
            labels = _labels(msg)
            occurred = _occurred(msg, now=now)
            if mid == tid:
                try:
                    recipients = [_email_from(email) for _, email in getaddresses([headers.get("to", "")], strict=True)]
                except (ValueError, TypeError):
                    raise EvidenceHeld("UNTRUSTED_SENT_RECIPIENT") from None
                if (not 1 <= len(recipients) <= 12 or address not in recipients
                        or sender not in SENDER or "SENT" not in labels
                        or "DRAFT" in labels):
                    raise EvidenceHeld("SENT_ANCHOR_NOT_PROVEN")
                anchor_when = occurred
            elif "SENT" not in labels and "TRASH" not in labels and "SPAM" not in labels and "DRAFT" not in labels:
                # Potential genuine replies from exact original contact or same
                # organisation: inspect manually, never automatically reply.
                if sender == address or sender.rsplit("@", 1)[-1] == address.rsplit("@", 1)[-1]:
                    candidates.append((mid, occurred))
        if anchor_when is None or any(when <= anchor_when for _, when in candidates):
            raise EvidenceHeld("INBOUND_ANCHOR_CHRONOLOGY_FAILED")
        ids = sorted(mid for mid, _ in candidates)
        old = prior.get(tid, set())
        if not old.issubset(ids):
            raise EvidenceHeld("PREVIOUS_REPLIES_DISAPPEARED")
        new_count += len(set(ids) - old)
        reviewed.append({
            "company": company, "sent_message_id": tid,
            "sent_anchor_verified": True, "inbound_header_candidates": ids,
            "buyer_intent_verified": False, "reply_body_verified": False,
        })
    return {
        "schema_version": "empire.founder_acquisition_autopilot.v1",
        "status": "SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY",
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "mode": "OBSERVE", "monitored_threads": len(reviewed),
        "sent_anchors_verified": len(reviewed),
        "inbound_header_candidate_count": sum(len(x["inbound_header_candidates"]) for x in reviewed),
        "new_inbound_header_candidates": new_count,
        "threads": reviewed,
        "next_unsent_review": ledger["pending"],
        "canonical_suppression_verified": False,
        "crm_writes": False, "outbound_sent": False,
        "automatic_reply_authorized": False,
        "paid_pilot_authorized": False, "revenue_verified": False,
        "personal_data_retained": False, "execution_authority": "none",
    }


def collect(service: Any, ledger: Mapping[str, Any], *, now: datetime,
            previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
    results = {}
    for _, _, tid in ledger["anchors"]:
        results[tid] = service.users().threads().get(
            userId="me", id=tid, format="metadata", metadataHeaders=HEADERS
        ).execute()
    return review_threads(ledger, results, now=now, previous=previous)
