"""Fail-closed buyer relationship registry: discovery + Gmail summary + founder holds.

Email content is untrusted evidence, never execution instructions. No SMTP,
mailbox login, DB writes, commercial approval, call routing or outbound.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping


class RelationshipEvidenceError(ValueError):
    pass


SCHEMA = "empire.buyer_mail_relationship_summary.v1"
OUTPUT_SCHEMA = "empire.commercial_relationship_registry.v1"
HEX_ID = re.compile(r"^[a-f0-9]{12,24}$")
VALID_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")
VALID_DOMAIN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
ALLOWED_HINTS = {
    "LANDING_APPROVAL_AND_ROUTE_PROOF",
    "ONBOARDING_BUYBOX",
    "REQUEST_BUYER_MARKETS",
    "WAITING_MARKET_DETAILS",
    "REQUEST_CURRENT_BUYBOX",
    "VERIFY_CONTACT_CHANNEL",
    "REVIEW_ONLY",
}
MAX_AGE_SECONDS = 96 * 3600


def when(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RelationshipEvidenceError("invalid_message_time")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RelationshipEvidenceError("invalid_message_time") from exc
    if timestamp.tzinfo is None:
        raise RelationshipEvidenceError("naive_message_time")
    return timestamp.astimezone(timezone.utc)


def ensure_source(src: Mapping[str, Any], *, now: datetime) -> bool:
    if src.get("schema_version") != SCHEMA:
        raise RelationshipEvidenceError("wrong_gmail_summary_schema")
    if src.get("origin") != "connected_gmail_connector_read_only":
        raise RelationshipEvidenceError("unsupported_gmail_summary_origin")
    if src.get("mailbox") != "flavag83@gmail.com":
        raise RelationshipEvidenceError("unexpected_gmail_mailbox")
    captured = when(src.get("captured_at"))
    if captured is None:
        raise RelationshipEvidenceError("missing_gmail_capture")
    age = (now - captured).total_seconds()
    if age < -300:
        raise RelationshipEvidenceError("future_gmail_capture")
    rows = src.get("threads")
    if not isinstance(rows, list) or len(rows) > 500:
        raise RelationshipEvidenceError("invalid_gmail_thread_count")
    return age <= MAX_AGE_SECONDS


def _str(value: Any, max_length: int = 200) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise RelationshipEvidenceError("invalid_string_value")
    return value.strip()


def _thread_row(row: Any, *, now: datetime) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RelationshipEvidenceError("invalid_thread")
    key = _str(row.get("entity_key"), 96).lower()
    if not VALID_KEY.fullmatch(key):
        raise RelationshipEvidenceError("invalid_entity_key")
    tid = _str(row.get("gmail_thread_id"), 35).lower()
    if not HEX_ID.fullmatch(tid):
        raise RelationshipEvidenceError("invalid_gmail_thread_id")
    domains = row.get("identity_domains")
    if not isinstance(domains, list) or not 1 <= len(domains) <= 8:
        raise RelationshipEvidenceError("invalid_identity_domains")
    identities = []
    for item in domains:
        domain = _str(item, 125).lower()
        if not VALID_DOMAIN.fullmatch(domain) or domain in ("gmail.com", "google.com"):
            raise RelationshipEvidenceError("invalid_identity_domain")
        identities.append(domain)
    inbound = when(row.get("last_inbound_at"))
    outbound = when(row.get("last_outbound_at"))
    for timestamp in (inbound, outbound):
        if timestamp and (timestamp - now).total_seconds() > 300:
            raise RelationshipEvidenceError("future_email_message")
    inbound_id = row.get("last_inbound_message_id")
    outbound_id = row.get("last_outbound_message_id")
    for value in (inbound_id, outbound_id):
        if value is not None and not HEX_ID.fullmatch(_str(value, 35).lower()):
            raise RelationshipEvidenceError("invalid_message_id")
    if (inbound is None) != (inbound_id is None):
        raise RelationshipEvidenceError("inbound_timestamp_id_mismatch")
    if (outbound is None) != (outbound_id is None):
        raise RelationshipEvidenceError("outbound_timestamp_id_mismatch")
    bounces = row.get("bounced_addresses", [])
    if not isinstance(bounces, list) or len(bounces) > 12:
        raise RelationshipEvidenceError("invalid_bounce_list")
    bounce_addresses = []
    for value in bounces:
        address = _str(value, 254).lower()
        if not re.fullmatch(r"[a-z0-9._+%-]+@[a-z0-9.-]+\.[a-z]{2,24}", address):
            raise RelationshipEvidenceError("invalid_bounce_address")
        bounce_addresses.append(address)
    hint = row.get("next_action_code", "REVIEW_ONLY")
    if hint not in ALLOWED_HINTS:
        raise RelationshipEvidenceError("unapproved_next_action_code")
    return {
        "entity_key": key, "company": _str(row.get("company"), 150),
        "identity_domains": sorted(set(identities)),
        "gmail_thread_id": tid,
        "last_inbound_at": inbound,
        "last_outbound_at": outbound,
        "last_inbound_message_id": inbound_id,
        "last_outbound_message_id": outbound_id,
        "bounced_addresses": sorted(set(bounce_addresses)),
        "next_action_code": hint,
    }


def reconcile(
    source: Mapping[str, Any],
    queue: Mapping[str, Any],
    qualification: Mapping[str, Any],
    *,
    now: datetime | None = None,
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise RelationshipEvidenceError("naive_now")
    now = now.astimezone(timezone.utc)
    fresh = ensure_source(source, now=now)
    candidates = queue.get("candidates")
    targets = qualification.get("targets")
    if not isinstance(candidates, list) or not isinstance(targets, list):
        raise RelationshipEvidenceError("missing_canonical_buyer_queue")
    if queue.get("candidate_count") != len(candidates) or qualification.get("shortlisted_count") != len(targets):
        raise RelationshipEvidenceError("canonical_queue_count_mismatch")

    registry: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for raw in source["threads"]:
        item = _thread_row(raw, now=now)
        key = item["entity_key"]
        for domain in item["identity_domains"]:
            if domain in aliases and aliases[domain] != key:
                raise RelationshipEvidenceError("ambiguous_company_alias")
            aliases[domain] = key
        target = registry.setdefault(key, {
            "entity_key": key, "company": item["company"],
            "identity_domains": set(),
            "gmail_thread_ids": set(), "bounced_addresses": set(),
            "last_inbound_at": None, "last_outbound_at": None,
            "last_inbound_message_id": None, "last_outbound_message_id": None,
            "next_action_codes": set(), "discovery_status": None,
            "qualification_tier": None,
            "founder_priority": 0,
        })
        target["identity_domains"].update(item["identity_domains"])
        target["gmail_thread_ids"].add(item["gmail_thread_id"])
        target["bounced_addresses"].update(item["bounced_addresses"])
        target["next_action_codes"].add(item["next_action_code"])
        for direction in ("inbound", "outbound"):
            ts = item[f"last_{direction}_at"]
            if ts and (target[f"last_{direction}_at"] is None or ts > target[f"last_{direction}_at"]):
                target[f"last_{direction}_at"] = ts
                target[f"last_{direction}_message_id"] = item[f"last_{direction}_message_id"]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        if not VALID_DOMAIN.fullmatch(domain):
            continue
        key = aliases.get(domain, domain)
        record = registry.setdefault(key, {
            "entity_key": key, "company": domain,
            "identity_domains": set(), "gmail_thread_ids": set(),
            "bounced_addresses": set(), "next_action_codes": set(),
            "last_inbound_at": None, "last_outbound_at": None,
            "last_inbound_message_id": None, "last_outbound_message_id": None,
            "discovery_status": None, "qualification_tier": None,
            "founder_priority": 0,
        })
        record["identity_domains"].add(domain)
        record["discovery_status"] = item.get("status", "WATCH")
    for item in targets:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        if not VALID_DOMAIN.fullmatch(domain):
            continue
        key = aliases.get(domain, domain)
        record = registry.get(key)
        if not record:
            continue
        record["qualification_tier"] = item.get("tier")
        score = item.get("founder_priority")
        if type(score) is int and 0 <= score <= 100:
            record["founder_priority"] = max(score, record["founder_priority"])

    old = {r.get("entity_key"): r for r in (previous or {}).get("relationships", [])
           if isinstance(r, dict)}
    result = []
    newly_received = 0
    for key, record in registry.items():
        inc = record["last_inbound_at"]
        out = record["last_outbound_at"]
        if record["qualification_tier"] in ("MANUAL_EVIDENCE_HOLD", "AUTOMATED_EVIDENCE_HOLD"):
            stage = "EVIDENCE_HOLD"
        elif record["bounced_addresses"] and not inc:
            stage = "DELIVERY_HOLD"
        elif inc and (out is None or inc > out):
            stage = "INBOUND_REVIEW_REQUIRED"
        elif inc and out and out >= inc:
            stage = "AWAITING_BUYER"
        elif out:
            stage = "CONTACTED_AWAITING_RESPONSE"
        else:
            stage = "RESEARCH_ONLY"
        new_reply = (
            fresh and inc is not None
            and key in old and record["last_inbound_message_id"] != old[key].get("last_inbound_message_id")
        )
        newly_received += bool(new_reply)
        result.append({
            "entity_key": key, "company": record["company"],
            "identity_domains": sorted(record["identity_domains"]),
            "gmail_thread_ids": sorted(record["gmail_thread_ids"]),
            "gmail_url": (
                "https://mail.google.com/mail/u/0/#all/"
                + sorted(record["gmail_thread_ids"])[0]
                if record["gmail_thread_ids"] else None
            ),
            "last_inbound_at": inc.isoformat() if inc else None,
            "last_outbound_at": out.isoformat() if out else None,
            "last_inbound_message_id": record["last_inbound_message_id"],
            "last_outbound_message_id": record["last_outbound_message_id"],
            "bounced_addresses": sorted(record["bounced_addresses"]),
            "stage": stage,
            "next_action_codes": sorted(record["next_action_codes"]),
            "new_inbound_since_last_snapshot": bool(new_reply),
            "discovery_status": record["discovery_status"],
            "qualification_tier": record["qualification_tier"],
            "founder_priority": record["founder_priority"],
            "gmail_snapshot_fresh": fresh,
            "commercial_buyer_approved": False,
            "suppression_evidence_complete": False,
            "outbound_authorized": False,
            "realised_revenue_proven": False,
        })
    rank = {"INBOUND_REVIEW_REQUIRED": 0, "AWAITING_BUYER": 1,
            "EVIDENCE_HOLD": 2, "DELIVERY_HOLD": 3,
            "CONTACTED_AWAITING_RESPONSE": 4, "RESEARCH_ONLY": 5}
    result.sort(key=lambda r: (rank[r["stage"]], -r["founder_priority"], r["company"]))
    raw = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    counts = {stage: sum(r["stage"] == stage for r in result) for stage in rank}
    return {
        "schema_version": OUTPUT_SCHEMA,
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "source_mailbox": source["mailbox"],
        "gmail_snapshot_captured_at": source["captured_at"],
        "gmail_snapshot_fresh": fresh,
        "automatic_live_gmail_ingest_configured": False,
        "gmail_source_sha256": sha256(raw).hexdigest(),
        "discovery_queue_generated_at": queue.get("generated_at"),
        "relationship_count": len(result),
        "linked_gmail_thread_count": sum(len(r["gmail_thread_ids"]) for r in result),
        "stage_counts": counts,
        "new_inbound_relationships_since_prior_snapshot": newly_received,
        "outbound_sent": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
        "relationships": result,
    }
