"""Read-only owner snapshot coverage for Market Economic Digital Twin.

Provides freshness and provenance boundaries only. It does not merge
unrelated markets, activate sources, infer actual buyer need, or use founder
policy-scenario price as paid customer willingness-to-pay.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import _time

SCHEMA="empire.predictive_revenue.market_economic_source_readiness.v1"
SOURCES={
    "market_gps":(
        "runtime/market_sweeps/revenue_gps_latest.json",
        "empire.market_sweep_revenue_gps.v1",timedelta(hours=8),
    ),
    "competitor_intelligence":(
        "runtime/competitive_intelligence/competitor_intelligence_feed_latest.json",
        "empire.competitor_intelligence_feed.v1",timedelta(days=3),
    ),
    "storm_opportunity":(
        "runtime/storm_opportunity/latest.json",
        "empire.storm_opportunity_snapshot.v1",timedelta(hours=24),
    ),
}
MAX_BYTES=3_000_000


def review_market_economic_source_readiness(
    sources:Mapping[str,Mapping[str,Any] | None], *,as_of:datetime,
) -> dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("source freshness needs aware clock")
    if not isinstance(sources,Mapping) or set(sources)!=set(SOURCES):
        raise ValueError("exact existing market-source owners required")
    now=as_of.astimezone(timezone.utc)
    rows={}
    for name,(_path,schema,max_age) in SOURCES.items():
        source=sources[name]
        state="MISSING"
        observed_age=None
        count=None
        research_signals=None
        policy_scenario=None
        if source is not None:
            if (not isinstance(source,Mapping)
                    or source.get("schema_version")!=schema
                    or source.get("mode")!="OBSERVE"
                    or source.get("execution_authority")!="none"):
                state="SOURCE_CONTRACT_HOLD"
            else:
                try:
                    stamp=_time(source.get("generated_at"))
                except ValueError:
                    state="SOURCE_TIME_HOLD"
                else:
                    elapsed=now-stamp
                    observed_age=int(elapsed.total_seconds())
                    if not timedelta(0)<=elapsed<=max_age:
                        state="STALE_OR_FUTURE_HOLD"
                    elif name=="market_gps":
                        n=source.get("market_count")
                        research=source.get("competitive_evidence_market_count")
                        commerce=source.get("commercial_demand_market_count")
                        scenario=source.get("verified_product_economics")
                        if (type(n) is not int or not 0<=n<=10000
                                or type(research) is not int or not 0<=research<=n
                                or type(commerce) is not int or not 0<=commerce<=n
                                or source.get("buyer_intent_inferred") is not False
                                or source.get("revenue_inferred") is not False
                                or source.get("outreach_enabled") is not False
                                or not isinstance(scenario,Mapping)
                                or scenario.get("economics_kind")!="founder_policy_scenario"
                                or scenario.get("prediction") is not False
                                or scenario.get("actual_cost_observed") is not False
                                or scenario.get("actual_revenue") is not False):
                            state="SOURCE_CLAIMS_HOLD"
                        else:
                            state="RESEARCH_COVERAGE_FRESH_NOT_COMMERCIAL_PROOF"
                            count=n
                            research_signals=research
                            policy_scenario=True
                    elif name=="competitor_intelligence":
                        n=source.get("canonical_company_count")
                        if (type(n) is not int or not 0<=n<=10000
                                or source.get("buyer_intent_inferred") is not False
                                or source.get("revenue_opportunity_inferred") is not False
                                or source.get("outreach_enabled") is not False):
                            state="SOURCE_CLAIMS_HOLD"
                        else:
                            state="RESEARCH_COVERAGE_FRESH_NOT_COMMERCIAL_PROOF"
                            count=n
                    else:
                        n=source.get("candidate_count")
                        if (type(n) is not int or not 0<=n<=10000
                                or source.get("automatic_external_execution_allowed") is not False
                                or source.get("damage_inferred") is not False
                                or source.get("demand_inferred") is not False
                                or source.get("economics_inferred") is not False
                                or source.get("outreach_authority")!="none"
                                or source.get("payment_authority")!="none"):
                            state="SOURCE_CLAIMS_HOLD"
                        else:
                            state="RESEARCH_COVERAGE_FRESH_NOT_COMMERCIAL_PROOF"
                            count=n
        rows[name]={
            "source_owner":name,
            "status":state,
            "age_seconds":observed_age,
            "observed_research_entities_or_markets":count,
            "competitor_evidence_market_count":research_signals,
            "founder_policy_price_and_cost_are_not_actuals":policy_scenario,
            "current_market_scope_matches_pilot":False,
            "verified_customer_purchases":None,
            "geographic_buying_capacity_authenticated":False,
            "may_calibrate_market_shock":False,
        }
    fresh=sum(v["status"]=="RESEARCH_COVERAGE_FRESH_NOT_COMMERCIAL_PROOF"
              for v in rows.values())
    return {
        "schema_version":SCHEMA,"status":"SOURCE_OWNER_MARKET_CONTEXT_REVIEWED",
        "mode":"OBSERVE", "fresh_research_owner_count":fresh,
        "source_count":len(rows),
        "sources":rows,
        "original_source_revision_bound_to_pilot":False,
        "product_market_price_authenticated":False,
        "real_storm_damage_or_demand_authenticated":False,
        "simulated_economic_twin_calibrated":False,
        "economic_playbook_production_authorized":False,
        "next_owner":"market_source_spatial_and_strategy_owners",
        "next_action":"BIND_LICENCED_TERRITORY_SPECIFIC_OBSERVATIONS_AND_REAL_PURCHASE_COST_RECEIPTS",
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }


def review_market_economic_source_readiness_runtime(
    repo_root:str | Path, *,as_of:datetime,
) -> dict[str,Any]:
    root=Path(repo_root).resolve()
    sources={}
    for name,(rel,_schema,_age) in SOURCES.items():
        file=root/rel
        try:
            if ((root/"runtime").is_symlink()
                    or file.parent.is_symlink()
                    or file.is_symlink()
                    or not file.is_file()
                    or not 0<file.stat().st_size<=MAX_BYTES):
                sources[name]=None
                continue
            raw=json.loads(file.read_text(encoding="utf-8"))
            sources[name]=raw
        except (OSError,ValueError,UnicodeError):
            sources[name]=None
    return review_market_economic_source_readiness(sources,as_of=as_of)
