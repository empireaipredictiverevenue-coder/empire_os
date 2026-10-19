"""Read-only, exact-market correlation of one Opportunity Radar signal and
existing EmpireDB buyer *projection*. Market correlation is NOT an accepted
buybox, CRM tenant relationship, buyer reply, quote, consent or revenue.

No SQL, DB write, Gmail access, buyer contacts or raw buyer IDs in output.
No fuzzy/substring joins across niche or city (e.g. UK != Little Rock).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping
import re

from empire_os.buyer_specific_buybox_review import (
    MAX_INPUT, review_buyer_buybox_candidates,
)
from empire_os.revenue_buyer_evidence_handoff import (
    review_one_commercial_evidence_request,
)
from empire_os.revenue_evidence_pathways import _read, market_identity_digest

SCHEMA = "empire.predictive_revenue.market_buyer_linkage_review.v1"
MAX_RETURN = 8
SAFE_NICHE = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
SAFE_METRO = re.compile(r"[a-z][a-z0-9 ,.'-]{0,99}\Z")


class MarketBuyerLinkageHold(ValueError):
    pass


def _normalize(value: Any, pattern: re.Pattern[str]) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.casefold().strip().split())
    return cleaned if pattern.fullmatch(cleaned) else None


def _source_market(repo_root: Path, *, prepared: Mapping[str, Any],
                   as_of: datetime) -> dict[str, Any]:
    current = review_one_commercial_evidence_request(
        repo_root, as_of=as_of,
    )
    if (current.get("status") != "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
            or not isinstance(prepared, Mapping)
            or dict(prepared) != current):
        raise MarketBuyerLinkageHold("first_party_evidence_request_drift_or_hold")
    request = current["request"]
    opaque = request["opportunity_ref"]
    data = _read(repo_root, "radar")
    rows = data.get("candidates")
    if not isinstance(rows, list) or len(rows) > 250:
        raise MarketBuyerLinkageHold("radar_scope_invalid")
    matched = [
        row for row in rows if isinstance(row, Mapping)
        and isinstance(row.get("opportunity_key"), str)
        and "oppref_" + sha256(
            row["opportunity_key"].encode()
        ).hexdigest()[:20] == opaque
    ]
    if len(matched) != 1:
        raise MarketBuyerLinkageHold("source_opportunity_identity_mismatch")
    row = matched[0]
    if market_identity_digest(row) != request.get("market_identity_digest"):
        raise MarketBuyerLinkageHold("source_market_revision_changed")
    if (row.get("execution_authority") != "none"
            or row.get("commercial_demand_observed") is not False
            or row.get("buyer_intent_inferred") is not False
            or row.get("revenue_inferred") is not False):
        raise MarketBuyerLinkageHold("source_market_cannot_prove_buyer_intent")
    niche = _normalize(row.get("niche"), SAFE_NICHE)
    metro = _normalize(row.get("metro"), SAFE_METRO)
    if not niche or not metro or niche != request["niche"]:
        raise MarketBuyerLinkageHold("exact_niche_metro_required")
    return {"niche": niche, "metro": metro, "opportunity_ref": opaque}


def review_existing_buyer_market_linkage(
    repo_root: Path, *, prepared: Mapping[str, Any],
    buyer_rows: Iterable[Mapping[str, Any]],
    as_of: datetime, max_return: int = MAX_RETURN,
) -> dict[str, Any]:
    if (not isinstance(as_of, datetime) or as_of.utcoffset() is None
            or type(max_return) is not int or not 1 <= max_return <= MAX_RETURN):
        raise ValueError("invalid bounded market review request")
    source = _source_market(
        Path(repo_root).resolve(), prepared=prepared, as_of=as_of,
    )
    buyer_inventory = list(buyer_rows)
    if len(buyer_inventory) > MAX_INPUT or any(
        not isinstance(row, Mapping) for row in buyer_inventory
    ):
        raise MarketBuyerLinkageHold("untrusted_or_unbounded_buyer_inventory")

    matching: list[Mapping[str, Any]] = []
    niche_only = 0
    tenant_held = 0
    incomplete_market = 0
    for row in buyer_inventory:
        # This founder-global research review has no tenant authority.
        # Even a niche/metro match cannot override a tenant-scoped record.
        # public.buyers tenant owner is org_id. An absent projection field
        # MUST NOT be interpreted as globally visible buyer data.
        if ("org_id" not in row or row.get("org_id") is not None
                or row.get("tenant_id") not in (None, "")):
            tenant_held += 1
            continue
        niche = _normalize(row.get("niche"), SAFE_NICHE)
        metro = _normalize(row.get("metro"), SAFE_METRO)
        if not niche or not metro:
            incomplete_market += 1
            continue
        if niche == source["niche"]:
            niche_only += 1
            if metro == source["metro"]:
                matching.append(row)
    # Reuse canonical same-record buybox checks. This is a configured state
    # inventory ONLY; the real product/postcode/terms must still be proved.
    preview = review_buyer_buybox_candidates(
        matching, as_of=as_of, max_candidates=max_return,
    )
    details = []
    blockers = Counter()
    for row in preview["candidates"]:
        missing = row["missing_evidence"]
        blockers.update(entry["evidence_key"] for entry in missing)
        details.append({
            "opaque_buyer_ref": row["buyer_ref"],
            "same_record_evidence_stage_count": row["evidence_stage_count"],
            "same_record_evidence_stage_total": row["evidence_stage_total"],
            "next_source_review": row["next_action"],
            "configured_activation_gate_passed": row[
                "configured_activation_gate_passed"
            ],
            "market_only_prospect_not_buyer_acceptance": True,
            "specific_product_price_and_postcode_terms_verified": False,
            "outbound_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": (
            "EXACT_MARKET_BUYER_RECORDS_NEED_VERIFICATION" if matching
            else "NO_EXACT_MARKET_BUYER_RECORDS_IN_PROJECTION"
        ),
        "mode": "OBSERVE",
        "opportunity_ref": source["opportunity_ref"],
        "market_niche": source["niche"],
        "market_metro": source["metro"],
        "source_buyer_record_count": len(buyer_inventory),
        "same_niche_record_count": niche_only,
        "same_niche_and_exact_metro_record_count": len(matching),
        "missing_or_unusable_market_record_count": incomplete_market,
        "tenant_scoped_records_held": tenant_held,
        "excluded_identity_count": preview["excluded_identity_count"],
        "candidate_count": preview["candidate_count"],
        "returned_count": preview["returned_count"],
        "truncated_count": preview["truncated_count"],
        "source_stage_blockers_in_displayed_records": dict(sorted(blockers.items())),
        "candidates": details,
        "authoritative_crm_organisation_link_verified": False,
        "confirmed_buybox_specific_price_postcode_and_capacity": False,
        "original_buyer_reply_or_authorisation_verified": False,
        "quant_inputs_created": False,
        "prediction_registered": False,
        "revenue_recognized": False,
        "full_cross_market_search_performed": False,
        "market_match_is_buyer_intent": False,
        "external_model_invoked": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def inspect_existing_buyer_projection_readonly(
    repo_root: Path, *, prepared: Mapping[str, Any],
    buyer_reader: Any, as_of: datetime,
) -> dict[str, Any]:
    """One bounded existing canonical reader; unknown must never mean zero."""
    if not callable(buyer_reader):
        raise ValueError("canonical buyer reader callable required")
    held = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "BUYER_SOURCE_UNAVAILABLE",
        "source_buyer_record_count": None,
        "same_niche_record_count": None,
        "same_niche_and_exact_metro_record_count": None,
        "candidate_count": None,
        "candidates": [],
        "market_match_is_buyer_intent": False,
        "confirmed_buybox_specific_price_postcode_and_capacity": False,
        "authoritative_crm_organisation_link_verified": False,
        "original_buyer_reply_or_authorisation_verified": False,
        "quant_inputs_created": False,
        "revenue_recognized": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
    try:
        buyer_rows = buyer_reader()
    except Exception:
        # Never emit gateway exception text: it may contain DSNs/credentials.
        return dict(held, status="CANONICAL_BUYER_GATEWAY_UNAVAILABLE")
    try:
        return review_existing_buyer_market_linkage(
            repo_root, prepared=prepared, buyer_rows=buyer_rows,
            as_of=as_of,
        )
    except (MarketBuyerLinkageHold, ValueError, TypeError, AttributeError):
        return dict(held, status="BUYER_MARKET_LINKAGE_EVIDENCE_HELD")
