"""Fail-closed, PII-free interpretation of restricted reply-linkage aggregates.

A structural database join does not authenticate an original provider message,
identify the contact, prove tenant authority, or prove purchase intent.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Mapping


FIELDS = (
    "reply_records_observed",
    "reply_records_with_intent_pointer",
    "reply_records_matched_to_intent",
    "reply_records_matched_to_prospect",
    "reply_records_missing_intent_pointer",
    "reply_records_with_unmatched_intent",
    "reply_records_with_unmatched_prospect",
    "positive_classification_records_unverified",
)


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def assess_reply_lineage(
    market: Mapping[str, Any],
    now: datetime,
    *,
    max_age_hours: int = 3,
) -> dict[str, Any]:
    """Assess only source metadata and aggregate counts; no commercial scores."""
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    now = now.astimezone(timezone.utc)
    base: dict[str, Any] = {
        "status": "PENDING_RESTRICTED_LINEAGE_SNAPSHOT",
        "reason_codes": [],
        "source": "market_gps_restricted_reply_lineage",
        "structural_joins_are_not_authenticated_buyers": True,
        "original_provider_identity_verified": False,
        "canonical_contact_identity_verified": False,
        "tenant_authority_verified": False,
        "buyer_intent_verified": False,
        "commercial_demand_verified": False,
        "execution_authority": "none",
    }
    body = market.get("restricted_reply_lineage")
    if not isinstance(body, Mapping):
        base["reason_codes"].append("LINEAGE_AGGREGATE_NOT_YET_OBSERVED")
        return base

    stamp = _timestamp(market.get("generated_at"))
    age = (now - stamp) if stamp else None
    if age is None or age < -timedelta(minutes=5) or age > timedelta(hours=max_age_hours):
        base["status"] = "REJECTED_STALE_OR_UNDATED_AGGREGATE"
        base["reason_codes"].append("LINEAGE_AGGREGATE_NOT_CURRENT")
        return base

    if any((
        market.get("execution_authority") != "none",
        market.get("buyer_intent_inferred") is not False,
        market.get("commercial_intent_inferred") is not False,
        market.get("raw_reply_records_are_commercial_proof") is not False,
        market.get("inbound_reply_authenticity_verified") is not False,
        body.get("schema") != "empire.market_gps_restricted_reply_lineage.v1",
        body.get("execution_authority") != "none",
        body.get("read_only_aggregate") is not True,
        body.get("buyer_intent_verified") is not False,
        body.get("tenant_binding_verified") is not False,
        body.get("original_provider_message_id_checked") is not False,
        body.get("canonical_contact_identity_verified") is not False,
        body.get("provider_thread_binding_verified") is not False,
        body.get("commercial_demand_inferred") is not False,
        type(body.get("window_days")) is not int,
        not 1 <= body.get("window_days", -1) <= 90
        if type(body.get("window_days")) is int else True,
    )):
        base["status"] = "REJECTED_UNTRUSTED_AGGREGATE_CONTRACT"
        base["reason_codes"].append("LINEAGE_CONTRACT_UNVERIFIED")
        return base

    if any(type(body.get(f)) is not int or body[f] < 0 for f in FIELDS):
        base["status"] = "REJECTED_INVALID_AGGREGATE"
        base["reason_codes"].append("INVALID_AGGREGATE_COUNTS")
        return base

    total = body["reply_records_observed"]
    pointer = body["reply_records_with_intent_pointer"]
    intent = body["reply_records_matched_to_intent"]
    prospect = body["reply_records_matched_to_prospect"]
    positive = body["positive_classification_records_unverified"]
    if not (
        prospect <= intent <= pointer <= total
        and positive <= total
        and body["reply_records_missing_intent_pointer"] == total - pointer
        and body["reply_records_with_unmatched_intent"] == pointer - intent
        and body["reply_records_with_unmatched_prospect"] == intent - prospect
    ):
        base["status"] = "REJECTED_CONTRADICTORY_AGGREGATE"
        base["reason_codes"].append("LINEAGE_RELATIONSHIP_CONTRADICTION")
        return base

    base["status"] = "CURRENT_STRUCTURAL_COUNTS_ONLY"
    base["window_days"] = body["window_days"]
    base["counts"] = {f: body[f] for f in FIELDS}
    if not total:
        base["reason_codes"].append("NO_REPLY_ROWS_IN_OBSERVED_WINDOW")
    if total > pointer:
        base["reason_codes"].append("REPLY_ROWS_MISSING_INTENT_POINTER")
    if pointer > intent:
        base["reason_codes"].append("REPLY_INTENT_POINTER_WITH_NO_MATCH")
    if intent > prospect:
        base["reason_codes"].append("INTENT_WITH_NO_PROSPECT_MATCH")
    base["reason_codes"].extend([
        "PROVIDER_MESSAGE_AUTHENTICITY_NOT_CHECKED",
        "CANONICAL_CONTACT_IDENTITY_NOT_CHECKED",
        "TENANT_AUTHORITY_NOT_CHECKED",
    ])
    return base
