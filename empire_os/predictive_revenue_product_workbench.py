"""Product-level integration of existing EmpireOS Predictive Revenue capabilities.

Not a new OS, database, agent, product code, pricing tier or orchestrator.
This is a read-only product workbench on the existing Founder Console/demo
API. A file being present is never verified commercial evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.predictive_revenue_products import predictive_revenue_product
from empire_os.predictive_revenue_demo import _read_json, _source_state
from empire_os.predictive_revenue_diagnostic_intelligence import (
    review_predictive_revenue_diagnostics,
)

SUPPORTED = frozenset({
    "predictive_revenue_diagnostic", "predictive_revenue_intelligence_os",
})

# Existing OS source keys, not new data sources or runtimes.
OS_CAPABILITY_SOURCES: dict[str, tuple[str, ...]] = {
    "revenue_truth_review": ("revenue_pulse",),
    "pipeline_and_conversion_analysis": ("revenue_pulse", "revenue_os"),
    "forecast_readiness": ("predictive_cloud",),
    "revenue_leakage_analysis": ("revenue_pulse", "economic_memory"),
    "market_opportunity_review": ("opportunity_loop",),
    "priority_action_plan": ("astra",),
    "predictive_revenue_command_center": (
        "revenue_os", "predictive_cloud", "revenue_pulse",
    ),
    "market_and_demand_intelligence": ("opportunity_loop",),
    "customer_and_buyer_intelligence": ("buyer_acquisition",),
    "search_attention_intelligence": ("predictive_cloud",),
    "conversion_intelligence": ("predictive_intelligence",),
    "ltv_and_retention_evidence": ("economic_memory",),
    "revenue_truth": ("revenue_pulse",),
    "economic_memory": ("economic_memory",),
    "prediction_vs_actual_calibration": (
        "predictive_intelligence", "economic_memory",
    ),
}

# Presence of these sources signals only that EmpireOS generated a read model.
# It must never be treated as certification of a customer-specific metric.
FORECAST_SOURCE="runtime/predictive_intelligence/latest.json"


def build_predictive_revenue_product_workbench(
    root: Path, *, product_code: str="predictive_revenue_diagnostic",
    as_of: datetime | None=None,
) -> dict[str, Any]:
    product=predictive_revenue_product(product_code)
    if product.product_code not in SUPPORTED:
        raise ValueError("product workbench supports Diagnostic and Intelligence only")
    now=as_of if as_of is not None else datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")

    payloads,source_state=_source_state(Path(root))
    predictive_path=Path(root)/FORECAST_SOURCE
    predictive_payload=_read_json(predictive_path)
    source_state["predictive_intelligence"]={
        "path":FORECAST_SOURCE,
        "available":bool(predictive_payload),
        "file_observed_at":None,
    }
    # No separate independent evidence pipeline.
    # Never echo customer names, source payloads, financial values or tenant IDs.
    availability={name:state["available"] is True
                  for name,state in source_state.items()}
    capabilities=[]
    for capability in product.included_capabilities:
        required=OS_CAPABILITY_SOURCES.get(capability)
        if not required:
            raise ValueError("existing product capability has no OS source mapping")
        missing=[key for key in required if not availability.get(key,False)]
        capabilities.append({
            "capability":capability,
            "existing_os_modules":list(required),
            "source_snapshot_presence":(
                "SOURCE_SNAPSHOTS_PRESENT_UNVERIFIED" if not missing
                else "SOURCE_SNAPSHOT_MISSING"
            ),
            "missing_source_keys":missing,
            "independent_customer_evidence_verified":False,
            "fulfilment_ready":False,
        })

    diagnostic=None
    blocked=[]
    snapshot_tenant=predictive_payload.get("tenant_id")
    memory=payloads.get("economic_memory") or {}
    if (predictive_payload and memory and
        memory.get("tenant_id")==snapshot_tenant and
        isinstance(snapshot_tenant,str) and snapshot_tenant.strip()):
        try:
            diagnostic=review_predictive_revenue_diagnostics(
                product_code=product.product_code,
                predictive_snapshot=predictive_payload,
                economic_memory=memory,
                tenant_id=snapshot_tenant,
                as_of=now,
            )
        except (ValueError,KeyError,TypeError,OverflowError):
            blocked.append("existing_diagnostic_evidence_contract_invalid")
    else:
        blocked.append("tenant_bound_predictive_intelligence_and_memory_not_available")
    if diagnostic is not None:
        # Copy only a bounded, non-PII projection of existing diagnostic.
        evaluation={
            "status":diagnostic["status"],
            "blocker_codes":list(diagnostic["blockers"]),
            "review_alerts":list(diagnostic["review_alerts"]),
            "verified_commercial_outcome_reviews":
                diagnostic["commercial_prediction_calibration"]["verified_review_count"],
            "temporal_holdout_count":
                diagnostic["commercial_prediction_calibration"]["temporal_holdout_count"],
            "client_report_claim_eligible":False,
        }
    else:
        evaluation={
            "status":"EVIDENCE_NOT_ADMITTED",
            "blocker_codes":blocked,
            "review_alerts":[],
            "verified_commercial_outcome_reviews":None,
            "temporal_holdout_count":None,
            "client_report_claim_eligible":False,
        }
    missing_sources=sorted({
        item for row in capabilities for item in row["missing_source_keys"]
    })
    return {
        "schema_version":"empire.predictive_revenue.product_workbench.v1",
        "integration_type":"PRODUCT_CAPABILITY_WITHIN_EXISTING_EMPIREOS",
        "existing_catalog_product_code":product.product_code,
        "existing_catalog_product_name":product.name,
        "existing_catalog_deployment_price_cents":
            product.deployment_price_cents,
        "currency":product.currency,
        "price_source":"existing_founder_approved_product_catalog",
        "catalog_changed":False,
        "existing_demo_path":"/v1/predictive-revenue/demo",
        "existing_interest_path":"/v1/predictive-revenue/interests",
        "existing_os_capabilities":capabilities,
        "missing_existing_os_sources":missing_sources,
        "source_snapshots_are_not_verified_outcomes":True,
        "existing_tenant_crm_report_adapter":{
            "source":"existing_empiredb_revenue_crm_prospects_view",
            "authentication":"existing_server_authenticated_revenue_crm_resolver",
            "session_scope":"empire_current_tenant_id()",
            "integration_status":"STAGED_OPT_IN_NOT_LIVE_CONNECTED",
            "customer_case_import_endpoint_created":False,
            "independent_client_delivery_approved":False,
        },
        "diagnostic_evidence_review":evaluation,
        "customer_diagnostic_fulfilled":False,
        "customer_delivery_enabled":False,
        "report_is_preview_not_verified":True,
        "new_database_created":False,
        "new_service_or_orchestrator_created":False,
        "outbound_enabled":False,
        "commercial_execution":False,
        "recognized_revenue_changed":False,
        "production_activated":False,
        "mode":"OBSERVE",
        "execution_authority":"none",
    }
