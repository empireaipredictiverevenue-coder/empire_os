"""Source-specific, OBSERVE-only production research queue for microsites.

Ranking reflects review value, NOT paid traffic potential, expected conversions,
search rank probability or actual revenue. A candidate never self-approves release.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Any

from empire_os.predictive_microsite_factory import build_candidate, review_portfolio
from empire_os.microsite_commercial_intelligence_v3 import build_microsite_commercial_review
from empire_os.microsite_first_party_gsc_bridge import connect_factory_to_gsc


def build_ranked_microsite_queue(
    specs: Sequence[Mapping[str, Any]], *,
    commercial: Mapping[str, Any],
    gsc: Mapping[str, Any] | None = None,
    calibration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(specs, (list, tuple)) or not 1 <= len(specs) <= 25:
        raise ValueError("bounded original candidate list required")
    if not isinstance(commercial, Mapping) or commercial.get("schema_version") != "empire.microsite_commercial_intelligence.v3":
        raise ValueError("canonical commercial review required")
    if (commercial.get("execution_authority") != "none"
            or commercial.get("published") is not False
            or commercial.get("publishable_candidates") != 0
            or commercial.get("candidates_reviewed") != len(specs)
            or not isinstance(commercial.get("candidates"), list)):
        raise ValueError("commercial review must be draft-only and complete")
    reviews = review_portfolio(specs)
    ids = [item["id"] for item in reviews]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate candidate identity")
    commercial_by_id = {r.get("candidate_id"): r for r in commercial["candidates"] if isinstance(r, Mapping)}
    if len(commercial_by_id) != len(ids) or set(commercial_by_id) != set(ids):
        raise ValueError("commercial review candidate identity drift")

    if gsc is not None:
        if (not isinstance(gsc, Mapping)
                or gsc.get("schema_version") != "empire.microsite.first_party_gsc_bridge.v1"
                or gsc.get("execution_authority") != "none"
                or gsc.get("publication_authorized") is not False
                or gsc.get("market_volume_assumed") is not False
                or not isinstance(gsc.get("candidates"), list)):
            raise ValueError("GSC bridge must use exact first-party source")
        gsc_by_id = {r.get("candidate_id"): r for r in gsc["candidates"] if isinstance(r, Mapping)}
        if len(gsc_by_id) != len(ids) or set(gsc_by_id) != set(ids):
            raise ValueError("GSC candidate identity mismatch")
    else:
        gsc_by_id = {}

    if calibration is not None:
        if (not isinstance(calibration, Mapping)
                or calibration.get("schema_version") != "empire.microsite.model_calibration_review.v1"
                or calibration.get("mode") != "OBSERVE"
                or calibration.get("execution_authority") != "none"
                or calibration.get("model_training_authorized") is not False
                or not isinstance(calibration.get("models"), list)):
            raise ValueError("untrusted model calibration dossier")
    cal_by_key = {}
    for item in (calibration or {}).get("models", []):
        if not isinstance(item, Mapping):
            raise ValueError("invalid calibration row")
        key = (item.get("model_name"), item.get("model_version"), item.get("metric"))
        if key in cal_by_key or any(not isinstance(v, str) or not v for v in key):
            raise ValueError("duplicate or invalid calibration model identity")
        cal_by_key[key] = item

    output = []
    for packet in reviews:
        ident = packet["id"]
        commercial_row = commercial_by_id[ident]
        if (commercial_row.get("area") != packet["market"]["area"]
                or commercial_row.get("keyword") != packet["keyword"]["record"]["keyword"]
                or commercial_row.get("commercial_ready_to_publish") is not False
                or commercial_row.get("buyer_activation_authorized") is not False
                or commercial_row.get("revenue_verified") is not False):
            raise ValueError("commercial overlay drift or unsafe activation")
        observed_gsc = gsc_by_id.get(ident)
        if observed_gsc and (observed_gsc.get("keyword") != packet["keyword"]["record"]["keyword"]
                             or observed_gsc.get("territory_key") != packet["market"]["market_id"]
                             or observed_gsc.get("geo_demand_from_gsc_proven") is not False
                             or observed_gsc.get("market_search_volume") is not None
                             or observed_gsc.get("buyer_accepted") is not False):
            raise ValueError("GSC candidate evidence is not bounded")

        f = commercial_row["predictive_forecast"]
        b = commercial_row["buyer_targeting"]
        forecast_verified = f.get("verified_forecast_registry_record") is True
        if forecast_verified and f.get("status") != "OBSERVED_PREDICTIVE_RESEARCH_SIGNAL":
            raise ValueError("forecast verification contradiction")
        key = (f.get("model_name"), f.get("model_version"), f.get("metric"))
        cal = cal_by_key.get(key)
        # Never substitute R² or an optimistic model confidence for out-of-sample calibration.
        calibrated = bool(forecast_verified and cal and
                          cal.get("calibration_evidence_verified") is True and
                          cal.get("out_of_sample_evaluations", 0) >= 3)
        exact_gsc = bool(observed_gsc and observed_gsc.get("first_party_query_observed") is True)
        buyer_guidance = b.get("status") == "TARGETING_GUIDANCE_ONLY"
        scored_keyword = packet["keyword"]["opportunity"]["available"] is True
        # Research PRIORITY, not a demand or ROI prediction.
        research_priority = (
            15 * int(bool(packet["content_evidence"]))
            + 25 * int(exact_gsc)
            + 15 * int(buyer_guidance)
            + 20 * int(forecast_verified)
            + 15 * int(calibrated)
            + 10 * int(scored_keyword)
        )
        gaps = list(packet["blockers"])
        if not exact_gsc:
            gaps.append("exact first-party GSC query/page source missing")
        if not forecast_verified:
            gaps.append("exact-scope original Predictive Cloud forecast missing")
        elif not calibrated:
            gaps.append("independent out-of-sample forecast calibration missing")
        if b.get("buyer") is not None and not buyer_guidance:
            gaps.append("fresh relevant buyer coverage guidance missing")
        gaps.append("current website owner has not released this exact asset")
        gaps.append("no attributed settled buyer revenue for this page")
        status = ("PRIORITIZE_EVIDENCE_REVIEW" if research_priority >= 40
                  else "NEEDS_SOURCE_RESEARCH")
        output.append({
            "candidate_id": ident,
            "keyword": packet["keyword"]["record"]["keyword"],
            "area": packet["market"]["area"],
            "site_kind": packet["candidate_kind"],
            "research_priority_points": research_priority,
            "research_priority_not_forecast": True,
            "keyword_opportunity_score": (
                packet["keyword"]["opportunity"]["score"] if scored_keyword else None),
            "exact_first_party_query_observed": exact_gsc,
            "buyer_coverage_observed": buyer_guidance,
            "forecast_evidence_verified": forecast_verified,
            "model_outcome_calibration_verified": calibrated,
            "slopmonster_score": packet["copy_audit"]["score"],
            "content_status": packet["status"],
            "review_status": status,
            "blockers": sorted(set(gaps)),
            "production_slot_authorized": False,
            "public_url": None,
            "verified_page_sessions": None,
            "verified_enquiries": None,
            "verified_buyer_acceptances": None,
            "verified_settled_revenue_minor": None,
        })
    output.sort(key=lambda p: (-p["research_priority_points"], p["candidate_id"]))
    for rank, row in enumerate(output, 1):
        row["research_rank"] = rank
    return {
        "schema_version": "empire.microsite_ranked_production_research_queue.v4",
        "mode": "OBSERVE",
        "queue_type": "RESEARCH_ONLY_NOT_PUBLISH_QUEUE",
        "execution_authority": "none",
        "candidate_count": len(output),
        "calibrated_forecast_candidates": sum(row["model_outcome_calibration_verified"] for row in output),
        "publishable_count": 0,
        "provisional_research_points_not_roi": True,
        "owner_publication_authorized": False,
        "new_domains_created": 0,
        "database_writes": False,
        "outbound_sent": False,
        "rows": output,
    }
