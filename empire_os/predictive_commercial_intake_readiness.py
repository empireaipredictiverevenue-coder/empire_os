"""Non-executing commercial intake readiness before strict customer planning.

A template with null market/industry fields is an INCOMPLETE draft, not a
Python error and never a customer contract. No input contents are returned,
except safe field names from the fixed schema. Bad values are never echoed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.predictive_commercial_requirements import INPUT_FIELDS

SCHEMA="empire.predictive_revenue.commercial_intake_readiness.v1"
REQUIRED_TO_PLAN=(
    "country","state","city","industry","currency","requested_qualified_leads",
)

FIELD_HINTS={
    "country":"Supported uppercase ISO-style country code (e.g. US, GB, CA, AU).",
    "state":"Explicit region code, such as AZ, TX or LON. Not a street address.",
    "city":"Customer's target city; no city is selected automatically.",
    "industry":"roofing, hvac, solar, construction, insurance, agency, data_brokerage, professional_services, software, other.",
    "currency":"Explicit original market currency, e.g. USD for US or GBP for GB.",
    "requested_qualified_leads":"Integer target greater than zero, NOT currently available inventory.",
}

def inspect_commercial_intake_draft(value:Any)->dict[str,Any]:
    if not isinstance(value,Mapping):
        return _report("COMMERCIAL_INTAKE_INVALID_STRUCTURE",[],[],0)
    fields=set(value)
    unknown=fields-INPUT_FIELDS
    missing_keys=INPUT_FIELDS-fields
    missing_required=[
        name for name in REQUIRED_TO_PLAN
        if name not in value or value[name] is None or value[name]==""
    ]
    if unknown or missing_keys:
        return _report(
            "COMMERCIAL_INTAKE_INVALID_STRUCTURE",missing_required,
            sorted(name for name in missing_keys if name in REQUIRED_TO_PLAN),
            len(unknown),missing_schema_fields_count=len(missing_keys),
        )
    if missing_required:
        return _report("COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS",
                       missing_required,[],0)
    return _report("COMMERCIAL_INTAKE_PLANNING_FIELDS_SUPPLIED",
                   [],[],0)


def _report(
    status:str,missing_required:list[str],missing_schema:list[str],
    unknown_count:int,*,missing_schema_fields_count:int=0,
)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":status,
        "planning_required_field_names":list(REQUIRED_TO_PLAN),
        "missing_required_planning_fields":missing_required,
        "missing_field_hints":{
            name:FIELD_HINTS[name] for name in missing_required
        },
        "missing_required_schema_field_names":missing_schema,
        "missing_schema_field_count":missing_schema_fields_count,
        "unknown_schema_field_count":unknown_count,
        "valid_customer_order_authenticated":False,
        "source_inventory_reconciled":False,
        "buyer_purchasing_authority_verified":False,
        "owner_handoffs_dispatched":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
