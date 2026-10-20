"""Evidence-first commercial growth review built around existing EmpireOS outputs.

Pure offline adapter. No buyer acquisition, payment, CRM, outbound, model training,
predictive score mutation, or database operations. NOT a commercial-authority gate.

Inputs:
* empire.predictive-revenue.commercial-offer-book.v2 (already policy gated)
* research observations from an authorized read-only producer
* empire.founder_commercial_funnel.v1 (aggregate snapshot only)

Never reinterpret research as verified buying intent. Never turn catalog prices into
forecast revenue. Anonymous/community signals cannot identify a buyer by themselves.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "empire.commercial.video_growth_framework_review.v1"
MAX_ROWS = 500


def _text(value: Any, max_chars: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:max_chars]


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(dict.fromkeys(
        clean for item in value[:30]
        if (clean := _text(item, 250))
    ))


def _source_freshness(value: Any, now: datetime) -> dict[str, Any]:
    timestamp = _text(value, 100)
    if not timestamp:
        return {"status": "UNKNOWN", "generated_at": None, "age_hours": None}
    try:
        dt = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
        if dt.tzinfo is None:
            raise ValueError("timezone required")
        age = (now - dt.astimezone(timezone.utc)).total_seconds() / 3600
    except (TypeError, ValueError, OverflowError):
        return {"status": "INVALID", "generated_at": timestamp, "age_hours": None}
    status = "FUTURE" if age < -0.1 else "STALE" if age > 72 else "FRESH"
    return {"status": status, "generated_at": timestamp, "age_hours": round(age, 2)}


def _identity(row: Mapping[str, Any]) -> str | None:
    """Only canonical prospect ID; no fuzzy name/domain/person identity joins."""
    prospect = _text(row.get("canonical_prospect_id"), 120)
    return prospect or None


def _signals(packet: Mapping[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], int]:
    source = packet.get("observations")
    if source is None and packet and all(
        isinstance(row, Mapping) for row in packet.values()
    ):
        # Existing revenue_actors/community_intent_normalized.json is a
        # signal-id-keyed dictionary, not an observations array. The actor's
        # claimed author is NEVER considered a prospect identity.
        source = []
        for key, actor in packet.items():
            if _text(actor.get("source")) != "community_intent":
                continue
            raw = actor.get("raw")
            raw = raw if isinstance(raw, Mapping) else {}
            inner = raw.get("community_intent")
            inner = inner if isinstance(inner, Mapping) else {}
            refs = raw.get("evidence_urls")
            refs = refs if isinstance(refs, list) else []
            if not refs and _text(actor.get("url")):
                refs = [actor["url"]]
            source.append({
                "signal_id": _text(actor.get("signal_id")) or _text(key),
                "niche": _text(actor.get("niche") or inner.get("niche")),
                "evidence_refs": refs,
                # No canonical_prospect_id: never infer from social author.
            })
    if not isinstance(source, list) or len(source) > MAX_ROWS:
        raise ValueError("observations must be a list with no more than 500 entries")

    linked: dict[str, list[dict[str, Any]]] = {}
    unlinked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for row in source:
        if not isinstance(row, Mapping):
            continue
        signal_id = _text(row.get("signal_id") or row.get("observation_id"), 160)
        refs = _refs(row.get("evidence_refs"))
        # No ID, no reliable dedup evidence; preserve as unlinked review, never
        # fabricate a source identity from free text or attribute to a buyer.
        if not signal_id or not refs:
            unlinked.append({
                "signal_id": signal_id or None,
                "review_reason": "signal_id_and_evidence_refs_required",
            })
            continue

        prospect = _identity(row)
        key = (prospect or "__unlinked__", signal_id)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        view = {
            "signal_id": signal_id,
            "niche": _text(row.get("niche"), 80) or None,
            "problem": _text(row.get("pain_summary") or row.get("problem"), 220) or None,
            "evidence_refs": refs,
            "buyer_demand_verified": False,  # Research never grants this.
            "source_status": "RESEARCH_OBSERVATION_ONLY",
        }
        if prospect:
            linked.setdefault(prospect, []).append(view)
        else:
            unlinked.append({
                "signal_id": signal_id,
                "review_reason": "canonical_prospect_id_required",
                "evidence_refs": refs,
            })
    return linked, unlinked, duplicates


def _offer_row(row: Mapping[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    state = _text(row.get("state"), 60).upper()
    # OFFER_READY is meaningful only when explicitly passed by canonical
    # source and still does NOT imply permission to contact anyone.
    ready = row.get("offer_package_ready") is True and state == "OFFER_READY"
    demand = row.get("buyer_demand_verified") is True and _text(
        row.get("demand_state"), 30
    ).upper() == "VERIFIED"
    existing = _text(row.get("contact_mode"), 55) == "EXISTING_THREAD_REVIEW"
    product_codes = list(dict.fromkeys(
        _text(item, 100) for item in (row.get("ready_product_codes") or [])
        if isinstance(item, str) and _text(item, 100)
    ))
    # Preserve only verified pre-selected product evidence from offer book.
    products = row.get("products")
    products = products if isinstance(products, list) else []
    evidence = _refs(row.get("evidence_refs")) + [
        ref for signal in signals for ref in signal["evidence_refs"]
    ]
    evidence = list(dict.fromkeys(evidence))[:40]
    if not ready:
        next_action = (
            "VERIFY_PRODUCT_TERMS_AND_FULFILLMENT" if state == "PRODUCT_READINESS_REQUIRED"
            else "QUALIFY_CONTACT_EVIDENCE"
        )
    elif not demand:
        next_action = "VALIDATE_BUYER_DEMAND"
    elif existing:
        next_action = "REVIEW_EXISTING_THREAD_FOR_NEXT_QUESTION"
    else:
        next_action = "REQUEST_FOUNDER_OUTBOUND_REVIEW"

    priority = (
        0 if ready and demand and existing else
        1 if ready and demand else
        2 if ready else
        3 if state == "CONTACT_EVIDENCE_REQUIRED" else 4
    )
    person_verified = row.get("person_verified") is True
    email_verified = row.get("email_verified") is True
    gap_codes = []
    if not _identity(row):
        gap_codes.append("CANONICAL_ID_MISSING")
    if state == "PRODUCT_READINESS_REQUIRED":
        gap_codes.append("PRODUCT_TERMS_OR_CATALOG_UNREADY")
    elif state not in ("OFFER_READY", "CONTACT_EVIDENCE_REQUIRED"):
        gap_codes.append("UNRECOGNIZED_OFFER_READINESS_STATE")
    if not person_verified or not email_verified or state == "CONTACT_EVIDENCE_REQUIRED":
        gap_codes.append("PERSON_CONTACT_EVIDENCE_UNVERIFIED")
    if not demand:
        gap_codes.append("BUYER_DEMAND_NOT_VERIFIED")
    if existing:
        gap_codes.append("EXISTING_CONVERSATION_REQUIRES_LIVE_THREAD_RECHECK")
    # These are cross-cutting review needs, not task assignments or
    # permission to change canonical prospect, contact or CRM records.
    workstream_map = {
        "CANONICAL_ID_MISSING": "decision_maker_resolver",
        "PRODUCT_TERMS_OR_CATALOG_UNREADY": "commercial_catalog_owner",
        "UNRECOGNIZED_OFFER_READINESS_STATE": "commercial_catalog_owner",
        "PERSON_CONTACT_EVIDENCE_UNVERIFIED": "contact_verifier",
        "BUYER_DEMAND_NOT_VERIFIED": "buyer_qualifier",
        "EXISTING_CONVERSATION_REQUIRES_LIVE_THREAD_RECHECK": "sales_director_operator",
    }
    return {
        "readiness_gap_codes": gap_codes,
        "review_owner_lanes": list(dict.fromkeys(workstream_map[c] for c in gap_codes)),
        "person_verified_in_source": person_verified,
        "email_verified_in_source": email_verified,
        "canonical_id_is_historical_source_claim": bool(_identity(row)),
        "canonical_prospect_id": _identity(row),
        "company": _text(row.get("company"), 120) or None,
        "domain": _text(row.get("domain"), 140) or None,
        "contact_mode": "EXISTING_THREAD_REVIEW" if existing else "NEW_OUTREACH_REVIEW",
        "demand_state": "BUYER_DEMAND_VERIFIED_BY_OFFER_BOOK" if demand else "NOT_VERIFIED",
        "offer_state": state or "UNKNOWN",
        "offer_package_ready": ready,
        "ready_product_codes": product_codes if ready else [],
        "verified_offer_price_bases": [
            {
                "product_code": _text(p.get("product_code"), 100),
                "amount_cents": p.get("amount_cents"),
                "currency": _text(p.get("currency"), 8),
                "unit": _text(p.get("unit"), 70),
            }
            for p in products if (
                ready and isinstance(p, Mapping)
                and type(p.get("amount_cents")) is int and p["amount_cents"] > 0
                and _text(p.get("currency"), 8) and _text(p.get("unit"), 70)
                and p.get("product_code") in product_codes
            )
        ],
        "linked_research_signal_ids": [s["signal_id"] for s in signals],
        "research_problem_hypotheses": [
            {
                "signal_id": s["signal_id"],
                "problem": s["problem"],
                "niche": s["niche"],
                "status": "UNVERIFIED_RESEARCH_HYPOTHESIS",
            }
            for s in signals[:5]
        ],
        "research_signals_do_not_prove_demand": True,
        "evidence_refs": evidence,
        "next_research_or_review_action": next_action,
        "priority_band": priority,
        "send_blockers": sorted(set([
            "founder_live_outbound_approval_required",
            "current_canonical_suppression_and_inbox_check",
            "live_outbound_authority_required",
            *(_refs(row.get("send_blockers"))),
        ])),
        "outreach_authorized": False,
        "offer_acceptance_authorized": False,
        "payment_authorized": False,
        "expected_revenue_cents": None,
        "revenue_realized_cents": None,
    }


def build_commercial_growth_review(
    *, observations: Mapping[str, Any],
    offer_book: Mapping[str, Any],
    funnel: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compose existing trusted-format packets into a non-executing review.

    Refuses unknown offer-book schemas and duplicate canonical buyer identities.
    Marks missing, invalid, future or stale source snapshots for refresh.
    Data remains observations, not commands.
    """
    if _text(offer_book.get("schema_version")) != "empire.predictive-revenue.commercial-offer-book.v2":
        raise ValueError("canonical commercial offer book v2 required")
    if _text(funnel.get("schema_version")) != "empire.founder_commercial_funnel.v1":
        raise ValueError("canonical commercial funnel v1 required")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must contain timezone")
    now = now.astimezone(timezone.utc)
    sources_freshness = {
        "offer_book": _source_freshness(offer_book.get("generated_at"), now),
        "funnel": _source_freshness(funnel.get("generated_at"), now),
    }
    requires_refresh = any(
        row["status"] != "FRESH" for row in sources_freshness.values()
    )

    targets = offer_book.get("targets")
    if not isinstance(targets, list) or len(targets) > MAX_ROWS:
        raise ValueError("offer book targets must be <=500 rows")
    linked, unlinked, duplicate_signals = _signals(observations)
    reviews: list[dict[str, Any]] = []
    observed_buyers: set[str] = set()
    for row in targets:
        if not isinstance(row, Mapping):
            continue
        prospect = _identity(row)
        if prospect:
            if prospect in observed_buyers:
                raise ValueError("duplicate canonical_prospect_id in offer book")
            observed_buyers.add(prospect)
        review = _offer_row(row, linked.pop(prospect, []) if prospect else [])
        if not prospect:
            review["next_research_or_review_action"] = "RESOLVE_CANONICAL_PROSPECT_ID"
            review["priority_band"] = 5
            review["offer_package_ready"] = False
            review["ready_product_codes"] = []
            review["verified_offer_price_bases"] = []
        reviews.append(review)
    # A signal linked by ID but missing an existing offer target stays unlinked
    # rather than being silently dropped or converted into a new prospect.
    for prospect, signals in linked.items():
        for signal in signals:
            unlinked.append({
                "signal_id": signal["signal_id"],
                "canonical_prospect_id": prospect,
                "review_reason": "no_canonical_offer_book_target",
                "evidence_refs": signal["evidence_refs"],
            })
    reviews.sort(key=lambda r: (
        r["priority_band"],
        r["canonical_prospect_id"] or "",
        r["domain"] or "",
    ))
    gap_counts = {
        code: sum(code in row["readiness_gap_codes"] for row in reviews)
        for code in (
            "CANONICAL_ID_MISSING",
            "PRODUCT_TERMS_OR_CATALOG_UNREADY",
            "UNRECOGNIZED_OFFER_READINESS_STATE",
            "PERSON_CONTACT_EVIDENCE_UNVERIFIED",
            "BUYER_DEMAND_NOT_VERIFIED",
            "EXISTING_CONVERSATION_REQUIRES_LIVE_THREAD_RECHECK",
        )
    }
    owner_counts = {
        lane: sum(lane in row["review_owner_lanes"] for row in reviews)
        for lane in sorted({lane for row in reviews for lane in row["review_owner_lanes"]})
    }

    # Aggregate economic truth must not be attributed to these candidates.
    actual = funnel.get("actual_revenue") is True
    recognized = funnel.get("recognized_revenue_cents")
    margin = funnel.get("realized_margin_cents")
    recognized = recognized if type(recognized) is int and recognized >= 0 else None
    margin = margin if type(margin) is int else None
    revenue_context = {
        "source": "supplied_canonical_funnel_snapshot",
        "input_actual_revenue_flag": actual,
        "reported_recognized_revenue_cents": recognized if actual else None,
        "reported_realized_margin_cents": margin if actual else None,
        "attributed_to_reviewed_opportunities_cents": None,
        "verification_status": "SOURCE_INPUT_NOT_INDEPENDENTLY_REVERIFIED",
        "current_stage": _text(funnel.get("current_stage"), 90) or "unknown",
        "next_event": _text(funnel.get("next_event"), 100) or "review_canonical_funnel",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE_ONLY",
        "deployment_status": "NOT_DEPLOYED",
        "source_freshness": {
            **sources_freshness,
            "max_age_hours": 72,
            "requires_refresh_before_commercial_use": requires_refresh,
        },
        "source_contracts": {
            "offer_book": "empire.predictive-revenue.commercial-offer-book.v2",
            "funnel": "empire.founder_commercial_funnel.v1",
            "observations": "research_only_no_contact_authority",
        },
        "readiness_gap_counts_nonexclusive": gap_counts,
        "owner_review_lane_counts_nonexclusive": owner_counts,
        "readiness_counts_are_overlapping": True,
        "historical_source_claims_not_live_customer_proof": True,
        "source_counts": {
            "canonical_offer_targets": len(reviews),
            "linked_research_observations": sum(len(r["linked_research_signal_ids"]) for r in reviews),
            "duplicate_research_observations_skipped": duplicate_signals,
            "unlinked_research_observations": len(unlinked),
        },
        "review_queue": reviews,
        "unlinked_signal_review": unlinked,
        "review_only": True,
        "refresh_is_required_before_approaching_or_reporting_on_these_targets": requires_refresh,
        "aggregate_revenue_context": revenue_context,
        "principles": [
            "identify_evidence_backed_expensive_problems",
            "match_only_current_verified_offers",
            "review_inbound_and_outbound_pathways",
            "advance_genuine_buyer_conversations",
            "verify_payment_fulfilment_and_realized_margin",
            "recalibrate_using_validated_outcomes_not_claims",
        ],
        "outbound_authority": "NONE",
        "payment_authority": "NONE",
        "agent_owner_changes": False,
        "database_writes": False,
        "external_actions": False,
        "autonomous_pricing": False,
        "model_training": False,
    }
