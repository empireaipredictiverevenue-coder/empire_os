"""Read-only commercial source diagnostics for Opportunity Evidence Resolver.

Never reads mailbox credentials or changes canonical messages, tenant identity,
Market GPS, Factory scores, outbound, payments or execution authority.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.reply_lineage_health import assess_reply_lineage

SOURCES = {
    "conversation_os": (
        "runtime/conversations_replies_control/latest.json",
        "runtime/conversations_replies_control/passive_reply_db_observer_latest.json",
        "runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json",
    ),
    "market_gps_and_commercial_outcomes": (
        "runtime/market_sweeps/revenue_gps_latest.json",
    ),
}
CLAIM_SOURCE = {
    "buyer_intent": "conversation_os",
    "demand": "market_gps_and_commercial_outcomes",
}


def _read(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    try:
        if not path.is_file() or path.stat().st_size > 2_000_000:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def _source_freshness(raw: Any, now: datetime, max_age_hours: int = 12) -> str:
    stamp = _time(raw)
    if stamp is None:
        return "UNDATED_OR_MISSING"
    age = now - stamp
    if age < -timedelta(minutes=5):
        return "FUTURE_DATED"
    if age > timedelta(hours=max_age_hours):
        return "STALE"
    return "CURRENT"


def assess_sources(root: Path, now: datetime | None = None) -> dict[str, Any]:
    root = root.resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("source assessment requires timezone")
    now = now.astimezone(timezone.utc)
    canonical, reply, mailbox = (
        _read(root, rel) for rel in SOURCES["conversation_os"]
    )
    collector = _read(root, "runtime/conversations_replies_control/collector_health_latest.json")
    market = _read(root, SOURCES["market_gps_and_commercial_outcomes"][0])
    lineage_health = assess_reply_lineage(market, now)
    linkage = _read(root, "runtime/conversations_replies_control/reply_linkage_plan_latest.json")

    observed_messages = canonical.get("canonical_messages")
    observed_messages = observed_messages if isinstance(observed_messages, list) else []
    quarantined = canonical.get("quarantine") or {}
    quarantined = quarantined if isinstance(quarantined, Mapping) else {}
    sample = quarantined.get("records") or []
    causes = Counter()
    if isinstance(sample, list):
        for row in sample[:500]:
            if isinstance(row, Mapping):
                causes.update(v for v in (row.get("reasons") or [])
                              if isinstance(v, str) and len(v) <= 64)
    # Hash source names the same way as Conversation OS, but report only
    # aggregate sample counts. A bounded sample is not the total population.
    summary = canonical.get("source_summary") or {}
    tables = summary.get("database_tables") or []
    source_kinds: dict[str, str] = {}
    if isinstance(tables, list):
        for table in tables[:40]:
            if not isinstance(table, str) or len(table) > 120:
                continue
            kind = (
                "OUTBOUND_EVENT_TABLE" if table.endswith(".outbound_events")
                else "REPLY_CANDIDATE" if "repl" in table.casefold()
                else "CONVERSATION_CANDIDATE" if "conversation" in table.casefold()
                else "OTHER"
            )
            source_kinds["source:" + sha256(table.encode()).hexdigest()] = kind
    sample_by_kind: Counter[str] = Counter()
    if isinstance(sample, list):
        sample_by_kind.update(
            source_kinds.get(str(row.get("source_id")), "UNKNOWN_SOURCE")
            for row in sample[:500] if isinstance(row, Mapping)
        )
    admission = canonical.get("source_admission") or {}
    admission = admission if isinstance(admission, Mapping) else {}
    admitted = admission.get("admitted_conversation_candidate_rows")
    admitted = admitted if type(admitted) is int and admitted >= 0 else None
    excluded = admission.get("excluded_nonmessage_rows")
    excluded = excluded if type(excluded) is int and excluded >= 0 else None
    if admission and (
        admission.get("admission_does_not_authenticate_buyer_intent") is not True
        or admission.get("tenant_binding_established") is not False
        or admission.get("execution_authority") != "none"
    ):
        admitted = None
        excluded = None
    quarantine_count = quarantined.get("quarantine_count")
    quarantine_count = quarantine_count if type(quarantine_count) is int else 0
    original_reply_count = reply.get("candidate_count")
    original_reply_count = (
        original_reply_count
        if type(original_reply_count) is int and original_reply_count >= 0
        else None
    )
    reply_freshness = _source_freshness(reply.get("generated_at"), now)
    canonical_freshness = _source_freshness(canonical.get("generated_at"), now)
    mailbox_freshness = _source_freshness(mailbox.get("generated_at"), now)
    reply_count = (
        original_reply_count if reply_freshness == "CURRENT" else None
    )
    mailbox_status = str(mailbox.get("status") or "UNAVAILABLE")[:45]
    conversation_reasons: list[str] = []
    collector_freshness = _source_freshness(collector.get("observed_at"), now)
    collector_status = str(collector.get("status") or "NOT_REPORTED")[:55]
    if collector_freshness != "CURRENT":
        conversation_reasons.append("CONVERSATION_COLLECTOR_HEALTH_NOT_CURRENT")
    if collector_status != "READ_SUCCESS":
        conversation_reasons.append("CONVERSATION_COLLECTOR_NOT_PROVEN_SUCCESSFUL")
    if not canonical:
        conversation_reasons.append("CANONICAL_CONVERSATION_SNAPSHOT_MISSING")
    elif canonical_freshness != "CURRENT":
        conversation_reasons.append("CANONICAL_CONVERSATION_SNAPSHOT_NOT_CURRENT")
    if reply_freshness != "CURRENT":
        conversation_reasons.append("CANONICAL_REPLY_OBSERVER_NOT_CURRENT")
    if mailbox_freshness != "CURRENT":
        conversation_reasons.append("MAILBOX_OBSERVER_NOT_CURRENT")
    if quarantine_count:
        conversation_reasons.append("CANONICAL_RECORDS_QUARANTINED")
    if not observed_messages:
        conversation_reasons.append("NO_CANONICAL_MESSAGES")
    if not reply or reply.get("status") != "CANONICAL_REPLY_ROWS_OBSERVED":
        conversation_reasons.append("CANONICAL_REPLY_OBSERVER_NOT_READY")
    if mailbox_status != "VERIFIED_RUNTIME":
        conversation_reasons.append("MAILBOX_OBSERVER_NOT_VERIFIED")
    conversation_reasons.extend(lineage_health["reason_codes"])
    # A mailbox/runtime health flag cannot attest to a specific buyer.
    # This diagnostic never declares commercial intent established.

    market_age = None
    market_time = _time(market.get("generated_at"))
    if market_time is not None:
        market_age = round((now - market_time).total_seconds() / 86400, 2)
    market_reasons: list[str] = []
    if not market:
        market_reasons.append("MARKET_GPS_SOURCE_MISSING")
    elif market_age is None:
        market_reasons.append("MARKET_GPS_UNDATED")
    elif market_age < -0.01:
        market_reasons.append("MARKET_GPS_FUTURE_DATED")
    elif market_age > 7:
        market_reasons.append("MARKET_GPS_STALE")
    count = market.get("commercial_demand_market_count")
    if type(count) is not int or count < 1:
        market_reasons.append("NO_OBSERVED_COMMERCIAL_DEMAND")
    if market.get("buyer_intent_inferred") is not False:
        market_reasons.append("MARKET_GPS_UNSAFE_INFERENCE_STATE")

    # No output below includes canonical contact/message payload or mailbox PII.
    return {
        "schema": "empire.commercial_evidence_source_health.v1",
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "sources": {
            "conversation_os": {
                "status": "BLOCKED" if conversation_reasons else "REVIEW_REQUIRED",
                "reason_codes": conversation_reasons,
                "canonical_message_count": len(observed_messages),
                "collector_status": collector_status,
                "collector_health_freshness": collector_freshness,
                "collector_source_query_completed": (
                    collector.get("source_query_completed") is True
                    if collector_freshness == "CURRENT" else False
                ),
                "canonical_snapshot_freshness": canonical_freshness,
                "quarantined_record_count": quarantine_count,
                "message_source_rows_admitted": admitted,
                "nonmessage_source_rows_excluded": excluded,
                "source_admission_does_not_prove_buyer_intent": True,
                "reply_linkage_schema_status": linkage.get("verification_status", "NOT_RESEARCHED"),
                "reply_linkage_actual_rows_proven": 0,
                "reply_linkage_structural_health": lineage_health,
                "reply_linkage_blockers": list(linkage.get("blockers") or [])[:8],
                "quarantine_sample_count": min(len(sample), 500) if isinstance(sample, list) else 0,
                "quarantine_reason_counts": dict(sorted(causes.items())),
                "quarantine_reason_counts_are_sample_based": True,
                "quarantine_sample_source_kind_counts": dict(sorted(sample_by_kind.items())),
                "quarantine_sample_is_not_population_distribution": True,
                "next_remediation": [
                    {
                        "owner_capability": "conversation_os",
                        "action": "separate_outbound_event_history_from_verified_inbound_reply_candidates",
                        "proof": "original source type and direction; retain ambiguous rows in quarantine",
                        "no_synthetic_message_or_contact_identity": True,
                    },
                    {
                        "owner_capability": "conversation_os",
                        "action": "restore_original_stable_provider_message_and_thread_ids",
                        "proof": "source-event IDs verified against immutable authenticated inbound records",
                        "no_synthetic_id": True,
                    },
                    {
                        "owner_capability": "identity_graph",
                        "action": "resolve_real_contact_and_tenant_with_canonical_identity",
                        "proof": "identity and tenant lineage; negative tests for cross-tenant joins",
                        "no_synthetic_id": True,
                    },
                    {
                        "owner_capability": "founder_mailbox",
                        "action": "restore_governed_inbound_reply_observer_after_mail_provider_verified",
                        "proof": "authenticated original inbound message and suppression checks",
                        "no_send_authority": True,
                    },
                ],
                "reply_observer_candidate_count": reply_count,
                "reply_observer_status": (
                    str(reply.get("status") or "UNAVAILABLE")[:45]
                    if reply_freshness == "CURRENT"
                    else "STALE_OBSERVER_NOT_CURRENT_TRUTH"
                ),
                "mailbox_observer_status": mailbox_status,
                "authenticated_buyer_intent_proved": False,
            },
            "market_gps_and_commercial_outcomes": {
                "status": "BLOCKED" if market_reasons else "REVIEW_REQUIRED",
                "reason_codes": market_reasons,
                "snapshot_age_days": market_age,
                "snapshot_reported_at": market.get("generated_at"),
                "market_count": market.get("market_count") if type(market.get("market_count")) is int else None,
                "reported_commercial_demand_market_count": count if type(count) is int else None,
                "reply_lineage_structural_health": lineage_health,
                "fresh_authenticated_demand_proved": False,
                "next_remediation": [
                    {
                        "owner_capability": "market_gps_and_commercial_outcomes",
                        "action": "refresh_market_gps_with_dedicated_restricted_materializer_only",
                        "proof": "dedicated role plus fresh query receipt and canonical event lineage",
                        "privileged_role_bypass_permitted": False,
                    },
                    {
                        "owner_capability": "commercial_exchange",
                        "action": "bind_qualified_inbound_orders_and_terms_to_exact_approved_buyer",
                        "proof": "buyer, tenant, geography, product and event-source identity",
                        "market_search_hits_count_as_demand": False,
                    },
                ],
            },
        },
        "canonical_tenant_binding_checked": False,
        "normalized_scores_written": 0,
        "commercial_claims_auto_verified": 0,
        "market_gps_refresh_attempted": False,
        "mailbox_read_attempted": False,
        "execution_authority": "none",
    }


def diagnostic_for_claim(health: Mapping[str, Any], claim: str) -> dict[str, Any]:
    source_key = CLAIM_SOURCE.get(claim)
    source = (health.get("sources") or {}).get(source_key) if source_key else None
    if not isinstance(source, Mapping):
        return {"source": "SOURCE_CONNECTOR_NOT_YET_MAPPED",
                "status": "UNKNOWN", "reasons": []}
    return {
        "source": source_key,
        "status": source.get("status"),
        "reasons": list(source.get("reason_codes") or []),
        "commercial_claim_verified": False,
    }
