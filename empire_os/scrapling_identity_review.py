"""No-write identity review bridge: Scrapling observations -> Empire canonical IDs.

Uses existing source-governance and acquisition-fingerprint contracts, but
does not create LeadCandidate, call canonical writers, assert a confirmed
match, or treat a proposed entity as lead inventory.

An incomplete or field-restricted EmpireDB reader must FAIL CLOSED: the lead
supply census (id/niche/metro/status only) is NOT enough for identity matching.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
import re

from empire_os.niche_taxonomy import niche_family, metro_key
from empire_os.prospect_ingest import acquisition_fingerprint
from empire_os.waterfall_source_bridge import (
    EvidenceReview, build_waterfall_source_review, MAX_REVIEW_RECORDS,
)

MAX_CANONICAL_ROWS = 20_000
REQUIRED_IDENTITY_FIELDS = frozenset(
    {"id", "business_name", "niche", "metro", "phone"}
)
SCHEMA = "empire.scrapling_canonical_identity_review.v1"

# Existing registered lead source aliases ONLY. Other sources may remain
# evidence-only until a separate authorised crawler source integration.
CANONICAL_SOURCE_ALIASES = {
    "gb_recc_solar": "recc_solar",
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _phone(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def review_scrapling_canonical_identity(
    *,
    report: Mapping[str, Any],
    review: EvidenceReview,
    canonical_rows: Sequence[Mapping[str, Any]] | None,
    canonical_snapshot_complete: bool,
    canonical_snapshot_ref: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Deterministic proposals only, NOT verified entity links or new leads.

    canonical_rows must come from a separately authorised complete, stable,
    read-only identity scan (NOT founder census, sampled leads, or exchange).
    """
    if not isinstance(report, Mapping):
        raise TypeError("report must be mapping")
    if not isinstance(review, EvidenceReview):
        raise TypeError("review must be EvidenceReview")
    records = report.get("records")
    if not isinstance(records, list) or len(records) > MAX_REVIEW_RECORDS:
        raise ValueError("bounded report required")

    snapshot_valid = (
        canonical_snapshot_complete is True
        and isinstance(canonical_snapshot_ref, str)
        and 5 <= len(canonical_snapshot_ref.strip()) <= 300
        and canonical_snapshot_ref == canonical_snapshot_ref.strip()
        and isinstance(canonical_rows, (tuple, list))
        and len(canonical_rows) <= MAX_CANONICAL_ROWS
    )
    snapshot_reasons = []
    rows: list[Mapping[str, Any]] = []
    if not snapshot_valid:
        snapshot_reasons.append("complete_authorised_canonical_snapshot_required")
    else:
        assert canonical_rows is not None
        if any(
            not isinstance(row, Mapping)
            or not REQUIRED_IDENTITY_FIELDS.issubset(row)
            or not str(row.get("id") or "").strip()
            for row in canonical_rows
        ):
            snapshot_reasons.append("canonical_identity_fields_missing")
        else:
            rows = list(canonical_rows)
            ids = [str(row["id"]).strip() for row in rows]
            if len(set(ids)) != len(ids):
                snapshot_reasons.append("duplicate_canonical_ids_in_snapshot")
            if any(not _norm(row.get("business_name"))
                   or not niche_family(row.get("niche"))
                   or not metro_key(row.get("metro"))
                   for row in rows):
                snapshot_reasons.append("canonical_identity_values_missing")

    decisions: list[dict[str, Any]] = []
    observed_keys: set[str] = set()
    stats: Counter[str] = Counter()
    for index, record in enumerate(records):
        # Reuse the reviewed Scrapling source contract for EVERY record.
        plan = build_waterfall_source_review(
            report, record_index=index, review=review, now=now
        )
        if not isinstance(record, Mapping):
            raise ValueError("source record must be mapping")
        observed_name = str(record.get("business_name") or "").strip()
        niche = str(record.get("niche_observed") or "")
        metro = str(record.get("metro_observed") or "")
        phone = str(record.get("public_phone_observed") or "")
        source_link = str(record.get("source_link_observed") or "")
        source = str(report.get("source_id") or "")
        observed_at = str(report.get("observed_at") or "")
        # The existing fingerprint is an *acquisition idempotency aid* ONLY.
        obs_key = acquisition_fingerprint(
            source=source, source_url=source_link or report.get("source_url", ""),
            business_name=observed_name, metro=metro, phone=phone,
        )
        reasons = [*plan.get("reasons", []), *snapshot_reasons]
        if not metro or not observed_name:
            reasons.append("record_identity_incomplete")
        if source not in CANONICAL_SOURCE_ALIASES:
            reasons.append("canonical_lead_source_adapter_not_approved")

        if obs_key in observed_keys:
            reasons.append("duplicate_observation_in_report")
        observed_keys.add(obs_key)

        # Reject mismatch between record's metro and founder-reviewed target
        # only when the plan provides an explicit territory scope.
        normalized_name = _norm(observed_name)
        if reasons:
            state = "HOLD"
            candidate_ids: list[str] = []
        else:
            niche_key, metro_normalized = niche_family(niche), metro_key(metro)
            same_context = [
                row for row in rows
                if niche_family(row["niche"]) == niche_key
                and metro_key(row["metro"]) == metro_normalized
            ]
            exact_name = [
                row for row in same_context
                if _norm(row["business_name"]) == normalized_name
            ]
            phone_key = _phone(phone)
            exact_phone = [
                row for row in same_context
                if phone_key and _phone(row.get("phone")) == phone_key
            ]
            # A shared number with a DIFFERENT business is a collision and
            # must never establish identity, regardless of source confidence.
            phone_conflicts = [
                row for row in exact_phone
                if _norm(row["business_name"]) != normalized_name
            ]
            if phone_conflicts:
                state = "IDENTITY_CONFLICT"
                reasons.append("shared_phone_different_business")
                candidate_ids = []
            elif len(exact_name) > 1:
                state = "AMBIGUOUS"
                reasons.append("multiple_exact_name_and_territory")
                candidate_ids = [str(row["id"]) for row in exact_name]
            elif len(exact_name) == 1:
                match = exact_name[0]
                if phone_key and _phone(match.get("phone")) and _phone(match.get("phone")) != phone_key:
                    state = "IDENTITY_CONFLICT"
                    reasons.append("observed_phone_disagrees_with_canonical")
                    candidate_ids = [str(match["id"])]
                else:
                    state = "POTENTIAL_EXISTING_REVIEW"
                    candidate_ids = [str(match["id"])]
            elif exact_phone:
                state = "IDENTITY_CONFLICT"
                reasons.append("phone_only_evidence_not_business_identity")
                candidate_ids = []
            else:
                state = "NOT_FOUND_IN_COMPLETE_SNAPSHOT"
                candidate_ids = []

            # Holdings in other markets or verticals may be branches and
            # aliases. Never auto-merge across corridor / niche.
            cross_market = [
                row for row in rows if _norm(row["business_name"]) == normalized_name
                and row not in exact_name
            ]
            external_phone = [
                row for row in rows if phone_key
                and _phone(row.get("phone")) == phone_key
                and row not in same_context
            ]
            if cross_market and state == "NOT_FOUND_IN_COMPLETE_SNAPSHOT":
                state = "CROSS_MARKET_MANUAL_REVIEW"
                reasons.append("same_name_elsewhere_not_independent_identity")
            if external_phone and state == "NOT_FOUND_IN_COMPLETE_SNAPSHOT":
                state = "CROSS_MARKET_MANUAL_REVIEW"
                reasons.append("phone_seen_in_different_market_or_vertical")

        stats[state] += 1
        decisions.append({
            "observation_key": obs_key,
            "source_id": source,
            "source_observed_at": observed_at,
            "niche": niche,
            "metro": metro,
            "state": state,
            "reasons": sorted(set(reasons)),
            "possible_canonical_ids": candidate_ids,
            "canonical_prospect_id_verified": None,
            "entity_link_authorized": False,
            "new_prospect_insert_authorized": False,
            "verified_business_contact": False,
            "buyer_intent_verified": False,
            "outbound_authorized": False,
        })

    return {
        "schema_version": SCHEMA,
        "mode": "OFFLINE_IDENTITY_REVIEW",
        "source_id": report.get("source_id"),
        "source_document_sha256": report.get("content_sha256"),
        "canonical_snapshot_ref": canonical_snapshot_ref if snapshot_valid else None,
        "canonical_snapshot_complete_asserted": bool(snapshot_valid and not snapshot_reasons),
        "canonical_snapshot_rows_inspected": len(rows),
        "source_rows_observed": len(records),
        "observation_decisions": decisions,
        "by_decision": dict(sorted(stats.items())),
        "unique_canonical_leads_verified_added": 0,
        "canonical_database_writes": False,
        "canonical_prospect_insert_authorized": False,
        "contact_promotion_authorized": False,
        "execution_authority": "none",
        "note": "All source/identity receipts are operator assertions pending independent verification",
    }
