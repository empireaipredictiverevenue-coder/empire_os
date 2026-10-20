"""Read-only prospective multi-source cost-pressure and profitability scenarios.

Original economic scenarios require approved BLS-owner input and an existing
owner's hypotheses. An explicit opt-in BLS v1 HTTPS probe can inspect one
pinned public source but cannot authorise it for profit scenario calibration.
Never invent a financial outcome, schedule a collector or modify production.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from typing import Any

from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
from empire_os.predictive_bls_public_probe import (
    probe_bls_public_v1, probe_bls_sector_public_v1,
)
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
    parser.add_argument("--probe-official-bls-v1",action="store_true",
                        help="One explicit official BLS public GET; does not approve source for profit scenarios")
    parser.add_argument("--probe-sector-bls-v1",action="store_true",
                        help="Four separate official BLS public research GETs; roofing/HVAC/electrical/concrete")
    args=parser.parse_args()
    if (int(args.probe_official_bls_v1)+int(args.probe_sector_bls_v1)
            +int(bool(args.bls_owner_review)))>1:
        parser.error("Choose only one BLS owner packet, single-series probe, or sector basket")
    now=datetime.now(timezone.utc)
    bls=review_bls_cost_index_owner(
        _json(args.bls_owner_review) if args.bls_owner_review else None,as_of=now,
    )
    public_probe=probe_bls_public_v1(as_of=now) if args.probe_official_bls_v1 else None
    sector_probe=probe_bls_sector_public_v1(as_of=now) if args.probe_sector_bls_v1 else None
    base={
        "schema_version":"empire.predictive_revenue.cost_pressure_operator.v1",
        "mode":"OBSERVE","status":"COST_PRESSURE_SOURCE_OR_ASSUMPTIONS_NOT_CONNECTED",
        "bls_source_status":bls["status"],
        "official_bls_public_research_probe":public_probe,
        "official_bls_sector_research_probe":sector_probe,
        "public_research_source_is_finance_owner_approved":False,
        "bls_series_count":bls["series_observation_count"],
        "original_hypothesis_bundle_supplied":args.hypothesis_bundle is not None,
        "original_registered_forecast_claimed":False,
        "hypothetical_scenario_review":None,
        "live_observed_supplier_prices_authenticated":False,
        "simulation_applied_to_production":False,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
    if (public_probe is not None and public_probe.get("status")
            == "BLS_PUBLIC_MONTHLY_INDEX_OBSERVED_RESEARCH_ONLY"):
        base["status"]="OFFICIAL_BLS_PUBLIC_RESEARCH_OBSERVED_OWNER_APPROVAL_REQUIRED"
    if sector_probe is not None:
        base["status"]=("OFFICIAL_BLS_SECTOR_RESEARCH_OBSERVED_OWNER_APPROVAL_REQUIRED"
                        if sector_probe["status"]=="BLS_SECTOR_PUBLIC_RESEARCH_REVIEWED"
                        else "OFFICIAL_BLS_SECTOR_RESEARCH_PARTIAL_SOURCE_HOLD")
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
