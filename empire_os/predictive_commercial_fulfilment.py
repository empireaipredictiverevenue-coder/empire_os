"""Governed fulfilment + procurement preflight for one commercial requirement.

Source reviews and immutable proposed handoff IDs do not dispatch tasks. RFQs
and quotes are source-owner *claims*, not authenticated supplier offers or
purchase-ready estimates. Cloud scenarios are explicitly hypothetical.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import re
from typing import Any,Mapping,Sequence
from empire_os.predictive_commercial_requirements import SCHEMA as REQUIREMENT
from empire_os.predictive_commercial_supply_readiness import SCHEMA as SUPPLY
from empire_os.predictive_commercial_lead_eligibility import review_lead_eligibility_owner_preview
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)
from empire_os.predictive_customer_value_demand import _time

SCHEMA="empire.predictive_revenue.commercial_fulfilment_and_procurement.v1"
HASH=re.compile(r"^[0-9a-f]{64}$")
OWNER_TASKS=(
    ("a2a_commercial_signal_miner","AUTHORIZED_LOCAL_MARKET_SIGNAL_RESEARCH"),
    ("buyer_scout","COMPANY_IDENTITY_BUYER_AUTHORITY_DUPLICATE_REVIEW"),
    ("lead_supply_intelligence","CANONICAL_CONSENTED_GEO_INVENTORY_AUDIT"),
    ("marketing_seo_campaigns","PERMITTED_CHANNEL_BUDGET_RESEARCH"),
    ("procurement_supply_intelligence","ORIGINAL_SUPPLIER_RFQ_SPEC_AND_QUOTE_REVIEW"),
    ("finance_os","CONTRACTED_PRICE_LANDED_COST_REFUND_SETTLEMENT_REVIEW"),
    ("predictive_quant","ORIGINAL_PROSPECTIVE_FORECAST_AND_OUTCOME_CUSTODY"),
    ("predictive_cloud","SCENARIO_CONSTRAINT_RISK_PORTFOLIO_SHADOW_REVIEW"),
)


def _digest(v:Mapping[str,Any])->str:
    return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),
                   allow_nan=False).encode()).hexdigest()


def prepare_owner_handoffs(requirement:Mapping[str,Any])->list[dict[str,Any]]:
    ref=requirement["requirement_revision_sha256"]
    if not isinstance(ref,str) or not HASH.fullmatch(ref):
        raise ValueError("original requirement revision required")
    items=[]
    for owner,task in OWNER_TASKS:
        unique=_digest({"revision":ref,"owner":owner,"task":task,"contract_version":1})
        items.append({
            "handoff_schema":"empire.predictive_revenue.proposed_a2a_owner_ticket.v1",
            "source_requirement_revision_sha256":ref,
            "owner":owner,"requested_review_type":task,
            "idempotency_key":"predictive:owner_review:"+unique,
            "target_industry":requirement["industry"],
            "target_country":requirement["country"],
            "target_state":requirement["state"],
            "target_city":requirement["city"],
            "source_tenant_authentication_verified":False,
            "source_signing_key_attested":False,
            "provider_request_receipt":None,
            "owner_acknowledgement_receipt":None,
            "replay_protection_persisted":False,
            "status":"PREPARED_NOT_DELIVERED",
            "task_dispatched":False,"outbound_sent":False,
            "execution_authority":"none",
        })
    return items


def _safe_int(x:Any,name:str)->int:
    if type(x) is not int or not 0<=x<=10**11:
        raise ValueError("exact bounded original "+name+" value required")
    return x


def review_roofing_procurement(
    requirement:Mapping[str,Any], *,
    original_roof_project:Mapping[str,Any]|None=None,
    supplier_owner_quotes:Sequence[Mapping[str,Any]]|None=None,
    as_of:datetime,
)->dict[str,Any]:
    """Plan materials by category, not roof area or price speculation."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware research time required")
    cats=list(requirement["material_category_research_scopes"])
    if requirement["industry"]!="roofing" and original_roof_project is not None:
        raise ValueError("roof-specific measured project record cannot be used for another industry")
    if supplier_owner_quotes is None:supplier_owner_quotes=[]
    if not isinstance(supplier_owner_quotes,(tuple,list)) or len(supplier_owner_quotes)>8:
        raise ValueError("bounded original supplier quote packets")
    measured=False
    project_revision=None
    needs=[
        "VERIFIED_PROJECT_ROOF_MEASUREMENTS_AND_PITCH",
        "SPECIFIED_COVERING_SYSTEM_AND_PRODUCT_COMPATIBILITY",
        "LOCAL_CODE_WIND_FIRE_AND_PERMIT_REQUIREMENTS",
        "WASTE_FLASHING_UNDERLAYMENT_VENT_QUANTITIES",
        "DELIVERY_SITE_ACCESS_DATES_AND_FREIGHT",
        "ORIGINAL_SUPPLIER_IDENTITY_AUTHENTICATED_QUOTATION",
        "FINANCE_PURCHASE_APPROVAL_AND_CASH_BUDGET",
    ] if requirement["industry"]=="roofing" else [
        "OWNER_AUTHENTICATED_INDUSTRY_SPECIFIC_SERVICE_OR_PRODUCT_SCOPE",
        "VERIFIED_MATERIAL_QUANTITIES_AND_LOCAL_CODE_OR_REGULATORY_REQUIREMENTS",
        "ORIGINAL_SUPPLIER_QUOTATIONS_AND_DELIVERY_TERMS",
        "FINANCE_PURCHASE_APPROVAL_AND_CASH_BUDGET",
    ]
    if original_roof_project is not None:
        p=original_roof_project
        if (not isinstance(p,Mapping) or set(p)!={
                "project_ref_sha256","roof_measurement_ref_sha256",
                "measured_area_m2","roof_pitch_ratio","system_spec_ref_sha256",
                "location_code_reviewed","source_owner_authenticated"}):
            raise ValueError("typed owner project survey contract required")
        for name in ("project_ref_sha256","roof_measurement_ref_sha256",
                     "system_spec_ref_sha256"):
            if not isinstance(p[name],str) or not HASH.fullmatch(p[name]):
                raise ValueError("opaque original project/source reference required")
        if (type(p["measured_area_m2"]) not in (int,float)
                or not 0<p["measured_area_m2"]<=100_000
                or type(p["roof_pitch_ratio"]) not in (int,float)
                or not 0<=p["roof_pitch_ratio"]<=6
                or p["location_code_reviewed"] is not False
                or p["source_owner_authenticated"] is not False):
            raise ValueError("unverified supplier/source assertions not accepted")
        project_revision=p["project_ref_sha256"]
    comparable=[]
    seen=set()
    for quote in supplier_owner_quotes:
        if (not isinstance(quote,Mapping) or set(quote)!={
                "source_owner","quote_ref_sha256","supplier_ref_sha256",
                "project_ref_sha256","observed_at","currency",
                "source_quoted_material_minor","source_quoted_freight_minor",
                "source_quoted_tax_minor","expected_delivery_days",
                "independent_supplier_acceptance_authenticated",
                "purchase_authorized"}):
            raise ValueError("exact original RFQ owner claim required")
        if (quote["source_owner"]!="existing_procurement_supply_intelligence"
                or quote["currency"]!=requirement["currency"]
                or quote["independent_supplier_acceptance_authenticated"] is not False
                or quote["purchase_authorized"] is not False):
            raise ValueError("cannot escalate quote as accepted supplier purchase")
        for k in ("quote_ref_sha256","supplier_ref_sha256","project_ref_sha256"):
            if not isinstance(quote[k],str) or not HASH.fullmatch(quote[k]):
                raise ValueError("required opaque quote/source reference")
        qid=quote["quote_ref_sha256"]
        if qid in seen:
            raise ValueError("duplicate/replayed procurement quote")
        seen.add(qid)
        if project_revision is None or quote["project_ref_sha256"]!=project_revision:
            raise ValueError("quote cannot be compared without matching original project scope")
        stamped=_time(quote["observed_at"])
        if not timedelta(0)<=as_of.astimezone(timezone.utc)-stamped<=timedelta(days=30):
            raise ValueError("supplier quote too old or future")
        days=_safe_int(quote["expected_delivery_days"],"delivery days")
        if days>365:
            raise ValueError("delivery horizon beyond bounds")
        component={
            field:_safe_int(quote[field],field)
            for field in ("source_quoted_material_minor","source_quoted_freight_minor",
                          "source_quoted_tax_minor")
        }
        comparable.append({
            "quote_ref_sha256":qid,
            "source_reported_landed_cost_minor_unverified":sum(component.values()),
            "source_reported_expected_delivery_days_unverified":days,
            "original_supplier_quote_independently_authenticated":False,
            "like_for_like_comparability_verified":False,
            "available_to_order":False,
        })
    comparable.sort(key=lambda x:(x["source_reported_landed_cost_minor_unverified"],
                                  x["quote_ref_sha256"]))
    return {
        "schema_version":"empire.predictive_revenue.supplier_rfqs.v1",
        "status":("PRELIMINARY_RFQ_REQUIREMENTS_NO_PURCHASE_READY_BOM"
                  if requirement["physical_material_procurement_applicable"]
                  else "NOT_APPLICABLE_NO_PHYSICAL_MATERIALS_REQUEST"),
        "mode":"OBSERVE","materials_to_scope_not_purchase_quantities":cats,
        "original_roof_project_ref_sha256":project_revision,
        "original_measurements_independently_authenticated":measured,
        "material_quantities_verified":False,
        "building_code_specification_verified":False,
        "source_owner_quote_count":len(comparable),
        "supplier_owner_claimed_quotes":comparable,
        "confirmed_comparable_landed_quote_minor":None,
        "sourcing_ready_for_purchase":False,
        "owner_missing_prerequisites":needs,
        "original_uk_tenders_are_us_material_supplier_quotes":False,
        "automatic_rfqs_sent":False,"purchase_orders_issued":False,
        "supplier_price_assumed_from_bls_ppi":False,
        "database_writes":False,"execution_authority":"none",
    }


def review_cloud_commercial_research(
    requirement:Mapping[str,Any], readiness:Mapping[str,Any], *,
    hypothetical_scenarios:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    """Explicit owner-supplied scenario IR; NO optimizer execution/allocation."""
    base={
        "schema_version":"empire.predictive_revenue.cloud_commercial_research.v1",
        "status":"CLOUD_SOURCE_ECONOMICS_AND_CAPACITY_MISSING",
        "mode":"OBSERVE","scenario_ir":None,
        "existing_cloud_compiler_reused":False,
        "tenant_scope_authenticated":False,
        "verified_target_market_selling_inventory":readiness.get("verified_target_market_available_inventory"),
        "verified_tampa_selling_inventory":readiness.get("verified_tampa_available_inventory")
            if requirement["country"]=="US" and requirement["state"]=="FL"
            and requirement["city"]=="Tampa" else None,
        "verified_buyer_serviceable_lead_capacity":None,
        "original_lead_acceptance_price_verified":False,
        "verified_supplier_landed_cost_available":False,
        "verified_lead_acquisition_cost_available":False,
        "original_profit_prediction_registered":False,
        "scenario_probabilities_empirically_calibrated":False,
        "optimizer_executed":False,
        "lead_allocation_or_marketing_spend_authorized":False,
        "payment_or_material_purchase_authorized":False,
        "database_writes":False,"execution_authority":"none",
    }
    if hypothetical_scenarios is None:
        return base
    src=hypothetical_scenarios
    if (not isinstance(src,Mapping) or set(src)!={
            "scenarios","actions","hypothetical_budget_minor",
            "assumed_research_action_capacity","risk_aversion",
            "original_assumptions_unverified"}
            or src["original_assumptions_unverified"] is not True
            or type(src["hypothetical_budget_minor"]) is not int
            or not 0<=src["hypothetical_budget_minor"]<=10**10
            or type(src["assumed_research_action_capacity"]) is not int
            or not 0<=src["assumed_research_action_capacity"]<=100):
        raise ValueError("exact hypothetical cloud economic research contract")
    actions=src["actions"]
    if (not isinstance(actions,list) or len(actions)>15 or
            any(not isinstance(x,Mapping) or
                x.get("capacity_group")!="research_action" or
                not isinstance(x.get("action_key"),str) or
                not re.fullmatch(r"research_[a-z0-9_]{3,60}",x["action_key"])
                for x in actions)):
        raise ValueError("shadow-only research action group required")
    problem=build_predictive_cloud_scenario_problem(
        scenarios=src["scenarios"],actions=actions,
        budget_cents=src["hypothetical_budget_minor"],
        capacity_constraints={"research_action":src["assumed_research_action_capacity"]},
        risk_aversion=src["risk_aversion"],
        workload_key="predictive_commercial_research_shadow",
        tenant_id=None,
    )
    return {
        **base,
        "status":"HYPOTHETICAL_RESEARCH_CLOUD_IR_NOT_ALLOCATION",
        "scenario_ir":problem,
        "existing_cloud_compiler_reused":True,
        "hypothetical_budget_is_actual_authorized_spend":False,
        "shadow_capacity_is_consent_verified_lead_delivery":False,
        "outcome_forecast_scenario_values_authenticated":False,
        "economic_solver_solution_produced":False,
    }


def plan_commercial_fulfilment(
    requirement:Mapping[str,Any],readiness:Mapping[str,Any], *,
    as_of:datetime,
    original_roof_project:Mapping[str,Any]|None=None,
    supplier_owner_quotes:Sequence[Mapping[str,Any]]|None=None,
    hypothetical_cloud:Mapping[str,Any]|None=None,
    lead_owner_eligibility_preview:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    if (not isinstance(requirement,Mapping)
            or requirement.get("schema_version")!=REQUIREMENT
            or requirement.get("status")!="COMMERCIAL_REQUIREMENT_INCOMPLETE"
            or requirement.get("execution_authority")!="none"
            or requirement.get("source_customer_order_authenticated") is not False
            or not isinstance(readiness,Mapping)
            or readiness.get("schema_version")!=SUPPLY
            or readiness.get("execution_authority")!="none"):
        raise ValueError("validated source-research-only requirement and inventory required")
    if any(readiness.get(rkey)!=requirement[ckey] for rkey,ckey in (
        ("research_target_industry","industry"),
        ("research_target_market_country","country"),
        ("research_target_market_state","state"),
        ("research_target_market_city","city"),
    )):
        raise ValueError("market/industry mismatched owner readiness cannot inform fulfilment")
    target=requirement["requested_qualified_leads_target_not_inventory"]
    if type(target) is not int or target<=0:
        raise ValueError("valid customer-requested target required")
    procurement=review_roofing_procurement(
        requirement,original_roof_project=original_roof_project,
        supplier_owner_quotes=supplier_owner_quotes,as_of=as_of,
    )
    cloud=review_cloud_commercial_research(
        requirement,readiness,hypothetical_scenarios=hypothetical_cloud,
    )
    tickets=prepare_owner_handoffs(requirement)
    lead_audit=review_lead_eligibility_owner_preview(
        requirement,lead_owner_eligibility_preview,as_of=as_of,
    )
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE","status":"INSUFFICIENT_EVIDENCE_NOT_READY_TO_PROMISE_OR_FULFIL",
        "original_requirement_revision_sha256":requirement["requirement_revision_sha256"],
        "industry":requirement["industry"],"country":requirement["country"],
        "state":requirement["state"],"city":requirement["city"],
        "customer_requested_qualified_leads":target,
        "verified_customer_order_count":None,
        "current_source_global_immediately_sellable_inventory":readiness.get(
            "global_immediately_sellable_inventory"),
        "source_target_industry_research_records_not_deliverable_leads":readiness.get(
            "source_target_industry_research_records_not_leads"),
        "source_roofing_research_records_not_deliverable_leads":readiness.get(
            "original_source_roofing_research_records_not_leads")
            if requirement["industry"]=="roofing" else None,
        "verified_market_and_customer_eligible_leads":None,
        "verified_target_market_inventory_units":readiness.get(
            "verified_target_market_available_inventory"),
        "verified_inventory_reserved_for_customer":None,
        "verified_fulfilment_gap_units":None,
        "unproven_target_units_pending_review":target,
        "source_global_verified_buyer_capacity_count":readiness.get(
            "verified_global_buyer_capacity_count"),
        "forecasted_accepted_leads":None,
        "forecasted_recoverable_margin_minor":None,
        "realized_gross_profit_minor":None,
        "lead_acquisition_channels_research_only":[
            "approved_first_party_seo_and_content",
            "approved_search_campaign_research_no_budget",
            "source_rights_reviewed_partnerships",
            "consented_inbound_forms_and_calls",
        ],
        "supplier_sourcing_preflight":procurement,
        "per_lead_duplicate_consent_and_eligibility_preflight":lead_audit,
        "cloud_scenario_capacity_review":cloud,
        "owner_handoffs_prepared_not_dispatched":tickets,
        "prepared_owner_ticket_count":len(tickets),
        "owner_handoff_delivery_receipts":0,
        "idempotency_keys_persisted_by_owner":False,
        "independent_tenant_A2A_trust_and_signing_verified":False,
        "lead_duplicates_and_rejections_checked_against_canonical_owner":False,
        "requested_target_is_verified_available":False,
        "requested_20_is_available_20":False if target==20 else None,
        "customer_commitment_authorized":False,
        "marketing_spend_authorized":False,
        "rfq_outbound_authorized":False,
        "materials_purchase_authorized":False,
        "production_deployed":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
