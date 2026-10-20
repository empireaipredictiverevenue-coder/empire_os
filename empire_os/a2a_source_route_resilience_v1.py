"""Live source status routing for the A2A miner.

Does not call any network service or self-certify provider capability.
Source health is separated from actual first-party evidence and true buyers.
"""
from __future__ import annotations
from typing import Any, Mapping

SCHEMA="empire.a2a.public_source_operational_routing.v1"


def build_source_route_board(
    first_party: Mapping[str, Any],
    mining: Mapping[str, Any],
    openmanus: Mapping[str, Any],
    agent_reach_doctor: Mapping[str, Any] | None = None,
    official_permit_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if (not isinstance(first_party, Mapping)
            or first_party.get("schema_version") != "empire.a2a.first_party_source_recovery_review.v1"
            or first_party.get("execution_authority") != "NONE"
            or first_party.get("new_verified_sales_leads") != 0
            or first_party.get("outbound_sent") != 0):
        raise ValueError("UNTRUSTED_FIRST_PARTY_ROUTE_SOURCE")
    if (not isinstance(mining, Mapping)
            or mining.get("schema_version") != "empire.a2a.public_business_evidence_mining.v1"
            or mining.get("execution_authority") != "NONE"
            or mining.get("verified_real_lead_count") != 0):
        raise ValueError("UNTRUSTED_PUBLIC_MINING_ROUTE_SOURCE")
    if (not isinstance(openmanus, Mapping)
            or openmanus.get("schema_version") != "empire.a2a.openmanus_scoped_owner_research_plan.v1"
            or openmanus.get("execution_authority") != "NONE"
            or openmanus.get("jobs_executed") != 0
            or openmanus.get("production_jobs_dispatched") != 0):
        raise ValueError("UNTRUSTED_EXECUTOR_SCOPE")
    if agent_reach_doctor is not None and not isinstance(agent_reach_doctor, Mapping):
        raise ValueError("INVALID_AGENT_REACH_HEALTH")
    health = (agent_reach_doctor or {}).get("doctor") or {}
    if not isinstance(health, Mapping):
        raise ValueError("INVALID_AGENT_REACH_CHANNELS")
    if official_permit_review is not None and (
            not isinstance(official_permit_review, Mapping)
            or official_permit_review.get("schema_version") !=
                "empire.a2a.official_permit_buyer_scout_owner_review.v1"
            or official_permit_review.get("execution_authority") != "NONE"
            or official_permit_review.get("verified_hvac_lead_buyers") != 0
            or official_permit_review.get("owner_tasks_dispatched") != 0):
        raise ValueError("UNTRUSTED_OFFICIAL_PERMIT_REVIEW")
    routes=[]
    sites=first_party.get("market_coverage")
    if not isinstance(sites, Mapping):
        raise ValueError("MISSING_FIRST_PARTY_MARKETS")
    source_cache_state=first_party.get("source_state")
    fresh=(source_cache_state == "CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS")
    for market,sector in (("tampa, fl","roofing"),("little rock, ar","hvac"),("nyc","general_contractor")):
        row=sites.get(market)
        if not isinstance(row, Mapping) or row.get("sector") != sector:
            raise ValueError("MARKET_COVERAGE_CLAIM_MISMATCH")
        count=row.get("successful_site_reads")
        scraped=row.get("self_described_sector_and_region_matches")
        if type(count) is not int or not 0 <= count <= 9 or type(scraped) is not int or not 0 <= scraped <= count:
            raise ValueError("INVALID_FIRST_PARTY_SOURCE_COUNTS")
        routes.append({
            "market":market,"sector":sector,
            "first_party_reads_verified_by_local_collector": count if fresh else None,
            "crawl4ai_offline_extractions_from_cached_reads": (
                sum(1 for r in first_party.get("source_records",[])
                    if isinstance(r, Mapping) and r.get("market")==market
                    and r.get("crawl4ai_offline_markdown_extracted") is True)
                if fresh else None
            ),
            "scrapling_structured_extractions_from_cached_reads": (
                sum(1 for r in first_party.get("source_records",[])
                    if isinstance(r, Mapping) and r.get("market")==market
                    and r.get("scrapling_structured_page_parsed") is True)
                if fresh else None
            ),
            "first_party_route": "AVAILABLE_SOURCE_EVIDENCE_NOT_BUYERS" if count>0 and fresh else
                                  "NO_RECENT_SUCCESSFUL_APPROVED_SOURCES",
            "general_search_route": "PROVIDER_HEALTH_UNVERIFIED",
            "official_permit_source_businesses_for_review": (
                official_permit_review.get("businesses_for_owner_review_count")
                if market == "little rock, ar" and official_permit_review else None
            ),
            "official_permit_source_is_current_demand": False,
            "actual_local_buyers_verified": 0,
            "owner_next_action": "BUYER_SCOUT_INDEPENDENT_GEO_AND_COMMERCIAL_NEED_VALIDATION",
        })
    provider_status = mining.get("public_provider_fresh_search_status")
    if not isinstance(provider_status, str) or len(provider_status)>160:
        provider_status="UNVERIFIED"
    channels={}
    for key in ("rss","web","reddit","linkedin","facebook","instagram"):
        row=health.get(key)
        channel_state=(row.get("status") if isinstance(row, Mapping) else None)
        channels[key]={
            "doctor_reported_status":channel_state if channel_state in ("ok","warn","off") else "not_checked",
            "live_query_success_proven_in_this_cycle":False,
            "social_account_connection_authorized":False if key in ("reddit","linkedin","facebook","instagram") else None,
        }
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"NONE",
        "source_route_policy":"PREFER_APPROVED_FIRST_PARTY_THEN_EXISTING_OWNER_PUBLIC_RSS; HOLD_DEGRADED_SEARCH",
        "source_routes":routes,
        "first_party_source_state":source_cache_state if isinstance(source_cache_state,str) else "UNKNOWN",
        "owner_public_search_provider_status":provider_status,
        "official_permit_source_state": (
            official_permit_review.get("source_state") if official_permit_review else "NOT_CONNECTED"
        ),
        "keyless_search_restored":False,
        "paid_search_provider_authorized_by_this_plan":False,
        "agent_reach_doctor":channels,
        "agent_reach_health_is_not_independent_live_query_proof":True,
        "browser_use_production_executor_verified":False,
        "openhands_production_execution_verified":False,
        "openhands_intended_role":"DISPOSABLE_CODE_WORKSPACE_NOT_PUBLIC_LEAD_SCRAPING",
        "openmanus_planned_jobs_not_executed":openmanus.get("jobs_prepared"),
        "browser_use_source_login_or_antibot_bypass_allowed":False,
        "new_verified_leads":0,"new_customer_records":0,"outbound_messages":0,
        "next_owner":"existing_search_fabric_and_buyer_scout_owners",
    }
