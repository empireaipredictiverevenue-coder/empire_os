"""Source-specific, OBSERVE-only production research queue for microsites.

Ranking reflects review value, NOT paid traffic potential, expected conversions,
search rank probability or actual revenue. A candidate never self-approves release.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from datetime import date, datetime, timezone
from urllib.parse import urlsplit
import ipaddress
import re
import json
from typing import Any

from empire_os.predictive_microsite_factory import build_candidate, review_portfolio
from empire_os.microsite_commercial_intelligence_v3 import build_microsite_commercial_review
from empire_os.microsite_first_party_gsc_bridge import connect_factory_to_gsc



def _executive_screen(
    proposal: Mapping[str, Any], *, exact_gsc: bool,
    buyer_guidance: bool, calibrated: bool, today: date,
) -> dict[str, Any]:
    """Investment-committee research screen, not an approval or revenue score.

    The source timestamps are AUTHOR-SUPPLIED, and a valid .gov domain is
    NOT a factual source review. Existing source owners retain all authority.
    """
    facts = proposal["content_evidence"]
    source_refs = {f["source_ref"].strip().casefold() for f in facts}
    official = len({f["official_url"] for f in facts if f.get("official_url")})
    age_days = []
    for fact in facts:
        stamp = datetime.fromisoformat(fact["checked_at"].replace("Z", "+00:00"))
        age_days.append((today - stamp.date()).days)
    # This is an explicit internal 90-day desk-refresh heuristic, not law
    # and not independent verification of an official claim or its accuracy.
    date_review = bool(age_days and all(0 <= n <= 90 for n in age_days))
    unique_utility = (
        len(facts) >= 2 and len(source_refs) >= 2
        and proposal["locally_useful_research_steps"] >= 3
    )
    near_duplicate = any(
        "near-duplicate location-swapped" in str(x)
        for x in proposal["blockers"]
    )
    source_desk = (
        proposal["market"]["region_verified"] is True
        and unique_utility and official >= 2 and date_review
        and not near_duplicate and proposal["copy_audit"]["review_required"] is False
    )

    if proposal["market"]["region_verified"] is not True:
        decision, action, owner = (
            "SOURCE_REPAIR_FIRST", "Verify the exact area/ZIP against a governed geography source",
            "Marketing Research")
    elif near_duplicate:
        decision, action, owner = (
            "SOURCE_REPAIR_FIRST", "Replace location-swapped copy with independent original area-specific utility",
            "Editorial Research")
    elif not unique_utility:
        decision, action, owner = (
            "SOURCE_REPAIR_FIRST", "Provide two distinct attributable facts and three practical research actions",
            "Marketing Research")
    elif official < 2:
        decision, action, owner = (
            "SOURCE_REPAIR_FIRST", "Attach at least two direct official primary-source links, then verify their claims",
            "Marketing Research")
    elif not date_review:
        decision, action, owner = (
            "SOURCE_REFRESH_FIRST", "Recheck all original source facts and record accurate dates (90-day desk heuristic)",
            "Marketing Research")
    elif proposal["copy_audit"]["review_required"] is True:
        decision, action, owner = (
            "EDITORIAL_REPAIR_FIRST", "Rewrite SlopMonster-flagged wording without altering evidence claims",
            "Editorial Research")
    elif not exact_gsc:
        decision, action, owner = (
            "MEASURE_FIRST_PARTY_INTENT", "Request exact-query first-party GSC evidence for this market and reporting window",
            "Original SEO Data Owner")
    elif not buyer_guidance:
        decision, action, owner = (
            "RESEARCH_COMMERCIAL_PATH", "Verify a relevant buyer path and economics without assuming lead acceptance",
            "Original Commercial Owner")
    else:
        decision, action, owner = (
            "EVALUATE_ONE_BOUNDED_EXPERIMENT",
            "Submit the sourced utility and observed search interest for independent owner review; no publication implied",
            "Original Website/SEO Owner")

    return {
        "schema_version": "empire.microsite.executive_research_screen.v1",
        "decision": decision,
        "research_desk_qualified": source_desk,
        "independent_source_claims_verified": False,
        "owner_publication_authorized": False,
        "commercial_investment_authorized": False,
        "customer_economics_verified": False,
        "research_evidence": {
            "distinct_author_source_refs": len(source_refs),
            "direct_official_source_links": official,
            "actionable_research_steps": proposal["locally_useful_research_steps"],
            "author_dated_within_90_days": date_review,
            "source_dates_independently_verified": False,
            "geography_verified": proposal["market"]["region_verified"] is True,
            "editorial_pattern_flags": proposal["copy_audit"]["review_required"] is True,
            "location_swap_duplicate": near_duplicate,
            "exact_query_first_party_observed": exact_gsc,
            "buyer_coverage_guidance_only": buyer_guidance,
            "out_of_sample_forecast_calibrated": calibrated,
        },
        "next_best_evidence_action": action,
        "next_action_owner": owner,
        "next_action_is_research_only": True,
        "expected_revenue_minor": None,
        "expected_traffic": None,
        "cost_per_acquisition": None,
        "roi": None,
    }


def _executive_portfolio(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Diversify *research attention*, never allocate budget or publish."""
    chosen = []
    covered_markets = set()
    for row in rows:
        if not row["executive_screen"]["research_desk_qualified"]:
            continue
        market = row["market_id"]
        if market in covered_markets:
            continue
        chosen.append({
            "candidate_id": row["candidate_id"],
            "market_id": market,
            "research_rank": row["research_rank"],
            "next_evidence_action": row["executive_screen"]["next_best_evidence_action"],
        })
        covered_markets.add(market)
        if len(chosen) >= 3:
            break
    return {
        "schema_version": "empire.microsite.executive_research_portfolio.v1",
        "stage": "RESEARCH_ALLOCATION_ONLY",
        "research_desk_qualified_count": sum(
            x["executive_screen"]["research_desk_qualified"] for x in rows),
        "research_shortlist_max_three_markets": chosen,
        "unique_markets_in_shortlist": len(covered_markets),
        "publication_authorized": False,
        "commercial_budget_authorized": False,
        "verified_revenue_minor": None,
        "measured_search_volume": None,
        "next_review_trigger": "Independent original-source fact and exact first-party query evidence",
    }


_COVERAGE_JOBS = frozenset({
    "grant_eligibility", "funding_amount", "home_suitability",
    "local_support", "planning_lookup", "cost_comparison",
    "installer_selection", "consumer_decision_guidance",
})
_SOURCE_KINDS = frozenset({
    "government_service", "public_local_authority", "consumer_guide",
    "charity_research", "commercial_information",
})


def _competitive_screen(
    packet: Mapping[str, Any], dossier: Mapping[str, Any] | None,
    *, today: date,
) -> dict[str, Any]:
    """Compare documented public coverage, NEVER infer market gap or ROI.

    Descriptions are desk researcher observations. A valid URL and observation
    do not establish page content accuracy or unmet user demand.
    """
    result = {
        "schema_version": "empire.microsite.competitive_desk_screen.v1",
        "status": "COMPETITOR_COVERAGE_UNKNOWN",
        "desk_observations_only": True,
        "independently_verified_competitor_claims": False,
        "competitor_coverage_not_demand": True,
        "competitive_gap_verified": False,
        "unique_reader_value_verified": False,
        "customer_willingness_to_pay_verified": False,
        "underwritten_contribution_margin_minor": None,
        "break_even_leads": None,
        "source_count": 0,
        "covered_public_reader_jobs": [],
        "sources": [],
        "next_evidence_action": "Document actual alternative solutions for the same user job before claiming differentiation",
    }
    if dossier is None:
        return result
    if not isinstance(dossier, Mapping):
        raise ValueError("competitive desk row must be a mapping")
    expected={"candidate_id","market_id","keyword","observed_at","sources"}
    if set(dossier)!=expected:
        raise ValueError("competitive row fields must match exact original candidate scope")
    if (dossier["candidate_id"]!=packet["id"]
        or dossier["market_id"]!=packet["market"]["market_id"]
        or dossier["keyword"]!=packet["keyword"]["record"]["keyword"]):
        raise ValueError("competitive evidence candidate/market/keyword scope mismatch")
    try:
        checked=datetime.fromisoformat(dossier["observed_at"].replace("Z","+00:00"))
    except (ValueError,AttributeError) as exc:
        raise ValueError("invalid competitive observation timestamp") from exc
    if checked.tzinfo is None or not 0 <= (today-checked.date()).days <= 30:
        raise ValueError("competitive research needs a current time-aware desk observation")
    sources=dossier["sources"]
    if not isinstance(sources,list) or len(sources)>8:
        raise ValueError("competitive desk accepts zero to eight source observations")
    seen=set()
    urls=[]
    topics=set()
    for item in sources:
        if not isinstance(item,Mapping) or set(item)!={"url","publisher","kind","covered_jobs"}:
            raise ValueError("competitive source has invalid fields")
        u=item["url"]
        if not isinstance(u,str) or not 15<=len(u)<=450:
            raise ValueError("competitive source URL invalid")
        split=urlsplit(u)
        hostname=split.hostname
        if (split.scheme!="https" or not hostname or split.username is not None
            or split.password is not None or split.port is not None
            or split.query or split.fragment or split.path.startswith("//")
            or re.fullmatch(r"[a-z0-9.-]+",hostname) is None
            or "." not in hostname or hostname.endswith(".local")
            or hostname in ("localhost","127.0.0.1")):
            raise ValueError("competitive source must be a direct public HTTPS URL")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise ValueError("competitive source cannot be an IP address")
        if u in seen:
            raise ValueError("competitive source URL duplicated")
        seen.add(u)
        publisher=item["publisher"]
        if not isinstance(publisher,str) or not 2<=len(publisher.strip())<=120:
            raise ValueError("competitor publisher label invalid")
        kind=item["kind"]
        jobs=item["covered_jobs"]
        if (kind not in _SOURCE_KINDS
            or not isinstance(jobs,list) or not 1<=len(jobs)<=8
            or not all(isinstance(job,str) for job in jobs)
            or len(jobs)!=len(set(jobs)) or set(jobs)-_COVERAGE_JOBS):
            raise ValueError("unknown public reader job/category")
        topics.update(jobs)
        urls.append({"url":u,"publisher":publisher.strip(),"kind":kind,
                     "observed_jobs":sorted(jobs)})
    return dict(
        result,
        status=("ESTABLISHED_ALTERNATIVES_OBSERVED_DESK_ONLY" if len(urls)>=2
                else "ONE_ALTERNATIVE_OBSERVED_DESK_ONLY" if urls
                else "NO_ALTERNATIVES_RECORDED_NOT_PROOF_OF_GAP"),
        source_count=len(urls),
        covered_public_reader_jobs=sorted(topics),
        sources=urls,
        next_evidence_action=(
            "Investigate and evidence one user decision underserved by existing sources; "
            "no unverified feature-gap or willingness-to-pay claim"
            if urls else result["next_evidence_action"]
        ),
    )


def build_ranked_microsite_queue(
    specs: Sequence[Mapping[str, Any]], *,
    commercial: Mapping[str, Any],
    gsc: Mapping[str, Any] | None = None,
    calibration: Mapping[str, Any] | None = None,
    as_of: date | None = None,
    competitive: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    as_of = datetime.now(timezone.utc).date() if as_of is None else as_of
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be an exact research review date")
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

    if competitive is not None:
        if (not isinstance(competitive,Mapping)
            or set(competitive)!={"schema_version","mode","execution_authority",
                                   "custody","candidates"}
            or competitive["schema_version"]!="empire.microsite.competitive_desk.v1"
            or competitive["mode"]!="OBSERVE"
            or competitive["execution_authority"]!="none"
            or competitive["custody"]!="RESEARCHER_DESK_OBSERVATIONS_UNVERIFIED"
            or not isinstance(competitive["candidates"],list)):
            raise ValueError("competitive dossier cannot confer independent evidence or authority")
        comp_rows=competitive["candidates"]
        comp_by_id={x.get("candidate_id"):x for x in comp_rows if isinstance(x,Mapping)}
        if (len(comp_by_id)!=len(comp_rows) or set(comp_by_id)!=set(ids)
                or len(comp_rows)!=len(ids)):
            raise ValueError("competitive candidate identities must exactly match original queue")
    else:
        comp_by_id={}

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
        competitive_screen=_competitive_screen(packet,comp_by_id.get(ident),today=as_of)
        executive=_executive_screen(
            packet, exact_gsc=exact_gsc, buyer_guidance=buyer_guidance,
            calibrated=calibrated, today=as_of)
        if (executive["research_desk_qualified"]
                and competitive_screen["source_count"]>=2):
            executive["decision"]="VALIDATE_DIFFERENTIATED_READER_JOB"
            executive["next_best_evidence_action"]=competitive_screen["next_evidence_action"]
            executive["next_action_owner"]="Marketing Research"
        output.append({
            "candidate_id": ident,
            "market_id": packet["market"]["market_id"],
            "executive_screen": executive,
            "competitive_screen": competitive_screen,
            "commercial_underwriting": {
                "schema_version": "empire.microsite.commercial_underwriting_readiness.v1",
                "status": "BUYER_TERMS_AND_UNIT_ECONOMICS_UNVERIFIED",
                "original_buyer_coverage_guidance_only": buyer_guidance,
                "buyer_contract_accepted_for_exact_page": False,
                "billable_event_definition_verified": False,
                "consented_qualified_enquiry_to_buyer_join_verified": False,
                "independently_verified_payout_minor": None,
                "variable_fulfilment_cost_minor": None,
                "customer_acquisition_cost_minor": None,
                "net_contribution_minor": None,
                "break_even_conversion_rate": None,
                "next_commercial_validation": (
                    "Original commercial owner to verify exact buyer acceptance, "
                    "contract, payout, compliance, refund risk and fulfilment costs"
                ),
                "budget_authorized": False,
            },
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
        "executive_portfolio": _executive_portfolio(output),
        "calibrated_forecast_candidates": sum(row["model_outcome_calibration_verified"] for row in output),
        "publishable_count": 0,
        "provisional_research_points_not_roi": True,
        "owner_publication_authorized": False,
        "new_domains_created": 0,
        "database_writes": False,
        "outbound_sent": False,
        "rows": output,
    }
