#!/usr/bin/env python3
"""Read-only original EmpireOS V4.21 external cash/forecast proof gap inventory.

Reads only pre-existing bounded local observer snapshots via the original
enterprise finance reviewer. No DB, network, customer rows, PII or writes.
Do not interpret the report as proof no external transactions exist.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from empire_os.enterprise_finance_evidence_readiness import (
    review_finance_source_readiness,
)

CANONICAL_ROOT=Path("/srv/empire_os")


def main(argv=None,*,repo_root=CANONICAL_ROOT)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({
            "status":"V421_EXPLICIT_READ_ONLY_REQUIRED",
            "commercial_authority":"none",
        },sort_keys=True))
        return 2
    try:
        observation=review_finance_source_readiness(Path(repo_root))
    except (ValueError,TypeError,OSError):
        print(json.dumps({
            "status":"V421_ORIGINAL_OBSERVATION_UNAVAILABLE_HELD",
            "commercial_authority":"none",
        },sort_keys=True))
        return 2
    proofs=observation["independent_finance_evidence_requirements"]
    pending=tuple(item["evidence_gap"] for item in proofs)
    result={
        "schema_version":"empire.predictive_revenue.v421.real_cash_proof_gaps.v1",
        "status":"V421_INDEPENDENT_REVENUE_AND_CALIBRATION_PROOF_HELD",
        "mode":"OBSERVE",
        "canonical_database":"EmpireDB",
        "original_finance_reader_schema":observation["schema_version"],
        "source_observation_status":observation["status"],
        "current_internal_observer_snapshot_count":observation[
            "current_internal_source_snapshot_count"],
        "independent_proof_categories_not_admitted":len(pending),
        "missing_proof_codes":pending,
        "source_licence_and_consent_covered":False,
        "complete_inbound_opportunity_census_verified":False,
        "independent_cash_clearing_and_refund_finality_verified":False,
        "complete_external_bank_statement_inventory_verified":False,
        "genuine_pre_outcome_forecast_timestamp_verified":False,
        "verified_cvr_ecac_live":False,
        "verified_30_60_90_cash_forecasts":None,
        "eligible_cash_training_examples":0,
        "production_model_weights_updated":False,
        "customer_report_distribution_authorized":False,
        "new_external_statement_sources_queried":False,
        "production_db_read_or_write_performed":False,
        "money_moved":False,
        "execution_authority":"none",
    }
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
