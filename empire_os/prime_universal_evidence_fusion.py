"""PRIME universal evidence FUSION, original Predictive Cloud, OBSERVE only.

Input is privacy-minimised, owner-prepared receipt metadata, NOT raw source
material. Caller MUST already be an authorised original source reader; this
pure deterministic function cannot authenticate that reader, provider rights,
tenant membership, trades, enquiries, orders or terminal financial outcomes.
No DB, network, dispatch, training, buyer contact or trading imports.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any

SCHEMA = "empire.prime.universal_evidence_fusion.v1"
RECEIPT_SCHEMA = "empire.prime.original_owner_evidence_summary.v1"
MAX_RECEIPTS = 100
MAX_LINKS = 16
# Existing organisational owners; this does not register new agents/readers.
OWNER_CLASSES = {
    "buyer_acquisition": {"GENERAL_INTEREST", "EXPLICIT_ENQUIRY"},
    "smart_crm": {"GENERAL_INTEREST", "EXPLICIT_ENQUIRY", "COMMITMENT"},
    "search_intelligence": {"GENERAL_INTEREST"},
    "media_os": {"GENERAL_INTEREST"},
    "permits": {"ACTIVITY"},
    "storm": {"ACTIVITY"},
    "legal": {"ACTIVITY"},
    "procurement": {"ACTIVITY"},
    "property_insurance": {"ACTIVITY"},
    "trading_quant": {"TRADING_RESEARCH"},
    "economic_memory": {"REALIZED_OUTCOME"},
}
CLASS_LEVEL = {
    "GENERAL_INTEREST": 1,
    "ACTIVITY": 2,
    "EXPLICIT_ENQUIRY": 3,
    "COMMITMENT": 4,
    "REALIZED_OUTCOME": 5,
    "TRADING_RESEARCH": None,
}
# Conservative reviewer freshness, not provider SLAs or licensing rules.
MAX_AGE = {
    "storm": timedelta(hours=6),
    "trading_quant": timedelta(minutes=1),
    "search_intelligence": timedelta(days=7),
    "media_os": timedelta(days=7),
    "buyer_acquisition": timedelta(days=30),
    "smart_crm": timedelta(days=30),
    "permits": timedelta(days=30),
    "legal": timedelta(days=30),
    "procurement": timedelta(days=7),
    "property_insurance": timedelta(days=30),
    "economic_memory": timedelta(days=365),
}
EXACT_FIELDS = frozenset({
    "schema_version", "owner", "evidence_class",
    "event_sha256", "origin_sha256", "entity_sha256",
    "source_sha256", "tenant_scope_sha256", "tenant_binding_sha256",
    "observed_at", "received_at", "provenance_status",
    "source_rights_status", "permitted_purpose",
    "supports_sha256", "contradicts_sha256", "prediction_as_of",
    "execution_authority",
})
SAFE_AUTHORITY = "none"
APPROVED_PURPOSE = "PRIVATE_PREDICTIVE_RESEARCH_ONLY"


class PrimeFusionHold(ValueError):
    """The owner-prepared evidence cannot safely cross the PRIME boundary."""


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _hashref(value: Any, field: str) -> str:
    if not (type(value) is str and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)):
        raise PrimeFusionHold(field + "_requires_sha256_hex")
    return value


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise PrimeFusionHold(field + "_aware_UTC_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise PrimeFusionHold(field + "_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PrimeFusionHold(field + "_UTC_required")
    return parsed.astimezone(timezone.utc)


def _links(value: Any, field: str) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or len(value) > MAX_LINKS:
        raise PrimeFusionHold(field + "_bounded_list_required")
    items = tuple(_hashref(x, field) for x in value)
    if len(items) != len(set(items)):
        raise PrimeFusionHold(field + "_duplicates_refused")
    return items


def _validated(
    row: Mapping[str, Any], *, tenant_digest: str, as_of: datetime,
) -> dict[str, Any]:
    if type(row) is not dict or set(row) != EXACT_FIELDS:
        raise PrimeFusionHold("exact_private_owner_summary_fields_required")
    if row["schema_version"] != RECEIPT_SCHEMA:
        raise PrimeFusionHold("wrong_original_owner_receipt_schema")
    owner = row["owner"]
    if type(owner) is not str or owner not in OWNER_CLASSES:
        raise PrimeFusionHold("unsupported_original_department_owner")
    classification = row["evidence_class"]
    if type(classification) is not str or classification not in OWNER_CLASSES[owner]:
        raise PrimeFusionHold("unsupported_owner_evidence_class_promotion")
    if row["execution_authority"] != SAFE_AUTHORITY:
        raise PrimeFusionHold("financial_or_external_authority_refused")
    if row["permitted_purpose"] != APPROVED_PURPOSE:
        raise PrimeFusionHold("cross_purpose_use_not_permitted")
    if row["source_rights_status"] != "OWNER_REVIEWED_PERMITTED":
        raise PrimeFusionHold("source_usage_rights_not_cleared")
    if row["provenance_status"] != "ORIGINAL_OWNER_CUSTODY_REVIEWED":
        raise PrimeFusionHold("source_provenance_not_owner_reviewed")
    if _hashref(row["tenant_scope_sha256"], "tenant_scope") != tenant_digest:
        raise PrimeFusionHold("cross_tenant_evidence_rejected")
    for field in ("event_sha256", "origin_sha256", "entity_sha256",
                  "source_sha256", "tenant_binding_sha256"):
        _hashref(row[field], field)
    observed = _time(row["observed_at"], "observed_at")
    received = _time(row["received_at"], "received_at")
    if observed > received or received > as_of:
        raise PrimeFusionHold("future_or_noncausal_receipt_clock")
    if as_of - received > MAX_AGE[owner]:
        raise PrimeFusionHold("stale_original_owner_observation")
    prediction_as_of = row["prediction_as_of"]
    if prediction_as_of is not None:
        predicted = _time(prediction_as_of, "prediction_as_of")
        if classification == "REALIZED_OUTCOME":
            raise PrimeFusionHold("financial_outcome_not_a_prediction_feature")
        if predicted < received or predicted > as_of:
            raise PrimeFusionHold("prediction_foreknowledge_or_future_time")
    support = _links(row["supports_sha256"], "supports")
    contradict = _links(row["contradicts_sha256"], "contradicts")
    if set(support) & set(contradict):
        raise PrimeFusionHold("support_and_contradiction_overlap")
    if row["event_sha256"] in set(support) | set(contradict):
        raise PrimeFusionHold("self_corroboration_refused")
    return dict(row)


def review_prime_universal_evidence(
    *, tenant_id: str, as_of: datetime,
    original_owner_summaries: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Shadow cross-domain research; never claims genuine calibrated accuracy.

    Hashes protect public review outputs from raw identifiers, but do NOT
    authenticate data: fields like OWNER_REVIEWED_PERMITTED are assertions from
    the source owner and require independent access/control evidence upstream.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise PrimeFusionHold("tenant_expected_from_authenticated_caller")
    if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise PrimeFusionHold("aware_as_of_required")
    now = as_of.astimezone(timezone.utc)
    if original_owner_summaries is not None and (
        type(original_owner_summaries) not in (list, tuple)
        or len(original_owner_summaries) > MAX_RECEIPTS
    ):
        raise PrimeFusionHold("bounded_original_owner_summary_sequence_required")

    accepted: dict[str, dict[str, Any]] = {}
    rejected = Counter()
    conflicted = set()
    tenant_digest = _digest(tenant_id)
    for row in original_owner_summaries or ():
        try:
            item = _validated(row, tenant_digest=tenant_digest, as_of=now)
        except PrimeFusionHold as exc:
            rejected[str(exc)] += 1
            continue
        identity = item["event_sha256"]
        previous = accepted.get(identity)
        if previous is None:
            accepted[identity] = item
        elif previous != item:
            conflicted.add(identity)
    for key in conflicted:
        accepted.pop(key, None)

    # Conflicting revisions, including duplicates after the first conflict,
    # must never silently re-enter the accepted cohort.
    accepted = {k: v for k, v in accepted.items() if k not in conflicted}

    records = tuple(accepted[k] for k in sorted(accepted))
    contradictory = set()
    unresolved_links = 0
    invalid_cross_entity_links = 0
    corroborating_links: dict[str, set[tuple[str, str]]] = defaultdict(set)
    contradiction_links: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in records:
        for key in row["supports_sha256"] + row["contradicts_sha256"]:
            other = accepted.get(key)
            if other is None:
                unresolved_links += 1
                continue
            if (other["entity_sha256"] != row["entity_sha256"]
                or other["tenant_scope_sha256"] != row["tenant_scope_sha256"]):
                invalid_cross_entity_links += 1
                contradictory.add(row["entity_sha256"])
                continue
            if key in row["contradicts_sha256"]:
                contradictory.add(row["entity_sha256"])
                contradiction_links[row["entity_sha256"]].add(tuple(sorted((
                    row["event_sha256"], key,
                ))))
            elif other["origin_sha256"] != row["origin_sha256"]:
                corroborating_links[row["entity_sha256"]].add(tuple(sorted((
                    row["origin_sha256"], other["origin_sha256"],
                ))))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[row["entity_sha256"]].append(row)

    # Never surface raw or hashed tenant/entity/source/event identifiers in a
    # Founder status payload. Per-group aliases are local ordinals only.
    reviews = []
    for index, entity_key in enumerate(sorted(grouped), start=1):
        entries = grouped[entity_key]
        origins = {x["origin_sha256"] for x in entries}
        categories = sorted({x["evidence_class"] for x in entries})
        owners = sorted({x["owner"] for x in entries})
        contradiction = entity_key in contradictory
        max_level = max(
            (CLASS_LEVEL[x["evidence_class"]] or 0) for x in entries
        )
        reviews.append({
            "local_group": index,
            "source_families": owners,
            "evidence_classes": categories,
            "owner_supplied_record_count": len(entries),
            "distinct_origin_count": len(origins),
            "correlated_repeat_count": len(entries) - len(origins),
            "linked_independent_origin_support_count": len(corroborating_links[entity_key]),
            "linked_contradictory_event_pair_count": len(contradiction_links[entity_key]),
            "highest_owner_asserted_commercial_evidence_level": max_level or None,
            "contradiction_or_invalid_link_present": contradiction,
            "buyer_intent_independently_verified": False,
            "owner_claims_do_not_prove_causality": True,
            "confidence_or_probability": None,
            "forecast_or_model_promotion": False,
            "review_status": (
                "CONTRADICTION_REVIEW_HOLD" if contradiction
                else "UNVERIFIED_OWNER_CUSTODY_RESEARCH_ONLY"
            ),
        })

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": ("NOT_CONNECTED_NOT_VERIFIED_ZERO" if original_owner_summaries is None
                   else "OWNER_INPUT_EMPTY_NOT_VERIFIED_ZERO" if not original_owner_summaries
                   else "PRIVATE_OWNER_SUPPLIED_SHADOW_REVIEW_ONLY"),
        "record_count_owner_supplied": len(records) if original_owner_summaries is not None else None,
        "rejected_count": sum(rejected.values()),
        "rejected_reasons_aggregate": dict(sorted(rejected.items())),
        "conflicting_event_count": len(conflicted),
        "unresolved_evidence_link_count": unresolved_links,
        "cross_entity_link_violation_count": invalid_cross_entity_links,
        "evidence_class_counts": dict(sorted(Counter(x["evidence_class"] for x in records).items())),
        "source_family_counts": dict(sorted(Counter(x["owner"] for x in records).items())),
        "group_reviews": reviews,
        "source_rights_independently_authenticated_by_this_module": False,
        "tenant_authentication_performed_by_this_module": False,
        "source_provenance_independently_authenticated_by_this_module": False,
        "buyer_enquiries_independently_verified": False,
        "accepted_orders_independently_verified": False,
        "settled_revenue_independently_verified": False,
        "trading_outcomes_mixed_into_commercial_calibration": False,
        "predictions_evaluated": False,
        "calibrated_confidence": None,
        "revenue_recognized_cents": None,
        "prediction_accuracy_proven": False,
        "independent_scientific_validation_status": "HOLD_NO_VALIDATED_FORWARD_COHORT",
        "founder_summary_safe_aggregates_only": True,
        "existing_economic_signal_fabric_unmodified": True,
        "original_crm_and_buyer_acquisition_unmodified": True,
        "astra_dispatched": False,
        "empiredb_written": False,
        "outbound_sent": False,
        "financial_execution": False,
        "model_training": False,
        "execution_authority": "none",
        "blockers": [
            "AUTHENTICATED_ORIGINAL_OWNER_SOURCE_ADAPTERS_NOT_CONNECTED",
            "OWNER_ASSERTIONS_NOT_INDEPENDENT_PROVENANCE_OR_RIGHTS",
            "TENANT_BINDING_NOT_AUTHENTICATED_BY_PURE_FUSION",
            "INDEPENDENT_FORWARD_OUTCOME_CALIBRATION_REQUIRED",
            "NO_AUTOMATIC_BUYER_INTENT_OR_REVENUE_PROMOTION",
        ],
    }
