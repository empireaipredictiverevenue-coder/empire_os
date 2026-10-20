"""Four-step commercial cost/price/original-forecast readiness — no writes.

Existing finance owner snapshots are inspected without database access. An
explicit source-owner bundle can be evaluated under the strict four-stage
research contract; no file is ever created or updated by this operator.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.enterprise_finance_evidence_readiness import (
    review_finance_source_readiness,
)
from empire_os.predictive_four_stage_economic_custody import (
    review_four_stage_cost_price_forecast_custody,
)
from empire_os.predictive_original_profit_forecast_preflight import (
    prepare_original_profit_forecast_preflight,
)

REQUIRED=frozenset(("pilot","materials","operations","selling_price"))
OPTIONAL=frozenset((
    "economic_plan","commerce_owner_review","original_quant_candidate",
    "registry_receipt","registry_readback",
))


def _bundle(location:str)->dict:
    path=Path(location)
    try:
        if (path.is_symlink() or not path.is_file()
                or not 0<path.stat().st_size<=1_000_000):
            raise ValueError("owner packet missing/oversized")
        with path.open("r",encoding="utf-8") as handle:
            values=json.load(handle)
        if not isinstance(values,dict) or not REQUIRED<=set(values) or set(values)-REQUIRED-OPTIONAL:
            raise ValueError("unknown or absent owner packet keys")
        return values
    except (OSError,UnicodeError,ValueError) as exc:
        raise ValueError("approved existing source-owner bundle required") from exc


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--owner-evidence-bundle",default=None,
                        help="Explicit typed materials, labour, price and Quant owner research JSON")
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    finance=review_finance_source_readiness(Path(args.repo_root),as_of=now)
    evidence=None
    profit_forecast_preflight=None
    if args.owner_evidence_bundle:
        obj=_bundle(args.owner_evidence_bundle)
        evidence=review_four_stage_cost_price_forecast_custody(
            obj["pilot"],obj["materials"],obj["operations"],obj["selling_price"],
            commerce_owner_review=obj.get("commerce_owner_review"),
            original_quant_candidate=obj.get("original_quant_candidate"),
            registry_receipt=obj.get("registry_receipt"),
            registry_readback=obj.get("registry_readback"),as_of=now,
        )
        if "economic_plan" in obj:
            profit_forecast_preflight=prepare_original_profit_forecast_preflight(
                obj["pilot"],obj["economic_plan"],evidence,as_of=now,
            )
    out={
        "schema_version":"empire.predictive_revenue.four_stage_economic_operator.v1",
        "mode":"OBSERVE",
        "status":"FOUR_STAGE_SOURCE_PROOFS_AWAIT_ORIGINAL_OWNER_EVIDENCE"
            if evidence is None else "FOUR_STAGE_OWNER_CLAIM_RESEARCH_REVIEWED",
        "live_finance_owner_snapshot_status":finance["status"],
        "finance_original_proof_requirements_open_count":finance[
            "required_proofs_not_admitted_count"],
        "finance_sources_fresh_count":finance[
            "current_internal_source_snapshot_count"],
        "finance_canonical_single_event_reader_source_status":finance[
            "single_event_reader_repository_prerequisites"]["status"],
        "independently_authenticated_financial_money_movement":finance[
            "independent_money_movement_proof_obtained"],
        "canonical_finance_database_queried":finance["empiredb_reads_performed"],
        "source_owner_bundle_supplied":args.owner_evidence_bundle is not None,
        "four_stage_cost_and_forecast_review":evidence,
        "original_profit_forecast_registration_preflight":profit_forecast_preflight,
        "original_profit_forecast_durably_registered":False,
        "profit_registry_has_independent_readback":False,
        "verified_supplier_invoice_coverage":None,
        "verified_local_labor_and_delivery_cost_coverage":None,
        "verified_accepted_price_and_settlement_coverage":None,
        "quant_prospectively_registered_forecast_coverage":None,
        "first_party_unit_level_gross_profit_accuracy":None,
        "cloud_financial_optimization_eligible":False,
        "next_program":"PREDICTIVE_CLOUD_AFTER_VERIFIED_COST_PRICE_AND_FORECAST_CUSTODY",
        "external_service_or_api_called":False,
        "original_finance_or_quant_db_modified":False,
        "commercial_actions_dispatched":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
    print(json.dumps(out,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
