"""Predictive Revenue gap diagnostics: source freshness + comparable what-if economics.

Every owner source is read-only. Unverified data is shown as held/unknown.
Hypothesis bundles are explicit original-owner assumptions, not a real-world
opportunity generator or purchase authorization.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from empire_os.predictive_funnel_gap_instrument import (
    review_commercial_funnel_gap_runtime,
)
from empire_os.predictive_market_evidence_binding import (
    review_revenue_gps_territory_evidence_runtime,
)
from empire_os.predictive_storm_measurement import (
    review_storm_measurement_runtime,
)
from empire_os.permit_project_intelligence import (
    analyze_permit_project_intelligence,
)
from empire_os.predictive_primary_source_economic_bridge import (
    review_existing_permit_owner,
)
from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
from empire_os.predictive_structural_revenue_gaps import (
    review_structural_market_revenue_gaps,
)


def _input(pathname:str)->dict:
    p=Path(pathname)
    if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=1_000_000:
        raise ValueError("approved owner hypothesis/source JSON file unavailable")
    with p.open("r",encoding="utf-8") as f:
        obj=json.load(f)
    if not isinstance(obj,dict):
        raise ValueError("owner input must be a plain object")
    return obj


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",required=True,action="store_true")
    p.add_argument("--repo-root",default="/srv/empire_os")
    p.add_argument("--hypothesis-bundle",default=None,
                   help="Original reviewed pilot, economics, market and interventions")
    p.add_argument("--bls-owner-review",default=None,
                   help="Already reviewed original BLS economic source JSON")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    funnel=review_commercial_funnel_gap_runtime(args.repo_root,as_of=now)
    market=review_revenue_gps_territory_evidence_runtime(args.repo_root,as_of=now)
    storm=review_storm_measurement_runtime(args.repo_root,as_of=now)
    permit=review_existing_permit_owner(
        analyze_permit_project_intelligence(args.repo_root,now=now),as_of=now,
    )
    bls=review_bls_cost_index_owner(
        _input(args.bls_owner_review) if args.bls_owner_review else None,as_of=now,
    )
    gap=None
    if args.hypothesis_bundle:
        bundle=_input(args.hypothesis_bundle)
        if set(bundle)!=frozenset((
            "pilot","economic_plan","market","interventions"
        )):
            raise ValueError("exact owner hypothesis bundle keys required")
        gap=review_structural_market_revenue_gaps(
            bundle["pilot"],bundle["economic_plan"],bundle["market"],
            bundle["interventions"],as_of=now,
        )
    output={
        "schema_version":"empire.predictive_revenue.gap_research_operator.v1",
        "status":"MARKET_AND_REVENUE_GAP_SOURCE_READINESS_REVIEWED",
        "mode":"OBSERVE",
        "source_reviewed_at":now.isoformat(),
        "funnel_original_owner":funnel,
        "market_gps_research_source_status":market.get("status"),
        "market_gps_research_market_count":market.get("market_count"),
        "market_gps_revision_sha256":market.get("source_revision_fingerprint"),
        "storm_original_owner_status":storm.get("status"),
        "storm_source_age_hours":storm.get("source_age_hours"),
        "permit_original_owner":permit,
        "bls_original_owner_status":bls.get("status"),
        "bls_series_count":bls.get("series_observation_count"),
        "original_hypothesis_bundle_supplied":args.hypothesis_bundle is not None,
        "structural_revenue_gap_hypothesis":gap,
        "gap_causal_attribution_completed":False,
        "independent_real_world_money_gap_quantified":False,
        "owner_source_epochs_are_atomic_one_cohort":False,
        "new_commercial_playbook_triggered":False,
        "executed_cash_or_customer_actions":False,
        "original_quant_forecast_registered":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
    print(json.dumps(output,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
