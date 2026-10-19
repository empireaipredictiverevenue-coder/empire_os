"""TREG external-tool provider policy for Empire AI Source Intelligence.

TREG is an OPTIONAL external relay, not EmpireDB or a source of buy-intent
truth. No credentials, tool calls, paid credits, PII enrichment, or outbound.
Used to evaluate capability/cost/data-rights before a human-led integration.

Third-party public catalog: github.com/superdesigndev/treg. Do not run the
remote install.sh, secret upload, or auto-registration against production.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA = "empire.treg_source_capability_preflight.v1"
MAX_MICROCOST = 1_000_000_000
CAPABILITIES = {
    "web_search": ("Search Intelligence", "treg.web.search"),
    "web_extract": ("Source Intelligence", "treg.web.extract"),
    "seo_keywords": ("SEO & Intent Engine", "catalog_discovery_only"),
    "company_enrichment": ("Waterfall B2B company identity", "catalog_discovery_only"),
    "lead_signals": ("Buyer Demand Graph", "lead-signals skill review only"),
    "social_trends": ("JEV / Organic Growth", "catalog_discovery_only"),
}
REJECTED_PURPOSES = frozenset({
    "consumer_claimants", "patient_enrichment", "personal_phone_finding",
    "mass_email_discovery", "consumer_surveillance", "cold_campaign_send",
})


@dataclass(frozen=True)
class TregProviderDecision:
    schema_version: str
    state: str
    capability: str
    empire_owner: str
    catalog_hint: str
    estimated_cost_usd: str | None
    active_spend_budget_usd: str
    funding_or_token_present: bool
    independent_source_rights_verified: bool
    third_party_processing_approved: bool
    buyer_intent_verified: bool = False
    outbound_authorized: bool = False
    tool_call_authorized: bool = False
    canonical_empiredb_writes: bool = False
    raw_result_resale_authorized: bool = False
    execution_authority: str = "none"


def evaluate_treg_capability(
    capability: str, *,
    estimated_price_usd: str | None = None,
    source_rights_verified: bool = False,
    third_party_processing_approved: bool = False,
    paid_budget_usd: str = "0",
    credentials_verified: bool = False,
    purpose: str = "b2b_company_research",
) -> dict[str, Any]:
    """Return an explainable no-execution decision, never a vendor call.

    Fee/price from a vendor catalogue may be outdated; pricing evidence
    alone cannot authorise purchasing, transferring CRM data or scraping.
    Funding must be separately approved through finance owner, which this
    module deliberately does not implement.
    """
    if capability not in CAPABILITIES:
        raise ValueError("unknown_or_unapproved_tool_capability")
    if purpose in REJECTED_PURPOSES or purpose != "b2b_company_research":
        raise ValueError("prohibited_or_unreviewed_external_data_purpose")
    if type(source_rights_verified) is not bool or type(third_party_processing_approved) is not bool:
        raise ValueError("source_rights_must_be_explicit_boolean")
    if type(credentials_verified) is not bool:
        raise ValueError("credential_receipt_must_be_explicit_boolean")
    try:
        budget = Decimal(paid_budget_usd)
        cost = Decimal(estimated_price_usd) if estimated_price_usd is not None else None
    except (InvalidOperation, TypeError):
        raise ValueError("invalid_fee_format") from None
    if (not budget.is_finite() or budget < 0 or budget > 10000
            or (cost is not None and (not cost.is_finite() or cost < 0 or cost > 10000))):
        raise ValueError("invalid_fee_bounds")

    if not third_party_processing_approved:
        state = "HOLD_EXTERNAL_PROCESSOR_AND_DATA_RIGHTS"
    elif not source_rights_verified:
        state = "HOLD_SOURCE_DATA_RIGHTS"
    elif cost is None:
        state = "HOLD_PRICE_NOT_VERIFIED"
    elif cost > budget:
        state = "HOLD_INSUFFICIENT_APPROVED_BUDGET"
    elif not credentials_verified:
        state = "HOLD_TREG_ACCESS_NOT_CONFIGURED"
    else:
        state = "REVIEW_ONLY_READY_FOR_SEPARATE_OPERATOR_GATE"
    owner, hint = CAPABILITIES[capability]
    d = TregProviderDecision(
        schema_version=SCHEMA, state=state,
        capability=capability, empire_owner=owner, catalog_hint=hint,
        estimated_cost_usd=str(cost) if cost is not None else None,
        active_spend_budget_usd=str(budget),
        funding_or_token_present=credentials_verified,
        independent_source_rights_verified=source_rights_verified,
        third_party_processing_approved=third_party_processing_approved,
    )
    return asdict(d)


def review_treg_for_empire() -> dict[str, Any]:
    """Current real policy: £0/$0 traffic/tool spend; no third-party secrets."""
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_PROVIDER_EVALUATION",
        "provider": "TREG (superdesigndev/treg)",
        "catalog_repository": "https://github.com/superdesigndev/treg",
        "capabilities": [
            evaluate_treg_capability(c) for c in CAPABILITIES
        ],
        "external_api_calls": 0,
        "paid_calls": 0,
        "external_crm_data_sent": False,
        "tool_calls_authorized": False,
        "source_to_canonical_insert_authorized": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
