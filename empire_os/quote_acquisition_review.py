"""Consent-first quote enquiry review for the existing EmpireOS acquisition flow.

Pure function: no contact storage, no messaging, no production writes.
Contractor and financial authority remain with canonical EmpireOS owners.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.quote_acquisition_review.v1"
VERTICALS = frozenset({"roofing", "hvac", "solar", "plumbing", "electrical",
                       "windows", "insulation", "dental", "legal", "commercial"})
GATES = ("first_party_request", "contact_permission", "privacy_notice_acknowledged",
         "service_scope_present", "location_present", "genuine_customer_intent")


def review_quote_request(*, vertical: str, request: Mapping[str, Any],
                         buyer: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe triage; never expose customer PII or generate a contact list."""
    if not isinstance(request, Mapping) or not isinstance(buyer, Mapping):
        raise ValueError("request and buyer mappings required")
    if not isinstance(vertical, str) or vertical not in VERTICALS:
        raise ValueError("unsupported vertical")
    checks = {name: request.get(name) is True for name in GATES}
    buyer_checks = {
        "contracted": buyer.get("contracted") is True,
        "service_match": buyer.get("service_match") is True,
        "territory_match": buyer.get("territory_match") is True,
        "capacity_verified": buyer.get("capacity_verified") is True,
        "terms_accepted": buyer.get("terms_accepted") is True,
        "delivery_permission": buyer.get("delivery_permission") is True,
    }
    missing = [f"request.{k}" for k, v in checks.items() if not v]
    missing += [f"buyer.{k}" for k, v in buyer_checks.items() if not v]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "vertical": vertical,
        "quote_qualification": "READY_FOR_HUMAN_REVIEW" if all(checks.values()) else "HOLD",
        "match_review": "READY_FOR_HUMAN_REVIEW" if not missing else "HOLD",
        "missing_evidence": missing,
        "recommended_organic_offer": f"Request a {vertical} quote from a qualified provider",
        "outbound_authorized": False,
        "customer_data_disclosed": False,
        "lead_delivered": False,
        "crm_writes": False,
        "payment_execution": False,
        "revenue_verified": False,
    }
