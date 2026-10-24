"""Offline, PII-free adapter for ORIGINAL authorised buyer Gmail metadata index.

Reads no files and creates no persistent identity store. All original mail
metadata remains with Buyer Acquisition. Caller supplies already-permitted
private snapshots and a freshly generated, ephemeral, scoped HMAC key.
No provider/contact/tenant authentication, source rights or replay protection
is established by this adapter. Not a buyer-intent/paid-order classifier.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import re
from typing import Any

from empire_os.prime_buyer_partner_signal_shadow import (
    TAXONOMY, founder_partner_signal_status, review_partner_signal_codes,
)
from empire_os.buyer_mail_semantics import EVENT_CODES

SCHEMA = "empire.prime.original_gmail_partner_semantic_index_shadow.v1"
SOURCE_SCHEMA = "empire.buyer_mail_relationship_summary.v1"
INDEX_SCHEMA = "empire.buyer_gmail_original_message_index.v1"
ORIGIN = "connected_gmail_connector_read_only"
SOURCES = frozenset({ORIGIN, "empire_gmail_api_readonly"})
SCOPE = "reviewed_existing_warm_partner_threads"
NO_BODIES = "remain_in_gmail_not_copied_to_server"
MAX_THREADS = 24
MAX_ORIGINAL_ROWS = 500
MAX_MESSAGES = 80
MAX_AGE = timedelta(hours=3)
UTC_WALL = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$")
HEXID = re.compile(r"^[a-f0-9]{16,32}$")


class PrimeIndexHold(ValueError):
    """Original owner index cannot be independently promoted to a buyer."""


def _utc(value: Any) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise PrimeIndexHold("original_owner_aware_timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise PrimeIndexHold("invalid_original_owner_timestamp") from None
    if parsed.utcoffset() is None:
        raise PrimeIndexHold("original_owner_timezone_required")
    return parsed.astimezone(timezone.utc)


def _utc_gmail_wall_clock(value: Any) -> str:
    """Original poll_buyer_gmail_readonly.py stores UTC naive second resolution."""
    if type(value) is not str or UTC_WALL.fullmatch(value) is None:
        raise PrimeIndexHold("original_gmail_UTC_wall_clock_contract_required")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise PrimeIndexHold("invalid_original_gmail_message_clock") from None
    return value + "+00:00"


def _id(value: Any) -> str:
    if type(value) is not str or HEXID.fullmatch(value) is None:
        raise PrimeIndexHold("bounded_original_provider_id_required")
    return value


def _index_link(
    original: Mapping[str, Any], index: Mapping[str, Any], *,
    known_threads: Mapping[str, str],
) -> tuple[list[Mapping[str, Any]], dict[str, str]]:
    if (type(original) is not dict
        or original.get("schema_version") != SOURCE_SCHEMA
        or original.get("origin") != ORIGIN
        or type(original.get("threads")) is not list
        or len(original["threads"]) > MAX_ORIGINAL_ROWS
        or type(index) is not dict
        or index.get("schema_version") != INDEX_SCHEMA
        or index.get("source") not in SOURCES
        or index.get("scope") != SCOPE
        or index.get("original_message_bodies") != NO_BODIES):
        raise PrimeIndexHold("original_protected_buyer_metadata_contract_required")
    rows = index.get("threads")
    if (type(rows) is not list or not 1 <= len(rows) <= MAX_THREADS
        or type(known_threads) is not dict or not 1 <= len(known_threads) <= MAX_THREADS):
        raise PrimeIndexHold("bounded_original_owner_thread_index_required")
    allowed = dict(known_threads)
    verified_labels = {}
    seen_original = set()
    for row in original["threads"]:
        if type(row) is not dict:
            raise PrimeIndexHold("malformed_original_owner_relationship")
        tid = row.get("gmail_thread_id")
        if tid in allowed or row.get("automatic_discovery_link") is True:
            tid = _id(tid)
            if tid in seen_original:
                raise PrimeIndexHold("duplicate_original_owner_relationship")
            seen_original.add(tid)
            entity = row.get("entity_key")
            if type(entity) is not str or not 1 <= len(entity) <= 150:
                raise PrimeIndexHold("original_owner_relationship_entity_missing")
            if tid in allowed:
                if allowed[tid] != entity:
                    raise PrimeIndexHold("original_owner_thread_entity_conflict")
            elif row.get("automatic_discovery_link") is True:
                allowed[tid] = entity
            name = row.get("company")
            if type(name) is not str or not 1 <= len(name) <= 192:
                raise PrimeIndexHold("original_owner_thread_label_missing")
            verified_labels[tid] = name
    if set(allowed) != set(verified_labels) or len(rows) != len(allowed):
        raise PrimeIndexHold("incomplete_original_owner_known_thread_join")
    return rows, verified_labels


def review_original_partner_index(
    *,
    original: Mapping[str, Any],
    index: Mapping[str, Any],
    known_threads: Mapping[str, str],
    as_of: datetime,
    ephemeral_hmac_key: bytes,
) -> dict[str, Any]:
    """Aggregate real original owner metadata while refusing commercial proof.

    This is a *read-only structural reconciliation* of private local records,
    not authenticated provider evidence. No raw message/body is returned.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise PrimeIndexHold("trusted_review_clock_required")
    if type(ephemeral_hmac_key) is not bytes or len(ephemeral_hmac_key) != 32:
        raise PrimeIndexHold("fresh_ephemeral_private_review_key_required")
    if frozenset(TAXONOMY) != EVENT_CODES:
        raise PrimeIndexHold("original_owner_code_vocabulary_changed")
    now = as_of.astimezone(timezone.utc)
    collected = _utc(index.get("collected_at")) if isinstance(index, Mapping) else None
    age = now - collected if collected is not None else timedelta.max
    if age < -timedelta(minutes=5) or age > MAX_AGE:
        raise PrimeIndexHold("original_owner_snapshot_not_fresh")
    rows, labels = _index_link(original, index, known_threads=known_threads)
    seen_threads = set()
    seen_messages = set()
    observations = []
    inbound = outbound = 0
    for thread in rows:
        if type(thread) is not dict or thread.get("truncated") is not False:
            raise PrimeIndexHold("original_owner_complete_thread_required")
        tid = _id(thread.get("thread_id"))
        if tid not in labels or tid in seen_threads or thread.get("partner") != labels[tid]:
            raise PrimeIndexHold("original_owner_thread_link_conflict")
        seen_threads.add(tid)
        messages = thread.get("messages")
        if (type(messages) is not list or not 1 <= len(messages) <= MAX_MESSAGES
            or thread.get("message_count") != len(messages)):
            raise PrimeIndexHold("original_owner_thread_message_integrity_required")
        for row in messages:
            if type(row) is not dict:
                raise PrimeIndexHold("malformed_original_owner_message")
            msg = _id(row.get("id"))
            if msg in seen_messages:
                raise PrimeIndexHold("duplicate_original_provider_message")
            seen_messages.add(msg)
            codes = row.get("recognized_codes", [])
            if (type(codes) is not list or len(codes) > len(TAXONOMY)
                or any(type(code) is not str or code not in EVENT_CODES for code in codes)
                or len(codes) != len(set(codes))):
                raise PrimeIndexHold("untrusted_original_owner_semantic_codes")
            if not codes:
                continue
            flags = row.get("labels")
            if (type(flags) is not list
                or any(type(flag) is not str for flag in flags)
                or any(flag in flags for flag in ("DRAFT", "SPAM", "TRASH"))
                or ("SENT" in flags) == ("INBOX" in flags)):
                raise PrimeIndexHold("noncanonical_original_message_direction")
            direction = "outbound" if "SENT" in flags else "inbound"
            observed = _utc_gmail_wall_clock(row.get("date"))
            fingerprint = hmac.new(
                ephemeral_hmac_key,
                b"empire-prime-temporary-partner-message-v1:" +
                tid.encode("ascii") + b"\x00" + msg.encode("ascii"),
                sha256,
            ).hexdigest()
            for code in codes:
                if TAXONOMY[code][1] != direction:
                    raise PrimeIndexHold("original_owner_code_direction_conflict")
                observations.append({
                    "event_code": code,
                    "direction": direction,
                    "observed_at": observed,
                    "message_fingerprint": fingerprint,
                })
                if direction == "inbound":
                    inbound += 1
                else:
                    outbound += 1
    if set(labels) != seen_threads:
        raise PrimeIndexHold("incomplete_original_known_thread_snapshot")
    internal = review_partner_signal_codes(
        source=index["source"], observations=observations, as_of=now,
    )
    founder = founder_partner_signal_status(internal)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "PRIVATE_ORIGINAL_OWNER_METADATA_SHADOW_ONLY",
        "owner_snapshot_age_minutes_floor": max(0, int(age.total_seconds() // 60)),
        "monitored_thread_count_not_verified_buyers": len(rows),
        "indexed_message_count_not_verified_buyer_replies": len(seen_messages),
        "semantic_occurrences_not_enquiries": len(observations),
        "inbound_semantic_occurrences_not_buyer_enquiries": inbound,
        "outbound_semantic_occurrences_not_buyer_enquiries": outbound,
        "founder_research_projection": founder,
        "original_provider_and_tenant_live_authenticated": False,
        "real_buyer_intent_verified": False,
        "atomic_nonce_replay_registry_verified": False,
        "original_source_rights_currently_certified": False,
        "signed_owner_receipts_admitted": False,
        "realized_revenue_cents": None,
        "source_read_only": True,
        "database_writes": False,
        "outbound_sent": False,
        "trading_executed": False,
        "execution_authority": "none",
    }
