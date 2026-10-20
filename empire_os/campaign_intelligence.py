"""Evidence-bound, multi-channel TAM campaign intelligence (offline owner API).

Adds real cross-channel prioritisation and paid-customer experiment learning to
the existing full-funnel GTM workflow. It never creates contacts, claims human
identity from tracking links, sends outreach or reports invented revenue.

Owners must authenticate receipts, CRM identity, suppression, permission and
settlements BEFORE creating these projections. Boolean fields here are strict
contracts for trusted server callers, NOT an API for raw browser input.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, Mapping

SCHEMA = "empire.gtm.evidence_intelligence.v1"
_HEX = re.compile(r"^[a-f0-9]{32}$")
_TENANT = re.compile(r"^tenant_[a-z0-9]{8,40}$")
_CAMPAIGN = re.compile(r"^campaign_[a-f0-9]{24}$")
_SCOPES = {"GB:solar:buyers", "US:roofing:buyers"}
_SOURCE = {
    "email_delivered": ("email_provider", 0),
    "email_link_clicked": ("first_party_click_gateway", 1),
    "consented_site_visit": ("first_party_site", 2),
    "consented_offer_page_visit": ("first_party_site", 3),
    "verified_public_procurement": ("verified_public_intent_source", 5),
    "public_company_growth_signal": ("verified_public_intent_source", 2),
    "optin_enquiry": ("canonical_crm", 8),
    "verified_social_inbound_enquiry": ("canonical_crm", 8),
    "demo_request": ("canonical_crm", 10),
    "direct_buyer_question": ("canonical_crm", 8),
    "pricing_request": ("canonical_crm", 10),
    "meeting_booked": ("canonical_crm", 12),
    "terms_accepted": ("canonical_crm", 14),
    "verified_paying_customer": ("canonical_commercial_ledger", 16),
    "unsubscribe": ("canonical_crm", -1),
    "hard_bounce": ("email_provider", -1),
    "explicit_not_interested": ("canonical_crm", -1),
}
_NEGATIVE = {"unsubscribe", "hard_bounce", "explicit_not_interested"}
_WEAK = {
    "email_delivered", "email_link_clicked", "consented_site_visit",
    "consented_offer_page_visit", "verified_public_procurement",
    "public_company_growth_signal",
}
_DIRECT = {
    "optin_enquiry", "verified_social_inbound_enquiry",
    "demo_request", "direct_buyer_question",
    "pricing_request", "meeting_booked",
}
_ACTION_ORDER = (
    "STOP_AND_SUPPRESS", "HOLD_IDENTITY_OR_SOURCE", "HOLD_INBOUND_BASIS",
    "REVIEW_EXISTING_CUSTOMER", "REVIEW_ACCEPTED_TERMS",
    "SAME_BUSINESS_DAY_SALES_REVIEW", "INTERNAL_RESEARCH_ONLY", "NO_OBSERVED_INTENT",
)


class CampaignIntelligenceHeld(ValueError):
    """Source conflict, trust gap or materially unsafe campaign evidence."""


def _aware(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise CampaignIntelligenceHeld("AWARE_EVENT_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _opaque(value: str) -> bool:
    return type(value) is str and bool(_HEX.fullmatch(value)) and value != "0" * 32


@dataclass(frozen=True)
class AccountIntelligenceContext:
    tenant_ref: str
    account_key: str
    market_scope: str
    campaign_id: str
    canonical_account_verified: bool
    suppression_clear: bool
    inbound_response_basis_verified: bool
    marketing_contact_basis_verified: bool
    offer_evidence_current: bool


@dataclass(frozen=True)
class TrustedCampaignSignal:
    event_id: str
    tenant_ref: str
    account_key: str
    market_scope: str
    campaign_id: str
    kind: str
    source: str
    observed_at: datetime
    source_receipt_verified: bool
    canonical_account_link_verified: bool
    purpose_lawfulness_verified: bool


def _context(ctx: AccountIntelligenceContext) -> None:
    if (
        type(ctx) is not AccountIntelligenceContext
        or not _opaque(ctx.account_key)
        or type(ctx.tenant_ref) is not str
        or not _TENANT.fullmatch(ctx.tenant_ref)
        or ctx.market_scope not in _SCOPES
        or type(ctx.campaign_id) is not str
        or not _CAMPAIGN.fullmatch(ctx.campaign_id)
    ):
        raise CampaignIntelligenceHeld("CANONICAL_ACCOUNT_CONTEXT_INVALID")
    for field in (
        "canonical_account_verified", "suppression_clear",
        "inbound_response_basis_verified", "marketing_contact_basis_verified",
        "offer_evidence_current",
    ):
        if type(getattr(ctx, field)) is not bool:
            raise CampaignIntelligenceHeld("CANONICAL_ACCOUNT_GATES_UNKNOWN")


def _signal(signal: TrustedCampaignSignal, ctx: AccountIntelligenceContext, now: datetime) -> None:
    if type(signal) is not TrustedCampaignSignal or not _opaque(signal.event_id):
        raise CampaignIntelligenceHeld("TRUSTED_EVENT_ID_REQUIRED")
    if (
        signal.tenant_ref != ctx.tenant_ref
        or signal.account_key != ctx.account_key
        or signal.market_scope != ctx.market_scope
        or signal.campaign_id != ctx.campaign_id
    ):
        raise CampaignIntelligenceHeld("CROSS_TENANT_ACCOUNT_OR_CAMPAIGN_SIGNAL")
    if signal.kind not in _SOURCE or signal.source != _SOURCE[signal.kind][0]:
        raise CampaignIntelligenceHeld("UNSUPPORTED_EVENT_SOURCE_PAIR")
    if (signal.source_receipt_verified is not True
            or signal.canonical_account_link_verified is not True
            or signal.purpose_lawfulness_verified is not True):
        raise CampaignIntelligenceHeld("SOURCE_RECEIPT_IDENTITY_OR_PURPOSE_UNVERIFIED")
    observed = _aware(signal.observed_at)
    if observed > now + timedelta(minutes=1) or observed < now - timedelta(days=365):
        raise CampaignIntelligenceHeld("EVENT_TIME_OUTSIDE_SUPPORTED_EVIDENCE_WINDOW")


def review_account_intelligence(
    ctx: AccountIntelligenceContext,
    signals: Iterable[TrustedCampaignSignal], *, now: datetime,
) -> dict:
    """Defensible *account* review; never equates a click to a person or buyer.

    Raw account identifiers, tokens and event IDs never leave this function.
    Repeated clicks or reloads cannot accumulate enough score to create
    sales eligibility. Negative evidence takes priority over every score.
    """
    _context(ctx)
    now = _aware(now)
    ordered = list(signals)
    if len(ordered) > 250:
        raise CampaignIntelligenceHeld("PER_ACCOUNT_SIGNAL_BATCH_TOO_LARGE")
    seen: dict[str, TrustedCampaignSignal] = {}
    recent: dict[str, set[str]] = {}
    active: list[TrustedCampaignSignal] = []
    stop_kinds: set[str] = set()
    stale = 0
    duplicates = 0
    for signal in ordered:
        _signal(signal, ctx, now)
        old = seen.get(signal.event_id)
        if old is not None:
            if old != signal:
                raise CampaignIntelligenceHeld("CONFLICTING_EVENT_ID_REPLAY")
            duplicates += 1
            continue
        seen[signal.event_id] = signal
        if signal.kind in _NEGATIVE:
            stop_kinds.add(signal.kind)
            continue
        if now - _aware(signal.observed_at) > timedelta(days=45):
            stale += 1
            continue
        active.append(signal)
        recent.setdefault(signal.kind, set()).add(
            _aware(signal.observed_at).date().isoformat()
        )
    # One contribution per kind and day, max two days per kind.
    # Score explains breadth of verified observations, NOT conversion probability.
    points = sum(
        min(len(days), 2) * _SOURCE[kind][1]
        for kind, days in recent.items()
    )
    kinds = set(recent)
    if stop_kinds or not ctx.suppression_clear:
        action = "STOP_AND_SUPPRESS"
    elif not ctx.canonical_account_verified:
        action = "HOLD_IDENTITY_OR_SOURCE"
    elif "verified_paying_customer" in kinds:
        action = "REVIEW_EXISTING_CUSTOMER"
    elif "terms_accepted" in kinds:
        action = "REVIEW_ACCEPTED_TERMS"
    elif kinds & _DIRECT:
        if ctx.inbound_response_basis_verified and ctx.offer_evidence_current:
            action = "SAME_BUSINESS_DAY_SALES_REVIEW"
        else:
            action = "HOLD_INBOUND_BASIS"
    elif kinds & _WEAK:
        action = "INTERNAL_RESEARCH_ONLY"
    else:
        action = "NO_OBSERVED_INTENT"
    return {
        "schema_version": SCHEMA,
        "action": action,
        "signal_strength_points_not_probability": points,
        "distinct_verified_signal_kinds": len(kinds),
        "distinct_receipt_sources": len({s.source for s in active}),
        "recent_verified_observations": len(active),
        "stale_positive_observations": stale,
        "replayed_event_ids_discarded": duplicates,
        "hard_stop_signal_count": len(stop_kinds),
        "marketing_contact_eligible_from_signals": False,
        "human_identity_inferred_from_click": False,
        "auto_send": False,
        "auto_retarget": False,
        "auto_budget": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }


def review_private_account_portfolio(
    rows: Iterable[tuple[AccountIntelligenceContext, Iterable[TrustedCampaignSignal]]],
    *, now: datetime,
) -> dict:
    """Aggregate existing owner-scoped accounts, not discover/prospect people."""
    items = list(rows)
    if len(items) > 500:
        raise CampaignIntelligenceHeld("PORTFOLIO_LIMIT_EXCEEDED")
    seen: set[tuple[str, str, str]] = set()
    actions: Counter[str] = Counter()
    total = 0
    for ctx, signals in items:
        _context(ctx)
        key = (ctx.tenant_ref, ctx.account_key, ctx.campaign_id)
        if key in seen:
            raise CampaignIntelligenceHeld("DUPLICATE_ACCOUNT_PORTFOLIO_IDENTITY")
        seen.add(key)
        result = review_account_intelligence(ctx, signals, now=now)
        actions[result["action"]] += 1
        total += result["recent_verified_observations"]
    return {
        "schema_version": "empire.gtm.account_signal_portfolio.v1",
        "accounts_reviewed": len(seen),
        "verified_observation_count": total,
        "action_counts": {key: actions[key] for key in _ACTION_ORDER},
        "private_account_identifiers_exposed": 0,
        "scheduled_communications": 0,
        "audience_exports": 0,
        "execution_authority": "NONE",
    }

EXPERIMENT_ARMS = (
    "no_marketing_holdout",
    "buyer_inventory_fit_offer",
    "revenue_leak_signal_offer",
    "verified_market_opportunity_brief",
)


@dataclass(frozen=True)
class TrustedArmOutcome:
    arm: str
    assigned_accounts: int
    delivered_accounts: int
    paying_customers: int
    unsubscribe_accounts: int
    complaint_accounts: int
    realized_gp_cents: int | None
    recognized_revenue_cents: int | None
    canonical_receipts_verified: bool
    assignment_integrity_verified: bool
    outcome_window_closed: bool
    financial_receipts_verified: bool


def evaluate_real_customer_experiment(
    arms: Iterable[TrustedArmOutcome], *,
    minimum_assigned_per_arm: int = 50,
) -> dict:
    """Account-assigned outcome lens; a holdout HAS NO email deliveries.

    This is not a significance test, causal proof or autonomous winner. It
    rejects missing buyer/ledger proof and explicit complaint danger.
    """
    if type(minimum_assigned_per_arm) is not int or not 20 <= minimum_assigned_per_arm <= 10000:
        raise CampaignIntelligenceHeld("EXPERIMENT_SAMPLE_POLICY_INVALID")
    items = list(arms)
    if len(items) != len(EXPERIMENT_ARMS) or any(
        type(x) is not TrustedArmOutcome for x in items
    ) or {x.arm for x in items} != set(EXPERIMENT_ARMS):
        raise CampaignIntelligenceHeld("ALL_FOUR_VERIFIED_EXPERIMENT_ARMS_REQUIRED")
    status = "OBSERVATIONAL_RESULTS_NOT_READY"
    blockers: list[str] = []
    reviews = []
    for row in items:
        if any(type(v) is not int or v < 0 for v in (
            row.assigned_accounts, row.delivered_accounts,
            row.paying_customers, row.unsubscribe_accounts,
            row.complaint_accounts
        )):
            raise CampaignIntelligenceHeld("INVALID_EXPERIMENT_COUNTS")
        if (row.assigned_accounts == 0
                or row.delivered_accounts > row.assigned_accounts
                or row.paying_customers > row.assigned_accounts
                or row.unsubscribe_accounts > row.delivered_accounts
                or row.complaint_accounts > row.delivered_accounts):
            raise CampaignIntelligenceHeld("EXPERIMENT_FUNNEL_ACCOUNT_COUNTS_INCOHERENT")
        for field in (
            "canonical_receipts_verified", "assignment_integrity_verified",
            "outcome_window_closed", "financial_receipts_verified",
        ):
            if type(getattr(row, field)) is not bool:
                raise CampaignIntelligenceHeld("EXPERIMENT_RECEIPT_GATE_UNKNOWN")
        if row.arm == "no_marketing_holdout" and (
            row.delivered_accounts or row.unsubscribe_accounts or row.complaint_accounts
        ):
            raise CampaignIntelligenceHeld("HOLDOUT_MUST_HAVE_ZERO_MARKETING_DELIVERY")
        if row.realized_gp_cents is not None and (
            type(row.realized_gp_cents) is not int or abs(row.realized_gp_cents) > 10**14
        ):
            raise CampaignIntelligenceHeld("INVALID_PROFIT_LEDGER_VALUE")
        if row.recognized_revenue_cents is not None and (
            type(row.recognized_revenue_cents) is not int
            or not 0 <= row.recognized_revenue_cents <= 10**14
        ):
            raise CampaignIntelligenceHeld("INVALID_RECOGNIZED_REVENUE")
        if row.financial_receipts_verified and (
            row.realized_gp_cents is None or row.recognized_revenue_cents is None
        ):
            raise CampaignIntelligenceHeld("FINANCIAL_PROOF_WITHOUT_AMOUNTS")
        trusted = (
            row.canonical_receipts_verified
            and row.assignment_integrity_verified
            and row.outcome_window_closed
            and row.assigned_accounts >= minimum_assigned_per_arm
        )
        if not trusted:
            blockers.append(f"{row.arm}:RECEIPT_ASSIGNMENT_WINDOW_OR_SIZE")
        financial = trusted and row.financial_receipts_verified
        complaint_rate = row.complaint_accounts / row.delivered_accounts if row.delivered_accounts else 0.0
        opt_out_rate = row.unsubscribe_accounts / row.delivered_accounts if row.delivered_accounts else 0.0
        unsafe = row.arm != "no_marketing_holdout" and (
            complaint_rate > 0.01 or opt_out_rate > 0.05
        )
        if unsafe:
            blockers.append(f"{row.arm}:COMPLAINT_OR_OPT_OUT_RATE")
        reviews.append({
            "arm": row.arm,
            "verified_paying_customers": row.paying_customers if trusted else None,
            "assigned_accounts": row.assigned_accounts if trusted else None,
            "delivered_accounts": row.delivered_accounts if trusted else None,
            "paid_customer_rate_per_assigned_account": (
                round(row.paying_customers / row.assigned_accounts, 6) if trusted else None
            ),
            "realized_gp_per_assigned_account_cents": (
                round(row.realized_gp_cents / row.assigned_accounts, 2)
                if financial else None
            ),
            "recognized_revenue_cents": row.recognized_revenue_cents if financial else None,
            "complaint_or_optout_hold": unsafe,
            "receipts_for_this_arm_accepted": trusted,
            "financial_receipts_accepted": financial,
        })
    matched = {r["arm"]: r for r in reviews}
    fully_trusted = all(r["receipts_for_this_arm_accepted"] for r in reviews)
    fully_financial = all(r["financial_receipts_accepted"] for r in reviews)
    candidate = None
    metric = None
    # A risk-flagged arm cannot be a winner, even with better conversions.
    if fully_trusted:
        choices = [r for r in reviews if r["arm"] != "no_marketing_holdout" and not r["complaint_or_optout_hold"]]
        if choices:
            metric = ("realized_gp_per_assigned_account_cents"
                      if fully_financial else "paid_customer_rate_per_assigned_account")
            control = matched["no_marketing_holdout"][metric]
            choices.sort(key=lambda row: (row[metric], row["arm"]), reverse=True)
            best = choices[0]
            # Only choose a *descriptive* positive winner above holdout,
            # never claim significance from aggregate counts alone.
            if fully_financial and best[metric] <= 0:
                status = "NO_POSITIVE_REALIZED_GROSS_PROFIT"
            elif best[metric] > control and best["verified_paying_customers"] > 0:
                candidate = best["arm"]
                status = "DESCRIPTIVE_OFFER_CANDIDATE_HUMAN_REVIEW_ONLY"
            else:
                status = "NO_POSITIVE_OBSERVED_OFFER_ADVANTAGE"
        else:
            status = "ALL_TREATMENT_ARMS_ON_SAFETY_HOLD"
    return {
        "schema_version": "empire.gtm.real_customer_experiment_intelligence.v1",
        "status": status,
        "primary_metric": "verified_paying_customers_per_randomly_assigned_account",
        "holdout_delivery_denominator_is_zero": True,
        "candidate_offer_arm": candidate,
        "comparison_metric": metric,
        "arm_reviews": reviews,
        "data_quality_holds": sorted(set(blockers)),
        "significance_or_causal_lift_claimed": False,
        "return_on_spend_claimed": False,
        "auto_budget_raised": False,
        "campaign_activated": False,
        "execution_authority": "NONE",
    }

# Conversion diagnosis adapts the pre-existing Conversion Intelligence specialist.
# It does not establish receipts or invent visitors, clicks, deals or spend.
_CAMPAIGN_FUNNEL_STAGES = {
    "visitor_to_lead": "test_landing_page_offer_and_form_clarity",
    "delivered_outreach_to_reply": "test_qualified_market_fit_offer_and_subject_copy",
    "reply_to_qualified_conversation": "review_buyer_fit_handling_and_response_quality",
    "conversation_to_terms": "review_commercial_offer_and_proof",
    "terms_to_acceptance": "review_terms_and_buyer_onboarding_friction",
    "acceptance_to_payment": "review_billing_and_checkout_friction",
    "payment_to_fulfilment": "review_production_delivery_friction",
}


@dataclass(frozen=True)
class TrustedCampaignFunnelStage:
    stage: str
    entered_accounts: int
    converted_accounts: int
    canonical_source_ref: str
    source_receipts_verified: bool
    campaign_attribution_verified: bool
    outcome_window_closed: bool


def diagnose_campaign_conversion_bottlenecks(
    stages: Iterable[TrustedCampaignFunnelStage], *,
    minimum_entered: int = 20,
) -> dict:
    """Apply existing specialist to independently verified funnel receipts.

    Rates are DESCRIPTIVE, not estimates of incremental revenue or conversion
    probability. Empty/unverified stages remain unknown, never zero by fiat.
    """
    from empire_os.conversion_intelligence import (
        ConversionStageEvidence, review_stage,
    )
    if type(minimum_entered) is not int or minimum_entered < 20:
        raise CampaignIntelligenceHeld("BOTTLE_NECK_SAMPLE_POLICY_INVALID")
    items = list(stages)
    if not 1 <= len(items) <= len(_CAMPAIGN_FUNNEL_STAGES):
        raise CampaignIntelligenceHeld("FUNNEL_STAGE_COUNT_INVALID")
    seen = set()
    reviews = []
    for item in items:
        if (type(item) is not TrustedCampaignFunnelStage
                or item.stage not in _CAMPAIGN_FUNNEL_STAGES
                or item.stage in seen):
            raise CampaignIntelligenceHeld("UNKNOWN_OR_DUPLICATE_FUNNEL_STAGE")
        seen.add(item.stage)
        if any(type(v) is not int or v < 0 for v in (
            item.entered_accounts, item.converted_accounts
        )) or item.converted_accounts > item.entered_accounts:
            raise CampaignIntelligenceHeld("FUNNEL_ACCOUNT_COUNTS_INVALID")
        if (type(item.canonical_source_ref) is not str
                or not re.fullmatch(r"canonical:[a-z_]{3,40}:[a-zA-Z0-9_-]{8,80}",
                                    item.canonical_source_ref)):
            raise CampaignIntelligenceHeld("CANONICAL_FUNNEL_PROVENANCE_REQUIRED")
        verified = (
            item.source_receipts_verified is True
            and item.campaign_attribution_verified is True
            and item.outcome_window_closed is True
        )
        if not verified:
            reviews.append({
                "stage": item.stage, "conversion_rate": None,
                "missing_proof": True, "observed_accounts": None,
                "recommended_experiment": None,
            })
            continue
        existing = review_stage(ConversionStageEvidence(
            stage=item.stage, entered=item.entered_accounts,
            converted=item.converted_accounts,
            evidence_ref=item.canonical_source_ref,
        ))
        reviews.append({
            "stage": item.stage,
            "conversion_rate": (
                existing.conversion_rate
                if existing.review_ready and item.entered_accounts >= minimum_entered
                else None
            ),
            "missing_proof": not existing.review_ready,
            "observed_accounts": item.entered_accounts,
            "recommended_experiment": _CAMPAIGN_FUNNEL_STAGES[item.stage],
        })
    known = [
        row for row in reviews
        if row["conversion_rate"] is not None
    ]
    known.sort(key=lambda r: (r["conversion_rate"], -r["observed_accounts"], r["stage"]))
    next_stage = known[0] if known else None
    return {
        "schema_version": "empire.gtm.campaign_conversion_bottleneck.v1",
        "status": "DESCRIPTIVE_EXPERIMENT_OPPORTUNITY_ONLY" if known
                  else "HOLD_INSUFFICIENT_VERIFIED_FUNNEL",
        "verified_stages_with_sufficient_sample": len(known),
        "reviewed_stages": reviews,
        "lowest_observed_stage": next_stage["stage"] if next_stage else None,
        "next_test": next_stage["recommended_experiment"] if next_stage else None,
        "incremental_revenue_or_causal_lift_claimed": False,
        "campaign_mutated": False,
        "execution_authority": "NONE",
    }
