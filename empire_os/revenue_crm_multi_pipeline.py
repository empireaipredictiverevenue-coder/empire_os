"""Tenant-bound, evidence-first multi-motion board for the existing Revenue CRM.

Different sales motions receive distinct pipeline and stage schemas. A CRM
prospect with no explicitly stored pipeline binding stays in triage; geography
and industry are filters, NOT separate pipelines. Buyer account cards come
only from the canonical buyer view and never imply a signed buyer agreement.
No CRM writes, mail, task creation, stage mutations or revenue inference.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID

SCHEMA = "empire.revenue_crm.multi_pipeline_board.v1"
PIPELINES = (
    ("service_customers", "B2B Services & Diagnostics", "sell_service",
     ("research", "need_review", "discovery", "proposal", "payment_review", "delivery_review", "hold"),
     ("assessment", "consultancy", "SEO / AEO / GEO", "AI automation")),
    ("software_subscriptions", "SaaS & Predictive Intelligence", "sell_subscription",
     ("research", "demo", "trial_review", "proposal", "subscription_review", "activation_review", "hold"),
     ("EmpireOS", "Predictive Cloud", "AI Receptionist", "CommerceOS")),
    ("enterprise_procurement", "Enterprise & Public Procurement", "tender_contract",
     ("opportunity", "eligibility", "bid_review", "submitted", "award_review", "delivery_review", "hold"),
     ("enterprise", "healthcare / NHS", "public procurement")),
    ("lead_buyers", "Lead & Call Buyers", "lead_inventory_buyers",
     ("buyer_research", "identity_review", "buy_box_review", "capacity_review", "terms_review", "pilot_review", "hold"),
     ("UK / US", "calls", "forms", "appointments", "bookings")),
    ("publisher_partners", "Publisher & Supply Partners", "recruit_supply",
     ("research", "rights_review", "source_verification", "terms_review", "pilot_review", "settlement_review", "hold"),
     ("owned organic", "external publishers", "source rights")),
    ("owned_consumer_enquiries", "Owned Consumer Acquisition", "inbound_job_intake",
     ("source_research", "live_source_review", "consent_review", "qualified_request", "allocation_review", "delivery_review", "hold"),
     ("roofing", "solar", "HVAC", "restoration", "National Storm Hub")),
    ("rank_rent", "Rank & Rent / Contractor Partners", "lease_local_asset",
     ("market", "contractor_review", "terms_review", "pilot_review", "rental_review", "renewal_review", "hold"),
     ("microsites", "contractors", "local demand")),
    ("data_api", "Data, API & Intelligence Licensing", "license_rights_cleared_data",
     ("use_case", "rights_review", "buyer_review", "sample_review", "contract_review", "delivery_review", "hold"),
     ("data exchange", "API feeds", "licensed intelligence")),
    ("affiliate_referrals", "Affiliate & SaaS Referrals", "affiliate_agreement",
     ("programme", "eligibility", "source_review", "tracking_review", "commission_review", "settlement_review", "hold"),
     ("Awin", "software referrals", "approved publisher commissions")),
    ("commerce_partners", "CommerceOS & Merchant Partnerships", "seller_and_supplier_onboarding",
     ("merchant", "eligibility", "supplier_review", "demo", "contract_review", "activation_review", "hold"),
     ("CommerceOS", "marketplaces", "verified wholesalers")),
)
PIPELINE_IDS = frozenset(p[0] for p in PIPELINES)
ALLOWED_FORMATS = ("call", "form", "appointment", "booking", "subscription", "contract", "referral", "licence", "commerce")
PROSPECT_STAGE = {
    "service_customers": {
        "engaged_conversation_review": "discovery", "proposal_review": "proposal",
        "awaiting_payment_review": "payment_review", "fulfilment_review": "delivery_review",
        "contact_hold": "hold",
    },
    "software_subscriptions": {
        "engaged_conversation_review": "demo", "proposal_review": "proposal",
        "awaiting_payment_review": "subscription_review", "fulfilment_review": "activation_review",
        "contact_hold": "hold",
    },
    "enterprise_procurement": {
        "engaged_conversation_review": "eligibility", "proposal_review": "bid_review",
        "awaiting_payment_review": "award_review", "fulfilment_review": "delivery_review",
        "contact_hold": "hold",
    },
    "publisher_partners": {
        "engaged_conversation_review": "source_verification", "proposal_review": "terms_review",
        "awaiting_payment_review": "pilot_review", "fulfilment_review": "settlement_review",
        "contact_hold": "hold",
    },
    "owned_consumer_enquiries": {
        "engaged_conversation_review": "consent_review", "proposal_review": "allocation_review",
        "awaiting_payment_review": "allocation_review", "fulfilment_review": "delivery_review",
        "contact_hold": "hold",
    },
    "rank_rent": {
        "engaged_conversation_review": "contractor_review", "proposal_review": "terms_review",
        "awaiting_payment_review": "rental_review", "fulfilment_review": "renewal_review",
        "contact_hold": "hold",
    },
    "data_api": {
        "engaged_conversation_review": "sample_review", "proposal_review": "contract_review",
        "awaiting_payment_review": "contract_review", "fulfilment_review": "delivery_review",
        "contact_hold": "hold",
    },
    "affiliate_referrals": {
        "engaged_conversation_review": "source_review", "proposal_review": "tracking_review",
        "awaiting_payment_review": "commission_review", "fulfilment_review": "settlement_review",
        "contact_hold": "hold",
    },
    "commerce_partners": {
        "engaged_conversation_review": "demo", "proposal_review": "contract_review",
        "awaiting_payment_review": "contract_review", "fulfilment_review": "activation_review",
        "contact_hold": "hold",
    },
}
NEXT_ACTIONS = {
    "unqualified_evidence_review": "Verify source, commercial role and buying need",
    "engaged_conversation_review": "Review the authenticated conversation and next activity",
    "proposal_review": "Review proposal scope, buyer acceptance and terms",
    "awaiting_payment_review": "Reconcile payment status; do not recognise revenue without settlement",
    "fulfilment_review": "Review delivery and acceptance evidence",
    "contact_hold": "Review consent, suppression or delivery hold",
}

class PipelineProjectionError(ValueError):
    """Untrusted, tenant-mismatched or inconsistent input must fail closed."""


def _tenant(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise PipelineProjectionError("invalid_authenticated_tenant") from None


def _stamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        at = value
    elif isinstance(value, str) and 0 < len(value) <= 64:
        try:
            at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return at.astimezone(timezone.utc) if at.tzinfo else None


def _safe_text(value: Any, *, max_len: int = 120) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())
    return clean[:max_len] if clean else None


def _observed_status(row: Mapping[str, Any]) -> str:
    from empire_os.revenue_crm_journeys import _stage
    return _stage(row)[0]


def _observed_at(row: Mapping[str, Any]) -> datetime | None:
    timestamps = [t for field in (
        "conversation_updated_at", "closer_updated_at",
        "fulfilment_updated_at", "buyer_capacity_verified_at",
        "capacity_verified_at", "commercial_terms_verified_at",
        "delivery_verified_at"
    ) if (t := _stamp(row.get(field))) is not None]
    return max(timestamps) if timestamps else None


def _explicit_pipeline(row: Mapping[str, Any]) -> str:
    # Current canonical revenue_crm_prospects view has no pipeline_id.
    # A caller's niche, industry, country or source-score is not a binding.
    value = row.get("pipeline_id")
    return value if type(value) is str and value in PIPELINE_IDS and value != "lead_buyers" else "unclassified"


def _prospect_card(row: Mapping[str, Any], tenant: str, now: datetime) -> dict[str, Any]:
    if _tenant(row.get("tenant_id")) != tenant:
        raise PipelineProjectionError("cross_tenant_prospect")
    ident = _tenant(row.get("prospect_id"))
    pipeline_id = _explicit_pipeline(row)
    source_stage = _observed_status(row)
    stages = PROSPECT_STAGE.get(pipeline_id, {})
    stage = stages.get(source_stage, "hold" if source_stage == "contact_hold" else None)
    if stage is None:
        stage = "triage" if pipeline_id == "unclassified" else next(
            p[3][0] for p in PIPELINES if p[0] == pipeline_id
        )
    observed_at = _observed_at(row)
    return {
        "id": ident, "source_kind": "crm_prospect", "pipeline_id": pipeline_id,
        "stage": stage, "title": _safe_text(row.get("business_name")) or "Unnamed prospect",
        "industry": _safe_text(row.get("niche"), max_len=64),
        "market": "UNVERIFIED",  # metro is not independently verified country.
        "metro": _safe_text(row.get("metro"), max_len=64),
        "outcome_format": "UNVERIFIED",
        "source_status": _safe_text(row.get("prospect_status"), max_len=48),
        "evidence_stage": source_stage,
        "last_observed_at": observed_at.isoformat() if observed_at else None,
        "stalled_review": bool(observed_at and timedelta(days=7) <= now - observed_at),
        "next_activity_due_at": None,
        "next_activity": NEXT_ACTIONS[source_stage],
        "forecast_price_cents": row.get("price_cents") if type(row.get("price_cents")) is int
                                    and 0 <= row["price_cents"] <= 1_000_000_000 else None,
        "recognized_revenue_cents": None,
        "pipeline_binding_verified": pipeline_id != "unclassified",
        "won_verified": False, "outbound_authorized": False,
    }


def _buyer_card(row: Mapping[str, Any], tenant: str, now: datetime) -> dict[str, Any]:
    if _tenant(row.get("tenant_id")) != tenant:
        raise PipelineProjectionError("cross_tenant_buyer")
    ident = _tenant(row.get("buyer_id"))
    # Current view verifies a buyer account record, not actual purchasing intent.
    terms = _stamp(row.get("commercial_terms_verified_at")) is not None
    capacity = _stamp(row.get("capacity_verified_at")) is not None
    delivered = _stamp(row.get("delivery_verified_at")) is not None
    if terms and delivered:
        stage = "pilot_review"
    elif terms:
        stage = "terms_review"
    elif capacity:
        stage = "capacity_review"
    else:
        stage = "buyer_research"
    observed_at = _observed_at(row)
    action = {
        "buyer_research": "Verify company, contract and live buyer demand",
        "capacity_review": "Validate accepted territories, daily caps and genuine availability",
        "terms_review": "Review exact payable events, traffic permissions and signed terms",
        "pilot_review": "Inspect accepted test events and independently settled outcomes",
    }[stage]
    return {
        "id": ident, "source_kind": "canonical_buyer_account",
        "pipeline_id": "lead_buyers", "stage": stage,
        "title": _safe_text(row.get("buyer_name")) or "Unnamed buyer account",
        "industry": _safe_text(row.get("niche"), max_len=64),
        "metro": _safe_text(row.get("metro"), max_len=64),
        "market": "UNVERIFIED", "outcome_format": "UNVERIFIED",
        "source_status": _safe_text(row.get("buyer_status"), max_len=48),
        "evidence_stage": "buyer_account_observed",
        "last_observed_at": observed_at.isoformat() if observed_at else None,
        "stalled_review": bool(observed_at and timedelta(days=7) <= now - observed_at),
        "next_activity_due_at": None, "next_activity": action,
        "forecast_price_cents": None, "recognized_revenue_cents": None,
        "pipeline_binding_verified": True, "won_verified": False,
        "active_capacity_observed": bool(row.get("is_active") is True
                                         and type(row.get("available_capacity")) is int
                                         and row["available_capacity"] > 0 and capacity),
        "outbound_authorized": False,
    }


def build_multi_pipeline_board(
    prospects: Sequence[Mapping[str, Any]], buyers: Sequence[Mapping[str, Any]],
    *, authenticated_tenant_id: str, now: datetime, pipeline: str | None = None
) -> dict[str, Any]:
    tenant = _tenant(authenticated_tenant_id)
    if now.tzinfo is None:
        raise PipelineProjectionError("timezone_aware_clock_required")
    now = now.astimezone(timezone.utc)
    if pipeline is not None and pipeline not in PIPELINE_IDS | {"unclassified"}:
        raise PipelineProjectionError("unknown_pipeline_filter")
    if len(prospects) > 500 or len(buyers) > 500:
        raise PipelineProjectionError("candidate_limit_exceeded")
    if any(not isinstance(row, Mapping) for row in (*prospects, *buyers)):
        raise PipelineProjectionError("invalid_record")

    cards = [_prospect_card(row, tenant, now) for row in prospects]
    cards += [_buyer_card(row, tenant, now) for row in buyers]
    ids = [(card["source_kind"], card["id"]) for card in cards]
    if len(ids) != len(set(ids)):
        raise PipelineProjectionError("duplicate_canonical_record")
    cards.sort(key=lambda card: (not card["stalled_review"], card["title"].casefold(),card["id"]))
    stages_by_pipeline = {
        ident: tuple({"id": stage, "label": stage.replace("_", " ").title()} for stage in stages)
        for ident,_,_,stages,_ in PIPELINES
    }
    all_pipelines = [
        {
            "id": ident, "name": label, "motion": motion,
            "stages": list(stages_by_pipeline[ident]),
            "product_examples": list(examples),
            "record_count": sum(c["pipeline_id"] == ident for c in cards),
            "verified_won_count": 0,
        }
        for ident,label,motion,_,examples in PIPELINES
    ]
    all_pipelines.insert(0,{
        "id":"unclassified", "name":"Unassigned / Identity Review",
        "motion":"classify_from_verified_commercial_role",
        "stages":[{"id":"triage","label":"Needs Verified Pipeline"},{"id":"hold","label":"Contact Hold"}],
        "product_examples":[], "record_count":sum(c["pipeline_id"]=="unclassified" for c in cards),
        "verified_won_count":0,
    })
    displayed=[c for c in cards if pipeline is None or c["pipeline_id"]==pipeline]
    return {
        "schema_version":SCHEMA, "mode":"OBSERVE", "read_only":True,
        "execution_authority":"none","authenticated_tenant_scope":True,
        "pipeline_filter":pipeline,"pipelines":all_pipelines,
        "cards":displayed,"total_cards":len(cards),"displayed_cards":len(displayed),
        "unassigned_prospects":sum(c["pipeline_id"]=="unclassified" for c in cards),
        "buyer_account_cards":sum(c["source_kind"]=="canonical_buyer_account" for c in cards),
        "qualified_customer_count":None,"realized_revenue_cents":None,
        "stage_changes_persisted":False,"drag_drop_writes_enabled":False,
        "email_send_enabled":False,"crm_writes":False,"new_automations":False,
        "geography_and_industry_are_filters":True,
        "source":"existing_authenticated_tenant_bound_revenue_crm_views",
        "generated_at":now.isoformat(),
    }
