"""Relationship-first heat-pump decision receipts in the ORIGINAL buyer-team cycle.

Consumes a verified seven-thread snapshot; safely migrates the prior four. A header
candidate is a HUMAN REVIEW task, not a buying signal, CRM admission or deal.
No new sender, OAuth access, scheduler, money or customer-data write.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import stat
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from empire_os.workspace_heat_pump_reply_tracking import (
    ANCHORS, LEGACY_ANCHORS, SCHEMA as SOURCE_SCHEMA,
)
from empire_os.workspace_solar_reply_tracking import HEX
from scripts.reconcile_buyer_email_relationships import atomic_private_write

SCHEMA = "empire.heat_pump_relationship_lifecycle.v1"
SOURCE = Path("runtime/buyer_network_intelligence/workspace_heat_pump_reply_review_latest.json")
OUTPUT = Path("runtime/buyer_network_intelligence/heat_pump_relationship_review_latest.json")
UK = ZoneInfo("Europe/London")
MAX_AGE_SECONDS = 30 * 60
BUSINESS_DAYS_BEFORE_VALUE_REVIEW = 5
EXPECTED = {tid: (name, anchor) for name, tid, anchor in ANCHORS}
LEGACY_EXPECTED = {tid: (name, anchor) for name, tid, anchor in LEGACY_ANCHORS}


class RelationshipHold(ValueError):
    pass


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise RelationshipHold("RELATIONSHIP_TIME_INVALID")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RelationshipHold("RELATIONSHIP_TIME_INVALID") from exc
    if timestamp.utcoffset() is None:
        raise RelationshipHold("RELATIONSHIP_TIME_UNAWARE")
    return timestamp.astimezone(timezone.utc)


def _business_review_date(sent_at: datetime) -> str:
    day = sent_at.astimezone(UK).date()
    count = 0
    while count < BUSINESS_DAYS_BEFORE_VALUE_REVIEW:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return day.isoformat()


def _snapshot(snapshot: Mapping[str, Any], now: datetime) -> dict[str, dict]:
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("schema_version") != SOURCE_SCHEMA
            or snapshot.get("status") != "HEAT_PUMP_WORKSPACE_THREADS_REVIEW_ONLY"
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"
            or snapshot.get("monitored_threads") != len(EXPECTED)
            or snapshot.get("verified_original_sends") != len(EXPECTED)
            or snapshot.get("outbound_sent") is not False
            or snapshot.get("database_writes") is not False
            or snapshot.get("automatic_reply_authorized") is not False
            or snapshot.get("commercial_buyer_acceptance_verified") is not False
            or snapshot.get("economic_memory_authorized") is not False
            or snapshot.get("payment_reconciled") is not False
            or snapshot.get("mailbox_full_coverage_verified") is not False):
        raise RelationshipHold("HEAT_PUMP_SOURCE_AUTHORITY_OR_COVERAGE_INVALID")
    age = (now - _time(snapshot.get("scanned_at"))).total_seconds()
    if not -60 <= age <= MAX_AGE_SECONDS:
        raise RelationshipHold("HEAT_PUMP_SOURCE_STALE_OR_FUTURE")
    rows = snapshot.get("threads")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED):
        raise RelationshipHold("HEAT_PUMP_RELATIONSHIP_ROWS_INCOMPLETE")
    mapped = {}
    all_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise RelationshipHold("HEAT_PUMP_RELATIONSHIP_ROW_INVALID")
        tid = row.get("gmail_thread_id")
        expected = EXPECTED.get(tid)
        if (expected is None or tid in mapped
                or row.get("company") != expected[0]
                or row.get("original_sent_message_id") != expected[1]
                or row.get("original_sent_verified") is not True
                or any(row.get(flag) is not False for flag in (
                    "buyer_terms_verified", "buyer_acceptance_verified",
                    "payable_capacity_verified", "crm_promotion_authorized"))):
            raise RelationshipHold("HEAT_PUMP_RELATIONSHIP_ANCHOR_OR_AUTHORITY_DRIFT")
        sent = _time(row.get("sent_at"))
        if sent > now + timedelta(seconds=60):
            raise RelationshipHold("HEAT_PUMP_SENT_AT_IN_FUTURE")
        candidates = row.get("inbound_header_candidates")
        if not isinstance(candidates, list) or len(candidates) > 20:
            raise RelationshipHold("HEAT_PUMP_RELATIONSHIP_CANDIDATES_INVALID")
        seen = set()
        for entry in candidates:
            if (not isinstance(entry, Mapping)
                    or entry.get("status") != "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED"
                    or entry.get("sender_correspondence") not in (
                        "EXACT_ORIGINAL_RECIPIENT", "SAME_DOMAIN_DIFFERENT_ADDRESS")
                    or entry.get("rfc_parent_relation") not in (
                        "NOT_PROVEN", "DIRECT_PARENT_MATCH",
                        "ORIGINAL_MESSAGE_REFERENCED_ONLY")):
                raise RelationshipHold("HEAT_PUMP_INBOUND_CANDIDATE_NOT_AUTHENTICATED")
            mid = entry.get("gmail_message_id")
            if not isinstance(mid, str) or not HEX.fullmatch(mid) or mid in seen:
                raise RelationshipHold("HEAT_PUMP_INBOUND_CANDIDATE_DUPLICATED")
            occurred = _time(entry.get("received_at"))
            if occurred <= sent or occurred > now + timedelta(seconds=60):
                raise RelationshipHold("HEAT_PUMP_INBOUND_CANDIDATE_TIME_INVALID")
            seen.add(mid)
        mapped[tid] = {"company": expected[0], "sent": sent, "inbound_ids": seen,
                       "correspondence": {x["gmail_message_id"]: x["sender_correspondence"]
                                          for x in candidates}}
        all_count += len(candidates)
    if set(mapped) != set(EXPECTED) or all_count != snapshot.get("inbound_header_candidate_count"):
        raise RelationshipHold("HEAT_PUMP_RELATIONSHIP_CENSUS_INVALID")
    return mapped


def review(snapshot: Mapping[str, Any], previous: Mapping[str, Any] | None,
           *, now: datetime) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise RelationshipHold("AWARE_RELATIONSHIP_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    current = _snapshot(snapshot, now)
    prior_seen = {tid: set() for tid in EXPECTED}
    prior_value_due = set()
    if previous is not None:
        if (not isinstance(previous, Mapping)
                or previous.get("schema_version") != SCHEMA
                or previous.get("status") != "RELATIONSHIP_REVIEW_EVIDENCE_ONLY"
                or previous.get("outbound_authorized") is not False
                or previous.get("crm_promotion_authorized") is not False
                or previous.get("buyer_acceptance_verified") is not False):
            raise RelationshipHold("RELATIONSHIP_PREVIOUS_STATE_INVALID")
        ids = previous.get("seen_inbound_message_ids")
        nudged = previous.get("value_review_already_surfaced")
        if (not isinstance(ids, dict)
                or set(ids) not in (set(LEGACY_EXPECTED), set(EXPECTED))
                or not isinstance(nudged, list) or len(nudged) != len(set(nudged))
                or not set(nudged).issubset(ids)):
            raise RelationshipHold("RELATIONSHIP_PREVIOUS_CENSUS_INVALID")
        for tid, old in ids.items():
            if (not isinstance(old, list) or len(old) > 20
                    or len(old) != len(set(old))
                    or any(not isinstance(x, str) or not HEX.fullmatch(x) for x in old)):
                raise RelationshipHold("RELATIONSHIP_PREVIOUS_IDS_UNSAFE")
            prior_seen[tid] = set(old)
        prior_value_due = set(nudged)
    if any(not prior_seen[tid].issubset(current[tid]["inbound_ids"]) for tid in EXPECTED):
        raise RelationshipHold("RELATIONSHIP_INBOUND_HISTORY_DROPPED")
    rows = []
    emitted = 0
    for name, tid, anchor in ANCHORS:
        row = current[tid]
        new = sorted(row["inbound_ids"] - prior_seen[tid])
        due = _business_review_date(row["sent"])
        has_reply = bool(row["inbound_ids"])
        if new:
            action = "REVIEW_NEW_PARTNER_REPLY_FOR_NEEDS_AND_BUYING_SIGNAL"
            emitted += 1
        elif has_reply:
            action = "AWAIT_FOUNDER_REVIEW_NO_REPEAT"
        elif now.astimezone(UK).date().isoformat() >= due and tid not in prior_value_due:
            action = "CONSIDER_VALUE_FIRST_CHECK_IN_NO_SALES_CTA"
            emitted += 1
            prior_value_due.add(tid)
        else:
            action = "WAIT_FOR_RELATIONSHIP_REPLY_NO_REPEAT"
        rows.append({
            "company": name, "gmail_thread_id": tid,
            "original_sent_message_id": anchor,
            "relationship_phase": "INBOUND_NEEDS_REVIEW" if has_reply else "WAITING_FOR_RESPONSE",
            "review_action": action,
            "founder_review_newly_due": bool(new) or action == "CONSIDER_VALUE_FIRST_CHECK_IN_NO_SALES_CTA",
            "new_header_candidates_for_review": new,
            "inbound_header_candidate_count": len(row["inbound_ids"]),
            "value_check_in_not_before_uk_date": due,
            "buying_signal_verified": False,
            "buyer_terms_verified": False,
            "crm_promotion_authorized": False,
            "outbound_authorized": False,
            "sales_cta_authorized": False,
            "suppression_and_consent_recheck_required_before_any_future_send": True,
        })
    return {
        "schema_version": SCHEMA, "status": "RELATIONSHIP_REVIEW_EVIDENCE_ONLY",
        "mode": "OBSERVE", "generated_at": now.isoformat(),
        "source_scanned_at": snapshot["scanned_at"],
        "sent_partner_relationships": len(rows),
        "inbound_header_candidates": sum(r["inbound_header_candidate_count"] for r in rows),
        "newly_due_founder_reviews": emitted,
        "relationships": rows,
        "seen_inbound_message_ids": {tid: sorted(current[tid]["inbound_ids"]) for tid in EXPECTED},
        "value_review_already_surfaced": sorted(prior_value_due),
        "crm_promotion_authorized": False, "buyer_acceptance_verified": False,
        "buying_signal_verified": False, "outbound_authorized": False,
        "payment_authorized": False, "database_writes": False,
        "automatic_email_authorized": False, "execution_authority": "none",
    }


def _private_read(path: Path, *, allow_absent: bool) -> dict | None:
    if allow_absent and not path.exists() and not path.is_symlink():
        return None
    if (path.is_symlink() or not path.is_file()
            or not 20 < path.stat().st_size <= 50_000
            or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise RelationshipHold("PRIVATE_RELATIONSHIP_EVIDENCE_UNSAFE")
    return json.loads(path.read_text(encoding="utf-8"))


def run_existing_buyer_team_review(root: Path, *, now: datetime | None = None) -> dict:
    """Executed only by the original Buyer Acquisition five-minute process."""
    try:
        if not isinstance(root, Path) or root.is_symlink():
            raise RelationshipHold("ORIGINAL_BUYER_TEAM_ROOT_REQUIRED")
        clock = now or datetime.now(timezone.utc)
        source = _private_read(root / SOURCE, allow_absent=False)
        previous = _private_read(root / OUTPUT, allow_absent=True)
        decision = review(source, previous, now=clock)
        atomic_private_write(root / OUTPUT, decision)
        return {"status": decision["status"],
                "sent_partner_relationships": decision["sent_partner_relationships"],
                "inbound_header_candidates": decision["inbound_header_candidates"],
                "newly_due_founder_reviews": decision["newly_due_founder_reviews"],
                "automatic_email_authorized": False,
                "outbound_authorized": False, "database_writes": False}
    except (RelationshipHold, OSError, json.JSONDecodeError, TypeError, KeyError, ValueError):
        return {"status": "HELD_RELATIONSHIP_EVIDENCE_UNAVAILABLE",
                "automatic_email_authorized": False,
                "outbound_authorized": False, "database_writes": False}
