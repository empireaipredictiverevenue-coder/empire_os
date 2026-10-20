"""Four-stage cost/price/forecast evidence custody for Predictive Revenue.

This is a typed read-only RESEARCH handoff to existing Materials, Workforce,
Fulfilment, Commerce, Finance and original Quant owners. Source-owner JSON
is not independent supplier invoice/payment authentication, and a matching
digest is not a canonical signed DB readback. Nothing executes or persists.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import re
from typing import Any, Mapping, Sequence

from empire_os.predictive_customer_value_pilot_preflight import SCHEMA as PILOT_SCHEMA
from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_customer_value_commerce_evidence import SCHEMA as COMMERCE_SCHEMA
from empire_os.original_conversion_registry import (
    build_registration_request, inspect_prospective_registry_readback,
)

SCHEMA="empire.predictive_revenue.four_stage_economic_custody.v1"
CURRENCIES=frozenset(("USD","GBP","EUR"))
HASH=re.compile(r"^[a-f0-9]{64}$")
KEY=re.compile(r"^[a-z][a-z0-9_.:-]{2,80}$")
PACKET_KEYS=frozenset((
    "schema_version","mode","execution_authority","source_owner",
    "evidence_status","generated_at","tenant_ref_sha256",
    "opportunity_key","pilot_design_sha256","product_ref_sha256",
    "geography_key","currency","line_items",
))
OPERATIONS_KEYS=frozenset((
    "schema_version","mode","execution_authority","source_owner",
    "evidence_status","generated_at","tenant_ref_sha256",
    "opportunity_key","pilot_design_sha256","product_ref_sha256",
    "geography_key","currency","crew_minutes_per_unit",
    "assumed_hourly_loaded_labor_cost_minor",
    "distance_tenths_km_per_unit","assumed_delivery_cost_minor_per_km",
    "other_fulfilment_minor_per_unit","capacity_units_source_verified",
))
PRICE_KEYS=frozenset((
    "schema_version","mode","execution_authority","source_owner",
    "evidence_status","generated_at","tenant_ref_sha256",
    "opportunity_key","pilot_design_sha256","product_ref_sha256",
    "geography_key","currency","commercial_terms_sha256",
    "price_event_sha256","price_observed_at","price_state",
    "offered_unit_price_minor","payment_settled_and_refund_final_verified",
))
LINE_KEYS=frozenset((
    "line_ref_sha256","source_document_sha256","document_kind",
    "source_document_at","units_allocated","total_allocated_cost_minor",
    "cost_nature","original_document_authenticated",
))
EVIDENCE_STATUS="SOURCE_OWNER_REPORTED_UNAUTHENTICATED"
MAX_MINOR=10**11
PROOF_GATES=(
    "ORIGINAL_INVOICE_SUPPLIER_AND_PAYMENT_PROOF",
    "UNIT_LEVEL_COST_ALLOCATION_AND_COHORT_AUTHENTICATION",
    "CREW_PAYROLL_TIMESHEETS_AND_DELIVERY_RADIUS_PROOF",
    "ORIGINAL_BUYER_TERMS_ACCEPTED_AND_PAYMENT_SETTLED",
    "REFUNDS_FEES_AND_FINAL_COLOUR_OF_MONEY",
    "ORIGINAL_QUANT_REGISTERED_PREDICTION_BEFORE_OUTCOME",
    "CANONICAL_TENANT_PRODUCT_TERRITORY_PREDICTION_OUTCOME_BINDING",
)


def _hash(value:Any,name:str)->str:
    if not isinstance(value,str) or not HASH.fullmatch(value):
        raise ValueError("opaque bounded "+name+" digest required")
    return value


def _money(value:Any,label:str)->int:
    if type(value) is not int or not 0<=value<=MAX_MINOR:
        raise ValueError("bounded exact minor currency units required: "+label)
    return value


def _natural(value:Any,label:str,maximum:int)->int:
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError("bounded integer "+label+" required")
    return value


def _as_of(value:Any,now:datetime)->datetime:
    timestamp=_time(value)
    if not timedelta(0)<=now-timestamp<=timedelta(hours=72):
        raise ValueError("source owner summary must be fresh and not future")
    return timestamp


def _pilot(pilot:Mapping[str,Any])->tuple[str,str,datetime,datetime]:
    if (not isinstance(pilot,Mapping)
            or pilot.get("schema_version")!=PILOT_SCHEMA
            or pilot.get("status")!="PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED"
            or pilot.get("execution_authority")!="none"
            or pilot.get("original_quant_forecast_registered") is not False
            or pilot.get("prospective_design_durably_registered") is not False):
        raise ValueError("original unregistered pilot review required")
    original=_hash(pilot.get("design_revision_sha256"),"pilot")
    opportunity=pilot.get("opportunity_key")
    if not isinstance(opportunity,str) or not 3<=len(opportunity)<=128:
        raise ValueError("original opportunity identity required")
    start,end=_time(pilot.get("planned_pilot_start_at")),_time(pilot.get("planned_pilot_end_at"))
    if not start<end<=start+timedelta(days=90):
        raise ValueError("original pilot horizon required")
    return original,opportunity,start,end


def _packet(
    raw:Mapping[str,Any], *, keys:frozenset[str],kind:str,
    original:str,opportunity:str,now:datetime,
    identity:dict[str,Any]|None,
)->dict[str,Any]:
    if not isinstance(raw,Mapping) or set(raw)!=keys:
        raise ValueError("exact "+kind+" original owner source contract required")
    if (raw["schema_version"]!=f"empire.predictive_revenue.{kind}_owner_claim.v1"
            or raw["mode"]!="OBSERVE"
            or raw["execution_authority"]!="none"
            or raw["source_owner"]!={"materials":"existing_materials_procurement",
                                     "operations":"existing_workforce_fulfilment",
                                     "selling_price":"existing_commercial_terms_billing"}[kind]
            or raw["evidence_status"]!=EVIDENCE_STATUS
            or raw["pilot_design_sha256"]!=original
            or raw["opportunity_key"]!=opportunity
            or raw["currency"] not in CURRENCIES):
        raise ValueError("source owner/currency/opportunity or authority mismatch")
    _as_of(raw["generated_at"],now)
    for k in ("tenant_ref_sha256","product_ref_sha256"):
        _hash(raw[k],k)
    if not isinstance(raw["geography_key"],str) or not KEY.fullmatch(raw["geography_key"]):
        raise ValueError("specific source owner geography code required")
    subset={k:raw[k] for k in (
        "tenant_ref_sha256","opportunity_key","pilot_design_sha256",
        "product_ref_sha256","geography_key","currency",
    )}
    if identity is not None and subset!=identity:
        raise ValueError("cross-product/tenant/territory/currency source join blocked")
    return subset


def review_four_stage_cost_price_forecast_custody(
    pilot:Mapping[str,Any],
    materials:Mapping[str,Any],
    operations:Mapping[str,Any],
    selling_price:Mapping[str,Any],
    *,
    commerce_owner_review:Mapping[str,Any]|None=None,
    original_quant_candidate:Mapping[str,Any]|None=None,
    registry_receipt:Mapping[str,Any]|None=None,
    registry_readback:Mapping[str,Any]|None=None,
    as_of:datetime,
)->dict[str,Any]:
    """Review owner claims from 4 source lanes; never confer financial authority."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("timezone aware decision time required")
    now=as_of.astimezone(timezone.utc)
    design,opportunity,start,end=_pilot(pilot)
    identity=_packet(materials,keys=PACKET_KEYS,kind="materials",
                     original=design,opportunity=opportunity,now=now,identity=None)
    _packet(operations,keys=OPERATIONS_KEYS,kind="operations",
            original=design,opportunity=opportunity,now=now,identity=identity)
    _packet(selling_price,keys=PRICE_KEYS,kind="selling_price",
            original=design,opportunity=opportunity,now=now,identity=identity)

    lines=materials["line_items"]
    if not isinstance(lines,list) or not 1<=len(lines)<=40:
        raise ValueError("bounded original materials procurement item rows required")
    used=set()
    quoted=0
    invoiced=0
    quote_count=0
    invoice_count=0
    for item in lines:
        if not isinstance(item,Mapping) or set(item)!=LINE_KEYS:
            raise ValueError("strict source line item contract required")
        line=_hash(item["line_ref_sha256"],"material line")
        _hash(item["source_document_sha256"],"material document")
        if line in used:
            raise ValueError("replayed cost line")
        used.add(line)
        if (item["document_kind"] not in ("supplier_quote","supplier_invoice")
                or item["cost_nature"] not in ("materials","packaging","subcontract_equipment")
                or item["original_document_authenticated"] is not False):
            raise ValueError("cannot promote source invoice authentication")
        stamped=_time(item["source_document_at"])
        if stamped>now or stamped<start-timedelta(days=90):
            raise ValueError("cost document epoch out of original pilot planning window")
        units=_natural(item["units_allocated"],"cost allocation units",100_000)
        total=_money(item["total_allocated_cost_minor"],"source cost")
        if units==0 or total%units!=0:
            raise ValueError("unambiguous integer per-unit allocation required")
        if item["document_kind"]=="supplier_quote":
            quoted+=total//units
            quote_count+=1
        else:
            invoiced+=total//units
            invoice_count+=1
    # Quotes and invoices can be revisions or mutually exclusive alternatives.
    # Do not silently add both as incurred expenses.
    material_reference=(
        invoiced if invoice_count and not quote_count
        else quoted if quote_count and not invoice_count
        else None
    )

    crew=_natural(operations["crew_minutes_per_unit"],"crew minutes",100_000)
    hourly=_money(operations["assumed_hourly_loaded_labor_cost_minor"],"crew rate")
    distance=_natural(operations["distance_tenths_km_per_unit"],"travel tenths-km",1_000_000)
    per_km=_money(operations["assumed_delivery_cost_minor_per_km"],"delivery rate")
    other=_money(operations["other_fulfilment_minor_per_unit"],"other fulfilment")
    if operations["capacity_units_source_verified"] is not False:
        raise ValueError("unsupported workforce capacity proof")
    # Round estimated cost UP in minor units, avoid optimistic profit.
    labor=int((Decimal(crew)*Decimal(hourly)/Decimal(60))
              .to_integral_value(rounding=ROUND_CEILING))
    delivery=int((Decimal(distance)*Decimal(per_km)/Decimal(10))
                 .to_integral_value(rounding=ROUND_CEILING))
    fulfilment=labor+delivery+other

    _hash(selling_price["commercial_terms_sha256"],"commercial terms")
    _hash(selling_price["price_event_sha256"],"price event")
    observed=_time(selling_price["price_observed_at"])
    if observed>now or observed<start-timedelta(days=90):
        raise ValueError("source price terms outside original research scope")
    if (selling_price["price_state"] not in ("quoted","accepted_reported")
            or selling_price["payment_settled_and_refund_final_verified"] is not False):
        raise ValueError("customer acceptance/paid terms must remain unverified")
    sale=_money(selling_price["offered_unit_price_minor"],"customer price")
    if sale==0:
        raise ValueError("positive original offered price required")
    cost_total=fulfilment+material_reference if material_reference is not None else None
    theoretical_margin=sale-cost_total if cost_total is not None else None
    # No original actual unit profitability when both quote and invoice
    # exist with no unambiguous supersession chain.
    modeled_pct=(
        round(theoretical_margin/sale*100,5)
        if theoretical_margin is not None else None
    )

    commerce_status="NOT_SUPPLIED"
    commerce_paid_claims=None
    commerce_refunds_claims=None
    if commerce_owner_review is not None:
        c=commerce_owner_review
        if (not isinstance(c,Mapping)
                or c.get("schema_version")!=COMMERCE_SCHEMA
                or c.get("status")!="OWNER_REPORTED_COMMERCE_EVIDENCE_RECONCILED_UNAUTHENTICATED"
                or c.get("original_pilot_design_revision_matched") is not True
                or c.get("source_owner_authentication_proven") is not False
                or c.get("tenant_authentication_proven") is not False
                or c.get("recognized_revenue_minor") is not None
                or c.get("quant_calibration_ready") is not False
                or c.get("original_quant_forecast_registered") is not False
                or c.get("database_writes") is not False
                or c.get("execution_authority")!="none"):
            raise ValueError("untrusted existing commerce source summary")
        for k in ("claimed_paid_event_count","claimed_reversal_count"):
            _natural(c.get(k),k,100_000)
        if c.get("source_reported_currency") not in (None,identity["currency"]):
            raise ValueError("cross-currency sales claim cannot be matched")
        commerce_status="OWNER_COMMERCE_CLAIMS_UNAUTHENTICATED_NOT_UNIT_JOINABLE"
        commerce_paid_claims=c["claimed_paid_event_count"]
        commerce_refunds_claims=c["claimed_reversal_count"]

    forecast_status="ORIGINAL_FORECAST_CANDIDATE_NOT_SUPPLIED"
    forecast_ref=None
    registry_status="NO_INDEPENDENT_QUANT_READBACK"
    if original_quant_candidate is not None:
        reg=build_registration_request(original_quant_candidate,as_of=now)
        prediction=reg["payload"]
        if prediction["opportunity_key"]!=opportunity:
            raise ValueError("forecast opportunity does not match original pilot")
        # The original registry candidate carries tenant UUID rather than
        # our opaque owner-scope tenant hash; it has no pilot revision binding.
        # Therefore a candidate match cannot authenticate tenant or design.
        forecast_ref=reg["prediction_ref"]
        forecast_status="CANDIDATE_VALIDATED_NOT_REGISTERED"
        if registry_receipt is not None or registry_readback is not None:
            checked=inspect_prospective_registry_readback(
                original_quant_candidate,receipt=registry_receipt,
                readback=registry_readback,as_of=now,
            )
            registry_status=checked["status"]
    elif registry_receipt is not None or registry_readback is not None:
        raise ValueError("registration receipts require original forecast candidate")

    return {
        "schema_version":SCHEMA,"status":"FOUR_STAGE_ECONOMIC_SOURCE_CUSTODY_REVIEWED",
        "mode":"OBSERVE",
        "original_opportunity_key":opportunity,
        "original_pilot_design_sha256":design,
        "research_country_scope_unverified":identity["geography_key"],
        "source_currency":identity["currency"],
        "raw_tenant_product_supplier_buyer_ids_disclosed":False,
        "material_supplier_quote_line_count":quote_count,
        "material_supplier_invoice_line_count":invoice_count,
        "quote_cost_minor_per_unit_claimed":quoted if quote_count else None,
        "invoice_cost_minor_per_unit_claimed":invoiced if invoice_count else None,
        "source_quotes_and_invoices_have_supersession_linkage":False,
        "selected_material_reference_cost_minor_unverified":material_reference,
        "crew_minutes_per_unit_source_owner_claim":crew,
        "hourly_labor_cost_minor_assumed":hourly,
        "estimated_labor_cost_minor_per_unit":labor,
        "distance_tenths_km_per_unit_assumed":distance,
        "estimated_delivery_minor_per_unit":delivery,
        "other_fulfilment_minor_per_unit_assumed":other,
        "estimated_fulfilment_cost_minor_per_unit":fulfilment,
        "source_reported_offered_price_minor_per_unit":sale,
        "price_acceptance_claim_only":selling_price["price_state"],
        "unverified_all_in_cost_reference_minor_per_unit":cost_total,
        "illustrative_unit_contribution_minor_excluding_cac_fees_tax_overhead":theoretical_margin,
        "illustrative_unit_contribution_margin_pct_unverified":modeled_pct,
        "quote_invoice_mix_blocks_single_cost_reference":quote_count>0 and invoice_count>0,
        "source_reported_commerce_review_status":commerce_status,
        "commerce_claimed_paid_event_count_not_actual_paid_units":commerce_paid_claims,
        "commerce_claimed_refund_event_count_not_settlement_final":commerce_refunds_claims,
        "original_quant_candidate_status":forecast_status,
        "original_quant_candidate_reference_not_registry_proof":forecast_ref,
        "original_quant_registry_readback_status":registry_status,
        "quant_registry_has_original_pilot_sha256_and_tenant_digest_binding":False,
        "original_registered_before_outcome_forecast_authenticated":False,
        "source_cost_invoice_independently_authenticated":False,
        "labor_timesheets_and_payroll_independently_authenticated":False,
        "local_delivery_capacity_independently_authenticated":False,
        "customer_accepted_price_independently_authenticated":False,
        "payment_settlement_refund_finality_verified":False,
        "actual_revenue_minor":None,"actual_gross_profit_minor":None,
        "matched_original_profit_forecast_and_outcome_pairs":None,
        "original_forecast_profit_error_minor":None,
        "causal_incremental_margin_verified":False,
        "source_index_used_as_supplier_invoice":False,
        "required_independent_proofs":list(PROOF_GATES),
        "next_owners":{
            "materials":"existing_materials_procurement",
            "workforce_and_delivery":"existing_workforce_fulfilment",
            "accepted_offer_and_payment":"existing_commercial_terms_billing",
            "original_forecast_registry":"existing_scientific_quant_original_registry",
            "actual_profit_and_refund_finality":"existing_finance_and_economic_memory",
        },
        "economic_memory_training_authorized":False,
        "billing_or_commercial_actions_authorized":False,
        "external_source_query_performed":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
