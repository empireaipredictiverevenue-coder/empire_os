"""Read-only prospective multi-source cost-pressure and profitability scenarios.

Requires two explicitly sourced files: approved original BLS-owner observation
and an existing pilot/economic-twin owner's proposed what-if assumptions.
Never invent live data, run a collector, alter DB or activate campaigns.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from typing import Any

from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
from empire_os.predictive_multi_index_economics import review_multi_index_cost_pressure

BUNDLE_FIELDS=frozenset((
    "pilot","economic_plan","market","cost_basket","scenario_cases",
))


def _json(path_str:str,*,max_bytes:int=1_000_000)->Any:
    path=Path(path_str)
    try:
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=max_bytes:
            raise ValueError("unavailable file or unsafe file size")
        with path.open("r",encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError,ValueError,UnicodeError) as exc:
        raise ValueError("source-owner JSON unavailable/invalid") from exc


def main()->int:
    parser=argparse.ArgumentParser(description="Original-source BLS + Predictive economic twin cost-pressure instrument")
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--bls-owner-review",default=None)
    parser.add_argument("--hypothesis-bundle",default=None)
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    bls=review_bls_cost_index_owner(
        _json(args.bls_owner_review) if args.bls_owner_review else None,as_of=now,
    )
    base={
        "schema_version":"empire.predictive_revenue.cost_pressure_operator.v1",
        "mode":"OBSERVE","status":"COST_PRESSURE_SOURCE_OR_ASSUMPTIONS_NOT_CONNECTED",
        "bls_source_status":bls["status"],
        "bls_series_count":bls["series_observation_count"],
        "original_hypothesis_bundle_supplied":args.hypothesis_bundle is not None,
        "original_registered_forecast_claimed":False,
        "hypothetical_scenario_review":None,
        "live_observed_supplier_prices_authenticated":False,
        "simulation_applied_to_production":False,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
    if args.hypothesis_bundle:
        bundle=_json(args.hypothesis_bundle)
        if not isinstance(bundle,dict) or set(bundle)!=BUNDLE_FIELDS:
            raise SystemExit("UNTRUSTED_ECONOMIC_HYPOTHESIS_CONTRACT")
        if bls["status"]=="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED":
            results=review_multi_index_cost_pressure(
                bls,bundle["pilot"],bundle["economic_plan"],bundle["market"],
                cost_basket=bundle["cost_basket"],
                scenario_cases=bundle["scenario_cases"],
                as_of=now,
            )
            base["status"]="COST_PRESSURE_HYPOTHETICAL_SCENARIOS_REVIEWED"
            base["hypothetical_scenario_review"]=results
    print(json.dumps(base,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
