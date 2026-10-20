"""Typed tenant-scoped commercial requirement intent; no execution authority.

A founder target is not verified buyer commitment, market demand or owned lead
inventory. Unverified tenant scopes are drafted, never authorised for A2A dispatch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA="empire.predictive_revenue.commercial_requirement.v1"
SHA=re.compile(r"^[a-f0-9]{64}$")
ZIP=re.compile(r"^[0-9]{5}$")
CODE=re.compile(r"^[a-z][a-z0-9_]{2,48}$")
KINDS=frozenset(("roofing","hvac","solar","construction","insurance","agency",
                 "data_brokerage","professional_services","software","other"))
CHANNELS=frozenset(("consented_form","verified_inbound_call","booked_appointment"))
MATERIAL_CATEGORIES={
    "roofing":("roof_covering_system","underlayment_waterproofing",
                "flashing","ridge_vents_accessories","fasteners_consumables",
                "insulation_if_applicable","delivery_freight"),
    "hvac":("equipment_system","refrigerant_and_lines","controls_thermostat",
            "ducting_and_fittings","installation_consumables","delivery_freight"),
    "solar":("pv_module_system","inverters","mounting_bos","electric_protection",
             "battery_if_applicable","delivery_freight"),
    "construction":("project_specific_material_specification","delivery_freight"),
}
INPUT_FIELDS=frozenset((
    "tenant_ref_sha256","company_ref_sha256","company_authorization_owner_receipt",
    "country","state","city","zip_codes","industry","service_types",
    "exclusions","requested_qualified_leads","delivery_deadline",
    "delivery_cadence","billable_lead_definition","exclusivity",
    "accepted_event_types","budget_minor","price_per_accepted_lead_minor",
    "currency","replacement_refund_policy","buyer_capacity_verified_units",
    "permission_proof_owner_receipt","material_specs_owner_receipt",
))

def _digest(record:Mapping[str,Any])->str:
    return sha256(json.dumps(record,sort_keys=True,separators=(",",":"),
                    allow_nan=False).encode()).hexdigest()


def review_commercial_requirement(raw:Mapping[str,Any],*,as_of:datetime)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("timezone-aware owner clock required")
    if not isinstance(raw,Mapping) or set(raw)!=INPUT_FIELDS:
        raise ValueError("complete exact commercial requirement schema required")
    tenant=raw["tenant_ref_sha256"]
    company=raw["company_ref_sha256"]
    for value in (tenant,company):
        if value is not None and (not isinstance(value,str) or not SHA.fullmatch(value)):
            raise ValueError("tenant and company must have original opaque digests")
    for field in ("company_authorization_owner_receipt","permission_proof_owner_receipt",
                  "material_specs_owner_receipt"):
        if raw[field] is not None:
            raise ValueError("unverified receipt cannot be self-certified in an intake")
    if (raw["country"] not in ("US","GB")
            or not isinstance(raw["state"],str)
            or not re.fullmatch(r"[A-Z]{2,3}",raw["state"])
            or not isinstance(raw["city"],str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z .-]{1,70}",raw["city"])):
        raise ValueError("explicit typed country region and city required")
    industry=raw["industry"]
    if industry not in KINDS:
        raise ValueError("industry taxonomy required")
    for key in ("service_types","exclusions","accepted_event_types","zip_codes"):
        value=raw[key]
        if not isinstance(value,list) or len(value)>30:
            raise ValueError("bounded list of "+key+" required")
        if len(value)!=len(set(value)) or any(not isinstance(x,str) or not x for x in value):
            raise ValueError("unique string "+key+" entries required")
    if any(not (ZIP.fullmatch(x) if raw["country"]=="US" else
                re.fullmatch(r"[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}",x))
           for x in raw["zip_codes"]):
        raise ValueError("exact country-specific postal values required")
    if any(not CODE.fullmatch(x) for x in raw["service_types"]+raw["exclusions"]):
        raise ValueError("typed service/exclusion tokens required")
    if any(x not in CHANNELS for x in raw["accepted_event_types"]):
        raise ValueError("accepted events must be consented and typed")
    target=raw["requested_qualified_leads"]
    if type(target) is not int or not 1<=target<=100000:
        raise ValueError("requested lead target must be a positive integer")
    if raw["delivery_deadline"] is not None:
        from empire_os.predictive_customer_value_demand import _time
        time=_time(raw["delivery_deadline"])
        if time<=as_of.astimezone(timezone.utc):
            raise ValueError("future deadline required")
    if raw["delivery_cadence"] is not None and raw["delivery_cadence"] not in (
        "daily","weekly","phased","one_time"):
        raise ValueError("typed cadence required")
    if raw["billable_lead_definition"] is not None and raw["billable_lead_definition"] not in (
        "consented_qualified_form","verified_connected_inbound_call",
        "attended_qualified_appointment"):
        raise ValueError("typed valid billable lead required")
    if raw["exclusivity"] not in ("unconfirmed","exclusive","shared"):
        raise ValueError("exclusive/shared terms must be explicit")
    if (raw["currency"] not in ("USD","GBP")
            or (raw["country"]=="US" and raw["currency"]!="USD")
            or (raw["country"]=="GB" and raw["currency"]!="GBP")):
        raise ValueError("country-specific currency requires an explicit original declaration")
    for key in ("budget_minor","price_per_accepted_lead_minor"):
        v=raw[key]
        if v is not None and (type(v) is not int or not 0<=v<=10**11):
            raise ValueError("explicit exact cents required")
    capacity=raw["buyer_capacity_verified_units"]
    if capacity is not None:
        raise ValueError("intake cannot independently attest buyer capacity")
    if raw["replacement_refund_policy"] is not None and raw["replacement_refund_policy"] not in (
        "approved_replace_eligible","approved_refund_eligible",
        "approved_replace_or_refund_eligible"):
        raise ValueError("refund policy must be approved through the commercial owner")
    public={k:raw[k] for k in sorted(INPUT_FIELDS)
            if k not in ("company_authorization_owner_receipt",
                         "permission_proof_owner_receipt","material_specs_owner_receipt")}
    # Stable across repeated reviews: draft identity is NOT globally allocated.
    revision=_digest(public)
    missing=[
        ("TENANT_SCOPE_AND_COMPANY_IDENTITY",tenant is None or company is None),
        ("OWNER_AUTHENTICATED_COMPANY_BUYING_AUTHORITY",True),
        ("EXACT_SERVICE_ZIP_TERRITORY",not raw["zip_codes"]),
        ("SERVICE_AND_EXCLUSION_SPECIFICATION",not raw["service_types"]),
        ("LEAD_ACCEPTANCE_AND_EVENT_DEFINITION",
         not raw["billable_lead_definition"] or not raw["accepted_event_types"]),
        ("DELIVERY_DEADLINE_AND_CADENCE",
         raw["delivery_deadline"] is None or raw["delivery_cadence"] is None),
        ("EXCLUSIVITY_AND_REPLACEMENT_TERMS",
         raw["exclusivity"]=="unconfirmed" or raw["replacement_refund_policy"] is None),
        ("CONTRACTED_BUDGET_AND_ACCEPTED_LEAD_PRICE",
         raw["budget_minor"] is None or raw["price_per_accepted_lead_minor"] is None),
        ("BUYER_SERVICE_CAPACITY_ORIGINAL_OWNER",True),
        ("CONSENT_COMPLIANCE_PROOF_ORIGINAL_OWNER",True),
        ("PROJECT_MEASUREMENTS_MATERIALS_AND_CODE_SPEC",True),
    ]
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"COMMERCIAL_REQUIREMENT_INCOMPLETE",
        "source_instruction_kind":"FOUNDER_EXAMPLE_TARGET_NOT_CUSTOMER_ORDER",
        "industry":industry,"country":raw["country"],"state":raw["state"],"city":raw["city"],
        "service_types":list(raw["service_types"]),
        "requested_qualified_leads_target_not_inventory":target,
        "currency":raw["currency"],"tenant_scope_verified":False,
        "company_buying_authority_verified":False,
        "consent_to_contact_proven":False,
        "defined_acceptance_specification_verified":False,
        "delivery_schedule_or_purchasing_committed":False,
        "requirement_revision_sha256":revision,
        "draft_idempotency_key":"predictive:commercial_requirement:"+revision,
        "required_owner_questions":[name for name,needed in missing if needed],
        "source_entered_zip_codes":list(raw["zip_codes"]),
        "source_entered_budget_minor":raw["budget_minor"],
        "source_entered_unit_price_minor":raw["price_per_accepted_lead_minor"],
        "source_entered_deadline":raw["delivery_deadline"],
        "source_entered_event_types":list(raw["accepted_event_types"]),
        "material_category_research_scopes":list(MATERIAL_CATEGORIES.get(
            industry,("project_specific_scope","delivery_freight"))),
        "verified_deliverable_lead_count":None,
        "source_customer_order_authenticated":False,
        "outbound_authorized":False,"procurement_authorized":False,
        "marketing_budget_authorized":False,"database_writes":False,
        "execution_authority":"none",
    }


def tampa_roofing_founder_example()->dict[str,Any]:
    """Exact known founder intent; UNKNOWN details intentionally left unknown."""
    return {
        "tenant_ref_sha256":None,"company_ref_sha256":None,
        "company_authorization_owner_receipt":None,
        "country":"US","state":"FL","city":"Tampa","zip_codes":[],
        "industry":"roofing","service_types":[],"exclusions":[],
        "requested_qualified_leads":20,"delivery_deadline":None,
        "delivery_cadence":None,"billable_lead_definition":None,
        "exclusivity":"unconfirmed","accepted_event_types":[],
        "budget_minor":None,"price_per_accepted_lead_minor":None,
        "currency":"USD","replacement_refund_policy":None,
        "buyer_capacity_verified_units":None,
        "permission_proof_owner_receipt":None,"material_specs_owner_receipt":None,
    }
