"""Meta Muse research intelligence: video-guided prompts + canonical Exchange gaps.

All market priorities are *research* estimates from a bounded, OBSERVE-only
Exchange selection, never demand probability, verified buyers or personal leads.
No social collection, contact, DB writes or paid search is performed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone, timedelta
from typing import Any
import re

SCHEMA = "empire.meta_market_priority_intelligence.v1"
SOURCE_VIDEO = "https://www.youtube.com/watch?v=tpZOU1ugODQ"
ALLOWED = {
    ("blocked_missing_evidence", "market_identity_missing"): "MARKET_IDENTITY",
    ("blocked_missing_evidence", "missing_active_identity_link"): "IDENTITY_LINK",
    ("overflow_no_capacity", "no_eligible_buyer_capacity"): "BUYER_CAPACITY",
}
ROUTE = re.compile(r"^corridor:v1:[a-z_]{3,40}:[a-z0-9_]{2,90}:qualified_lead:lead$")
MARKET = re.compile(r"^[a-z0-9][a-z0-9 ,.'()-]{1,95}$")
NICHE = re.compile(r"^[a-z][a-z0-9_ ]{2,50}$")
MAX_ROWS = 1000


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "state": "HOLD",
        "reason": reason,
        "reviewed_selection_rows": 0,
        "ranked_non_solar_markets": [],
        "verified_payable_buyers": 0,
        "saleable_person_leads": 0,
        "customer_outreach_authorized": False,
        "data_written_to_crm": False,
    }


def build_video_research_prompts(*, niche: str, market: str) -> list[dict[str, str]]:
    """Original EmpireOS prompt adaptations, NOT verbatim video prompts.

    All returned text is internal instructions. A prompt must not be construed
    as permission for unauthorised Meta or personal-profile data access.
    """
    if not NICHE.fullmatch(niche) or not MARKET.fullmatch(market):
        raise ValueError("invalid_public_market_scope")
    base = f"Sector={niche}; city/market={market}. "
    guard = (
        "Use only pre-authorised public aggregate observations and licensed "
        "business sources; verify provenance/usage rights and freshness. "
        "Never harvest individual contacts, private groups, profiles, DMs "
        "or unconsented posts. Do not send, scrape, publish or spend. "
        "Unknown facts stay UNKNOWN; return source receipts and review holds."
    )
    specs = (
        ("01_NICHE_CITY_RULES", "04:33", "Define local niche, provider admission criteria, exact city and legitimate buyer requirements."),
        ("02_EXPLICIT_GROUP_RESEARCH", "13:46", "Specifically investigate which relevant Facebook Group TOPICS could signal aggregate demand. Do not enter or extract private groups; record only permitted sources and access rights."),
        ("03_MARKETPLACE_AND_INSTAGRAM", "15:19", "Where permitted, compare aggregate Marketplace categories and Instagram professional business supply, geography, trust signals and gaps. No follower, member or seller-person harvesting."),
        ("04_CLEAN_INDEPENDENT_SOURCES", "06:51", "Deduplicate by canonical source/corridor, check independent corroboration, distinguish listings from willing providers and source observations from opted-in enquiries."),
        ("05_OWNED_DISTRIBUTION", "17:20", "Design an owned niche page or first-party opt-in landing page with clear consent, buyer recipient, privacy and attribution. Draft only; publish after explicit approval."),
        ("06_COMMERCIAL_SOFTWARE_LOOP", "17:20", "Specify the smallest repeatable product only after accepted buyer capacity, genuine opt-ins, acknowledged delivery, disputed-event handling, independent settled payments and measured net margin."),
    )
    return [
        {"id":id, "video_time_reference":time,
         "source_video":SOURCE_VIDEO, "verbatim_creator_prompt":False,
         "prompt":base + instruction + " " + guard,
         "execution_authority":"NONE"}
        for id,time,instruction in specs
    ]


def rank_exchange_research_gaps(snapshot: Mapping[str, Any] | None,
                                *, now: datetime | None = None,
                                exclude_niches: tuple[str, ...] = ("solar",),
                                top_n: int = 12) -> dict[str, Any]:
    """Inspect every selected row, emit aggregates only, fail closed on drift."""
    if not isinstance(snapshot, Mapping):
        return _hold("no_canonical_selection_supplied")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    if not 1 <= top_n <= 20:
        return _hold("unbounded_market_preview")
    if (snapshot.get("schema_version") != "empire.commercial_exchange_snapshot.v1"
        or snapshot.get("source") != "canonical_empiredb_projection"
        or snapshot.get("canonical_backend") != "empiredb"
        or snapshot.get("mode") != "OBSERVE"
        or snapshot.get("execution_authority") != "none"
        or snapshot.get("automatic_external_delivery") is not False):
        return _hold("untrusted_canonical_selection_shape")
    observed = snapshot.get("observed_at")
    try:
        stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("naive")
    except (ValueError, TypeError, AttributeError):
        return _hold("untrusted_source_observation_time")
    if not current-timedelta(hours=6) <= stamp <= current+timedelta(minutes=5):
        return _hold("stale_or_future_canonical_selection")

    rows=snapshot.get("inventory")
    seats=snapshot.get("buyer_seats")
    if (not isinstance(rows, list) or not isinstance(seats, list)
        or len(rows)>MAX_ROWS or len(seats)>3000
        or type(snapshot.get("inventory_count")) is not int
        or len(rows)!=snapshot["inventory_count"]
        or type(snapshot.get("buyer_seat_count")) is not int
        or len(seats)!=snapshot["buyer_seat_count"]):
        return _hold("source_counts_or_bounds_invalid")
    if snapshot.get("allocation_candidate_count")!=0 or snapshot.get("allocated_count")!=0:
        return _hold("unexpected_commercial_allocation_state")
    if any(not isinstance(s, Mapping) or s.get("seat_state")!="blocked_missing_evidence"
           for s in seats):
        return _hold("active_or_unreviewed_buyer_seat_state")

    observed_ids=set()
    grouped:dict[tuple[str,str,str],Counter]=defaultdict(Counter)
    reasons=Counter()
    excluded=Counter()
    unknown=Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            return _hold("invalid_selection_row")
        identity=row.get("prospect_id")
        if not isinstance(identity,str) or not 1<=len(identity)<=128 or identity in observed_ids:
            return _hold("duplicate_or_missing_selection_identity")
        observed_ids.add(identity)
        blocker=ALLOWED.get((row.get("state"),row.get("reason")))
        if blocker is None:
            return _hold("unreviewed_selection_state")
        reasons[blocker]+=1
        niche=row.get("niche_family")
        market=row.get("metro")
        corridor=row.get("corridor_key")
        if niche in exclude_niches:
            excluded[niche]+=1
            continue
        if (not isinstance(niche,str) or not NICHE.fullmatch(niche)
            or not isinstance(market,str) or not MARKET.fullmatch(market)
            or not isinstance(corridor,str) or not ROUTE.fullmatch(corridor)):
            unknown[blocker]+=1
            continue
        grouped[(niche,market,corridor)][blocker]+=1
    if sum(reasons.values()) != len(rows):
        return _hold("unaccounted_for_source_selection_rows")
    if (reasons["MARKET_IDENTITY"]+reasons["IDENTITY_LINK"] !=
            snapshot.get("blocked_missing_evidence_count")
            or reasons["BUYER_CAPACITY"] != snapshot.get("overflow_count")):
        return _hold("canonical_source_blocker_counts_drift")
    if (snapshot.get("seat_state_counts") != {"blocked_missing_evidence":len(seats)}):
        return _hold("buyer_seat_state_counts_drift")

    markets=[]
    for (niche,market,corridor),count in grouped.items():
        # Bigger *existing* buyer-capacity gaps are priorities to investigate.
        # The number is NOT a purchasing propensity or predictive forecast.
        cap=count["BUYER_CAPACITY"]
        identity=count["IDENTITY_LINK"]
        scope=count["MARKET_IDENTITY"]
        level="BUYER_CAPACITY" if cap else "IDENTITY_LINK" if identity else "MARKET_IDENTITY"
        markets.append({
            "niche":niche,"market":market,"corridor":corridor,
            "selected_research_rows":sum(count.values()),
            "buyer_capacity_blocked_rows":cap,
            "canonical_identity_blocked_rows":identity,
            "market_identity_blocked_rows":scope,
            "research_priority_points_not_demand_score":5*cap+2*identity+scope,
            "first_owner":"existing_sales_exchange" if cap else "existing_crm_identity",
            "next_research_question":(
                "WHO_IS_A_REAL_CONTRACTED_PAYING_BUYER_FOR_THIS_EXACT_TERRITORY?"
                if cap else "WHICH_ORIGINAL_CANONICAL_ENTITY_AND_SOURCE_RIGHTS_ARE_MISSING?"
            ),
            "matched_zip_or_provider_willingness_proven":False,
            "paying_buyer_or_transfer_rights_proven":False,
            "recommended_video_prompts":[
                "01_NICHE_CITY_RULES", "02_EXPLICIT_GROUP_RESEARCH",
                "04_CLEAN_INDEPENDENT_SOURCES",
            ],
            "outreach_authorized":False,
        })
    markets.sort(key=lambda x:(
        -x["research_priority_points_not_demand_score"],
        -x["selected_research_rows"], x["niche"],x["market"],
    ))
    return {
        "schema_version":SCHEMA,
        "state":"BOUNDED_RESEARCH_PRIORITIES_NO_COMMERCIAL_PROMOTION",
        "source_snapshot_at":observed,
        "reviewed_selection_rows":len(rows),
        "distinct_selected_ids_checked":len(observed_ids),
        "blocker_counts":dict(sorted(reasons.items())),
        "excluded_delegated_niches":dict(sorted(excluded.items())),
        "unknown_market_rows":sum(unknown.values()),
        "market_groups_checked":len(markets),
        "ranked_non_solar_markets":markets[:top_n],
        "rank_is_research_priority_not_buyer_probability":True,
        "independent_source_rights_verified":False,
        "verified_payable_buyers":0,
        "saleable_person_leads":0,
        "customer_outreach_authorized":False,
        "data_written_to_crm":False,
    }
