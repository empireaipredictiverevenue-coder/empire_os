"""Authenticated tenant-scoped *name-only* duplicate preview for six solar companies.

Consumes only existing Revenue CRM 040 tenant-safe prospect view rows after
the existing signed-identity resolver and dedicated DB-role checks. No
cross-tenant data, contact emails, claimed buyer intent or CRM mutation.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from uuid import UUID

COMPANIES = frozenset((
    "GB NRG", "Perfect Sense Energy", "Solar4Good",
    "Sustain Commercial Solar", "SOL PV Group", "100% Renewables",
))

MAX_WINDOW = 500
MAX_DISCLOSED_CANDIDATES = 12
SCHEMA = "empire.workspace_solar_tenant_prospect_name_preview.v1"


class TenantProspectMatchHeld(ValueError):
    """Inconsistent authenticated CRM source; do not infer contact linkage."""


def _uuid(raw: object) -> str:
    if not isinstance(raw, str):
        raise TenantProspectMatchHeld("INVALID_TENANT_OR_PROSPECT_IDENTIFIER")
    try:
        value = str(UUID(raw))
    except (ValueError, TypeError, AttributeError):
        raise TenantProspectMatchHeld("INVALID_TENANT_OR_PROSPECT_IDENTIFIER") from None
    if value != raw:
        raise TenantProspectMatchHeld("NONCANONICAL_TENANT_OR_PROSPECT_IDENTIFIER")
    return value


def _name(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise TenantProspectMatchHeld("INVALID_CRM_BUSINESS_NAME")
    cleaned = unicodedata.normalize("NFKC", value)
    if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
        raise TenantProspectMatchHeld("UNSAFE_CRM_BUSINESS_NAME")
    name = " ".join(cleaned.casefold().split())
    if not name:
        raise TenantProspectMatchHeld("INVALID_CRM_BUSINESS_NAME")
    return name


def preview_six_tenant_prospect_name_matches(
    prospects: Sequence[Mapping[str, object]], *,
    authenticated_tenant_id: str,
    window_limit: int = MAX_WINDOW,
) -> dict:
    """Names imply possible duplicates, NEVER tenant contact authority."""
    tenant = _uuid(authenticated_tenant_id)
    if (type(window_limit) is not int or not 1 <= window_limit <= MAX_WINDOW
            or not isinstance(prospects, (list, tuple))
            or len(prospects) > window_limit):
        raise TenantProspectMatchHeld("UNBOUNDED_CRM_TENANT_VIEW")
    matched = defaultdict(list)
    seen_ids: set[str] = set()
    target_names = {_name(company): company for company in COMPANIES}
    for row in prospects:
        if not isinstance(row, Mapping):
            raise TenantProspectMatchHeld("UNTRUSTED_TENANT_PROSPECT_ROW")
        if _uuid(row.get("tenant_id")) != tenant:
            raise TenantProspectMatchHeld("CROSS_TENANT_CRM_ROW")
        pid = _uuid(row.get("prospect_id"))
        if pid in seen_ids:
            raise TenantProspectMatchHeld("DUPLICATE_TENANT_CRM_PROSPECT_ID")
        seen_ids.add(pid)
        normalized = _name(row.get("business_name"))
        company = target_names.get(normalized)
        if company is not None:
            matched[company].append(pid)
    complete_window = len(prospects) < window_limit
    items = []
    for company in sorted(COMPANIES):
        ids = sorted(matched[company])
        if len(ids) > 1:
            state = "POSSIBLE_MULTIPLE_NAME_MATCHES_REQUIRE_DEDUP_REVIEW"
        elif len(ids) == 1:
            state = "POSSIBLE_NAME_MATCH_REQUIRES_IDENTITY_REVIEW"
        elif not complete_window:
            state = "NO_MATCH_IN_PARTIAL_TENANT_VIEW_NOT_EXHAUSTIVE"
        else:
            state = "NO_EXACT_NAME_MATCH_IN_VISIBLE_TENANT_VIEW"
        items.append({
            "company": company,
            "status": state,
            "possible_name_match_count": len(ids),
            "candidate_prospect_ids": ids[:MAX_DISCLOSED_CANDIDATES],
            "candidate_ids_truncated": len(ids) > MAX_DISCLOSED_CANDIDATES,
            "name_match_does_not_verify_original_contact": True,
            "tenanted_prospect_row_is_not_email_sender_proof": True,
            "crm_contact_binding_verified": False,
            "crm_conversation_created": False,
            "outbound_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "TENANT_AUTHENTICATED_PROSPECT_NAME_DUPLICATE_REVIEW_ONLY",
        "tenant_scope_source": "existing_signed_crm_principal_and_dedicated_db_reader",
        "tenant_view_row_count": len(prospects),
        "requested_window_limit": window_limit,
        "tenant_visible_window_exhaustive": complete_window,
        "six_historical_companies_checked": 6,
        "possible_exact_company_name_matches": sum(len(matched[c]) for c in COMPANIES),
        "items": items,
        "canonical_contact_identity_verified": False,
        "historical_outbound_intent_bound": False,
        "tenant_contact_authority_verified": False,
        "crm_mutation": False,
        "outbound_sent": False,
        "payment_execution": False,
        "execution_authority": "none",
    }
