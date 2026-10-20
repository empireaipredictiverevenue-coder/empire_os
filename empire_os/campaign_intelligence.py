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

# Account route planning reuses the existing outreach_account_strategy helpers.
# Only typed, trusted CRM/relationship projections are accepted. This function
# does not create a prospect or claim a real company/contact exists.

@dataclass(frozen=True)
class TrustedBuyingMember:
    person_key: str
    account_key: str
    tenant_ref: str
    decision_role: str
    observed_at: datetime
    canonical_person_link_verified: bool
    contact_route_verified: bool
    source_provenance_verified: bool


@dataclass(frozen=True)
class TrustedWarmIntroduction:
    referrer_key: str
    account_key: str
    tenant_ref: str
    kind: str
    observed_at: datetime
    relationship_verified: bool
    introduction_permission_verified: bool
    strength: str


@dataclass(frozen=True)
class TrustedAccountTouch:
    touch_key: str
    account_key: str
    tenant_ref: str
    observed_at: datetime
    canonical_delivery_receipt_verified: bool


@dataclass(frozen=True)
class TrustedAccountRoute:
    context: AccountIntelligenceContext
    buying_members: tuple[TrustedBuyingMember, ...]
    warm_introductions: tuple[TrustedWarmIntroduction, ...]
    contact_history: tuple[TrustedAccountTouch, ...]
    contact_history_complete: bool
    market_and_buyer_fit_verified: bool
    offer_fulfilment_verified: bool
    marketing_channel_lawfulness_verified: bool


def review_account_buying_route(
    route: TrustedAccountRoute, *,
    verified_signals: Iterable[TrustedCampaignSignal],
    now: datetime,
) -> dict:
    """Choose the NEXT human-review commercial play for a canonical account.

    The existing committee, verified-introduction and fatigue planners supply
    prioritisation. No PII or account identifiers leave the result. A public
    hiring observation or page click alone is never a reply/consent.
    """
    from empire_os.outreach_account_strategy import (
        INTRO_KINDS, ROLE_PRIORITY, build_buying_committee,
        choose_introduction_path, evaluate_contact_fatigue,
    )
    if type(route) is not TrustedAccountRoute:
        raise CampaignIntelligenceHeld("TRUSTED_ACCOUNT_ROUTE_REQUIRED")
    _context(route.context)
    now = _aware(now)
    for flag in (
        "contact_history_complete", "market_and_buyer_fit_verified",
        "offer_fulfilment_verified", "marketing_channel_lawfulness_verified",
    ):
        if type(getattr(route, flag)) is not bool:
            raise CampaignIntelligenceHeld("ACCOUNT_ROUTE_AUTHORITY_GATE_INVALID")
    members, introductions, touches = (
        route.buying_members, route.warm_introductions, route.contact_history
    )
    if (type(members) is not tuple or len(members) > 30
            or type(introductions) is not tuple or len(introductions) > 30
            or type(touches) is not tuple or len(touches) > 500):
        raise CampaignIntelligenceHeld("BOUNDED_ACCOUNT_ROUTE_REQUIRED")
    ctx = route.context
    people_for_existing_planner = []
    role_rows: dict[str, bool] = {}
    seen_members: set[str] = set()
    for person in members:
        if type(person) is not TrustedBuyingMember or not _opaque(person.person_key):
            raise CampaignIntelligenceHeld("CANONICAL_BUYING_PERSON_INVALID")
        if person.person_key in seen_members:
            raise CampaignIntelligenceHeld("DUPLICATE_CANONICAL_BUYING_PERSON")
        seen_members.add(person.person_key)
        if (person.account_key != ctx.account_key
                or person.tenant_ref != ctx.tenant_ref
                or person.decision_role not in ROLE_PRIORITY):
            raise CampaignIntelligenceHeld("CROSS_ACCOUNT_OR_UNKNOWN_BUYING_ROLE")
        observed = _aware(person.observed_at)
        if observed > now or now - observed > timedelta(days=90):
            raise CampaignIntelligenceHeld("BUYING_PERSON_EVIDENCE_STALE")
        if (person.canonical_person_link_verified is not True
                or person.source_provenance_verified is not True
                or type(person.contact_route_verified) is not bool):
            raise CampaignIntelligenceHeld("CANONICAL_PERSON_LINK_UNVERIFIED")
        # Internal opaque placeholders are never disclosed. No actual names,
        # generated contacts or job titles are invented.
        people_for_existing_planner.append({
            "person_id": person.person_key, "name": person.person_key,
            "title": "", "decision_role": person.decision_role,
            "contact_verified": person.contact_route_verified,
            "evidence_ref": f"canonical_person:{person.person_key}",
        })
        role_rows[person.person_key] = person.contact_route_verified
    committee = build_buying_committee(people_for_existing_planner)
    primary = next(
        (person for person in committee["members"] if
         role_rows.get(person["person_id"]) is True),
        None,
    )

    paths_for_existing_planner = []
    seen_paths: set[tuple[str, str]] = set()
    for path in introductions:
        if (type(path) is not TrustedWarmIntroduction
                or not _opaque(path.referrer_key)
                or path.account_key != ctx.account_key
                or path.tenant_ref != ctx.tenant_ref
                or path.kind not in INTRO_KINDS
                or path.strength not in {"strong", "medium", "weak"}):
            raise CampaignIntelligenceHeld("TRUSTED_INTRODUCTION_LINK_INVALID")
        key = (path.referrer_key, path.kind)
        if key in seen_paths:
            raise CampaignIntelligenceHeld("DUPLICATE_INTRODUCTION_EVIDENCE")
        seen_paths.add(key)
        when = _aware(path.observed_at)
        if when > now or now - when > timedelta(days=90):
            raise CampaignIntelligenceHeld("INTRODUCTION_EVIDENCE_STALE")
        if (path.relationship_verified is not True
                or type(path.introduction_permission_verified) is not bool):
            raise CampaignIntelligenceHeld("INTRODUCTION_PROVENANCE_UNVERIFIED")
        if path.introduction_permission_verified:
            paths_for_existing_planner.append({
                "kind": path.kind, "referrer": path.referrer_key,
                "verified": True, "relationship_strength": path.strength,
                "evidence_ref": f"canonical_relationship:{path.referrer_key}",
            })
    chosen_intro = choose_introduction_path(paths_for_existing_planner)

    seen_touches: set[str] = set()
    touches_for_existing_planner = []
    for touch in touches:
        if type(touch) is not TrustedAccountTouch or not _opaque(touch.touch_key):
            raise CampaignIntelligenceHeld("CANONICAL_CONTACT_TOUCH_INVALID")
        if touch.touch_key in seen_touches:
            raise CampaignIntelligenceHeld("DUPLICATE_CONTACT_HISTORY_EVENT")
        seen_touches.add(touch.touch_key)
        if (touch.account_key != ctx.account_key
                or touch.tenant_ref != ctx.tenant_ref
                or touch.canonical_delivery_receipt_verified is not True):
            raise CampaignIntelligenceHeld("CONTACT_HISTORY_SOURCE_UNVERIFIED")
        when = _aware(touch.observed_at)
        if when > now:
            raise CampaignIntelligenceHeld("CONTACT_HISTORY_FUTURE_EVENT")
        touches_for_existing_planner.append({"occurred_at": when.isoformat()})
    fatigue = evaluate_contact_fatigue(
        touches_for_existing_planner, now=now,
        max_touches_30d=1, min_cooldown_hours=720,
    )
    observed = review_account_intelligence(ctx, verified_signals, now=now)
    signal_action = observed["action"]
    blockers = []
    if not ctx.suppression_clear or signal_action == "STOP_AND_SUPPRESS":
        play = "STOP_AND_SUPPRESS"
    elif not ctx.canonical_account_verified:
        play = "HOLD_CANONICAL_ACCOUNT_IDENTITY"
    elif signal_action == "REVIEW_EXISTING_CUSTOMER":
        play = "EXISTING_CUSTOMER_HUMAN_REVIEW"
    elif signal_action == "REVIEW_ACCEPTED_TERMS":
        play = "COMMERCIAL_TERMS_HUMAN_REVIEW"
    elif signal_action == "SAME_BUSINESS_DAY_SALES_REVIEW":
        play = "SAME_BUSINESS_DAY_EXISTING_INBOUND_REVIEW"
    elif signal_action == "HOLD_INBOUND_BASIS":
        play = "HOLD_INBOUND_REPLY_BASIS"
    elif not route.contact_history_complete:
        play = "HOLD_INCOMPLETE_GLOBAL_CONTACT_HISTORY"
    elif fatigue["blocked"]:
        play = "HOLD_30_DAY_COMPANY_COOLDOWN"
    elif not route.market_and_buyer_fit_verified:
        play = "RESEARCH_ACCOUNT_MARKET_FIT"
    elif not route.offer_fulfilment_verified or not ctx.offer_evidence_current:
        play = "VERIFY_COMMERCIAL_OFFER_PROOF"
    elif (not route.marketing_channel_lawfulness_verified
          or not ctx.marketing_contact_basis_verified):
        play = "HOLD_MARKETING_CHANNEL_PERMISSION"
    elif chosen_intro is not None:
        play = "PREPARE_VERIFIED_WARM_INTRO_FOR_OWNER_REVIEW"
    elif primary is not None:
        play = "PREPARE_ONE_CONTACT_OFFER_FOR_OWNER_REVIEW"
    else:
        play = "RESEARCH_VERIFIED_BUYING_COMMITTEE"
    if not route.contact_history_complete:
        blockers.append("GLOBAL_CONTACT_HISTORY_NOT_VERIFIED")
    if fatigue["blocked"]:
        blockers.append("30_DAY_COMPANY_COOLDOWN_OR_CONTACT_HISTORY")
    if (not route.marketing_channel_lawfulness_verified
            or not ctx.marketing_contact_basis_verified):
        blockers.append("CHANNEL_LAWFULNESS_NOT_VERIFIED")
    if not route.offer_fulfilment_verified:
        blockers.append("OFFER_FULFILMENT_NOT_VERIFIED")
    return {
        "schema_version": "empire.gtm.buying_committee_route_review.v1",
        "recommended_play": play,
        "account_signal_action": signal_action,
        "observed_verified_buying_members": committee["observed_member_count"],
        "verified_contact_route_count": sum(role_rows.values()),
        "selected_contact_role": primary["decision_role"] if primary else None,
        "selected_contact_personally_identifiable": False,
        "verified_warm_introduction_available": chosen_intro is not None,
        "preferred_introduction_type": chosen_intro["kind"] if chosen_intro else None,
        "global_contact_history_checked": route.contact_history_complete,
        "company_cooldown_held": fatigue["blocked"],
        "missing_requirements": blockers,
        "inferred_buyer_identity_or_demand": False,
        "outbound_sent": False, "campaign_enrolled": False,
        "personal_data_exposed": False, "database_writes": False,
        "execution_authority": "NONE",
    }


def review_account_route_portfolio(
    packets: Iterable[
        tuple[TrustedAccountRoute, Iterable[TrustedCampaignSignal]]
    ], *, now: datetime,
) -> dict:
    """Privacy-minimising aggregate Sales Director play queue.

    Deliberately exposes no contact IDs, company names or recipient lists.
    The existing owner must retain account-level access controls and source
    receipt verification; this is not a replacement CRM or buyer graph.
    """
    packets = list(packets)
    if len(packets) > 500:
        raise CampaignIntelligenceHeld("ROUTE_PORTFOLIO_LIMIT_EXCEEDED")
    seen: set[tuple[str, str, str]] = set()
    plays: Counter[str] = Counter()
    intro_count = 0
    verified_routes = 0
    for route, signals in packets:
        if type(route) is not TrustedAccountRoute:
            raise CampaignIntelligenceHeld("TRUSTED_ROUTE_PROJECTION_REQUIRED")
        _context(route.context)
        identity = (
            route.context.tenant_ref,
            route.context.account_key,
            route.context.campaign_id,
        )
        if identity in seen:
            raise CampaignIntelligenceHeld("DUPLICATE_ACCOUNT_ROUTE_PORTFOLIO")
        seen.add(identity)
        result = review_account_buying_route(route, verified_signals=signals, now=now)
        plays[result["recommended_play"]] += 1
        if result["verified_warm_introduction_available"]:
            intro_count += 1
        verified_routes += result["verified_contact_route_count"]
    return {
        "schema_version": "empire.gtm.sales_director_route_portfolio.v1",
        "accounts_reviewed": len(seen),
        "commercial_plays": dict(sorted(plays.items())),
        "verified_contact_routes_reviewed": verified_routes,
        "verified_warm_introductions_reviewed": intro_count,
        "sent_messages": 0,
        "contact_information_exposed": False,
        "autonomous_sender_enabled": False,
        "execution_authority": "NONE",
    }

# Multi-wave learning stays within the original experiment decision owner.
# A wave is an owner-attested, canonical ledger/CRM projection, never user
# browser input. It can recommend testing, not change the actual assignment,
# tracking, offer, email channel or spend.
EXPERIMENT_ID = "tam-full-funnel-offer-angle-20261020"


@dataclass(frozen=True)
class TrustedCampaignLearningWave:
    wave_key: str
    tenant_ref: str
    market_scope: str
    experiment_id: str
    started_at: datetime
    outcome_window_closed_at: datetime
    evidence_issued_at: datetime
    arm_outcomes: tuple[TrustedArmOutcome, ...]
    source_receipts_verified: bool
    assignment_replay_verified: bool
    cross_wave_identity_dedup_verified: bool
    comparable_cohort_verified: bool


def _wilson_interval(positives: int, sample: int, z: float = 2.64) -> tuple[float, float]:
    """Conservative binomial interval, not a campaign-level causal estimate."""
    if type(positives) is not int or type(sample) is not int or not 0 <= positives <= sample:
        raise CampaignIntelligenceHeld("INVALID_CONFIDENCE_INTERVAL_COUNTS")
    if sample == 0:
        raise CampaignIntelligenceHeld("EMPTY_CONFIDENCE_INTERVAL_DENOMINATOR")
    # Reuse Empire's canonical Predictive Intelligence statistics helper.
    # 2.64 is deliberately more conservative than its default 95% interval.
    from empire_os.predictive_intelligence import _wilson_interval as existing_wilson
    low, high = existing_wilson(positives, sample, z=z)
    return (round(low, 7), round(high, 7))


def review_multiwave_commercial_learning(
    waves: Iterable[TrustedCampaignLearningWave], *, now: datetime,
    minimum_assigned_per_arm: int = 50,
    max_evidence_age_days: int = 14,
) -> dict:
    """Compare verified, non-overlapping, comparable campaign cohorts.

    Missing or incompatible receipts hold the *entire* pooled winner claim.
    Negative performance and unsubscribes are never washed out by averaging.
    Assignment integrity is source-owner-attested; this function cannot audit
    raw email or payment identities and never represents itself as doing so.
    """
    now = _aware(now)
    if type(max_evidence_age_days) is not int or not 1 <= max_evidence_age_days <= 90:
        raise CampaignIntelligenceHeld("INVALID_LEARNING_FRESHNESS_POLICY")
    if type(minimum_assigned_per_arm) is not int or not 20 <= minimum_assigned_per_arm <= 10000:
        raise CampaignIntelligenceHeld("INVALID_LEARNING_SAMPLE_POLICY")
    rows = list(waves)
    if len(rows) > 12:
        raise CampaignIntelligenceHeld("TOO_MANY_LEARNING_WAVES")
    if not rows:
        return {
            "schema_version": "empire.gtm.multiwave_learning.v1",
            "status": "NO_AUTHENTICATED_LEARNING_WAVES",
            "waves_reviewed": 0, "comparable_pool_ready": False,
            "proposed_offer": None, "next_learning_action": "AWAIT_VERIFIED_CAMPAIGN_OUTCOMES",
            "cohort_trend": None, "arm_statistics": None,
            "auto_reallocation": False, "execution_authority": "NONE",
        }
    first = rows[0]
    if type(first) is not TrustedCampaignLearningWave:
        raise CampaignIntelligenceHeld("INVALID_LEARNING_WAVE_SHAPE")
    market = first.market_scope
    tenant = first.tenant_ref
    if market not in _SCOPES or type(tenant) is not str or not _TENANT.fullmatch(tenant):
        raise CampaignIntelligenceHeld("LEARNING_MARKET_OR_TENANT_NOT_VERIFIED")
    seen_keys: set[str] = set()
    seen_time_spans: set[tuple[datetime, datetime]] = set()
    validated: list[tuple[datetime, datetime, TrustedCampaignLearningWave, dict]] = []
    holds: set[str] = set()
    for row in rows:
        if type(row) is not TrustedCampaignLearningWave or not _opaque(row.wave_key):
            raise CampaignIntelligenceHeld("INVALID_LEARNING_WAVE_ID")
        if row.wave_key in seen_keys:
            raise CampaignIntelligenceHeld("DUPLICATE_LEARNING_WAVE")
        seen_keys.add(row.wave_key)
        if (row.tenant_ref != tenant or row.market_scope != market
                or row.experiment_id != EXPERIMENT_ID):
            raise CampaignIntelligenceHeld("INCOMPARABLE_TENANT_MARKET_OR_EXPERIMENT")
        start = _aware(row.started_at)
        closed = _aware(row.outcome_window_closed_at)
        issued = _aware(row.evidence_issued_at)
        if start > closed or closed > issued or issued > now + timedelta(minutes=1):
            raise CampaignIntelligenceHeld("LEARNING_WAVE_CAUSAL_CLOCK_INVALID")
        if closed - start < timedelta(days=14):
            holds.add("OUTCOME_MATURATION_WINDOW_TOO_SHORT")
        if now - issued > timedelta(days=max_evidence_age_days):
            holds.add("OUTCOME_SOURCE_SNAPSHOT_STALE")
        if (start, closed) in seen_time_spans:
            raise CampaignIntelligenceHeld("REPEATED_WAVE_TIME_WINDOW")
        seen_time_spans.add((start, closed))
        for flag in (
            "source_receipts_verified", "assignment_replay_verified",
            "cross_wave_identity_dedup_verified", "comparable_cohort_verified",
        ):
            if type(getattr(row, flag)) is not bool:
                raise CampaignIntelligenceHeld("UNKNOWN_LEARNING_TRUST_GATE")
            if getattr(row, flag) is not True:
                holds.add(flag.upper() + "_MISSING")
        if type(row.arm_outcomes) is not tuple:
            raise CampaignIntelligenceHeld("LEARNING_ARM_ROWS_INVALID")
        evidence = evaluate_real_customer_experiment(
            row.arm_outcomes, minimum_assigned_per_arm=minimum_assigned_per_arm,
        )
        # The existing experiment definition fixes a 10% account holdout.
        # Comparing campaigns with different assignment regimes is unsafe.
        assigned = {arm.arm: arm.assigned_accounts for arm in row.arm_outcomes}
        total_assigned = sum(assigned.values())
        control_share = assigned["no_marketing_holdout"] / total_assigned
        if not 0.07 <= control_share <= 0.13:
            holds.add("HOLDOUT_RANDOMIZATION_SHARE_MISMATCH")
        if any(
            not 0.25 <= assigned[name] / total_assigned <= 0.35
            for name in EXPERIMENT_ARMS if name != "no_marketing_holdout"
        ):
            holds.add("TREATMENT_ARM_ALLOCATION_IMBALANCE")
        if evidence["data_quality_holds"]:
            holds.add("ARM_RECEIPT_OR_SAFETY_HOLD")
        if any(x["receipts_for_this_arm_accepted"] is not True
               for x in evidence["arm_reviews"]):
            holds.add("CLOSED_CANONICAL_OUTCOMES_NOT_VERIFIED")
        validated.append((start, closed, row, evidence))
    validated.sort(key=lambda record: record[0])
    if any(previous[1] >= following[0] for previous, following in
           zip(validated, validated[1:])):
        holds.add("OVERLAPPING_OR_CONTAMINATED_WAVE_WINDOWS")
    if len(validated) > 1:
        baseline_bounds = []
        for _, _, item, _ in validated:
            control = next(arm for arm in item.arm_outcomes
                           if arm.arm == "no_marketing_holdout")
            baseline_bounds.append(_wilson_interval(
                control.paying_customers, control.assigned_accounts
            ))
        if max(pair[0] for pair in baseline_bounds) > min(
            pair[1] for pair in baseline_bounds
        ):
            holds.add("CONTROL_BASELINE_SHIFT_REQUIRES_SOURCE_REVIEW")
    # Owner receipt verification is only sufficient for a valid *review*.
    # It does not establish full-period randomized causal comparability.
    if holds:
        return {
            "schema_version": "empire.gtm.multiwave_learning.v1",
            "status": "HOLD_MISSING_OR_INCOMPARABLE_CAMPAIGN_EVIDENCE",
            "waves_reviewed": len(validated), "comparable_pool_ready": False,
            "source_holds": sorted(holds), "proposed_offer": None,
            "next_learning_action": "REPAIR_EXISTING_EXPERIMENT_AND_COMMERCIAL_SOURCE_PROOF",
            "cohort_trend": None, "arm_statistics": None,
            "auto_reallocation": False, "execution_authority": "NONE",
        }

    totals = {
        arm: {"assigned": 0, "delivered": 0, "customers": 0,
              "complaints": 0, "optouts": 0, "gp": 0, "revenue": 0}
        for arm in EXPERIMENT_ARMS
    }
    all_finance = True
    single_wave_rates = []
    for _, _, row, _ in validated:
        by_arm = {arm.arm: arm for arm in row.arm_outcomes}
        by_control = by_arm["no_marketing_holdout"]
        single_wave_rates.append(
            round(by_control.paying_customers / by_control.assigned_accounts, 6)
        )
        for arm in row.arm_outcomes:
            t = totals[arm.arm]
            t["assigned"] += arm.assigned_accounts
            t["delivered"] += arm.delivered_accounts
            t["customers"] += arm.paying_customers
            t["complaints"] += arm.complaint_accounts
            t["optouts"] += arm.unsubscribe_accounts
            all_finance &= arm.financial_receipts_verified is True
            if arm.financial_receipts_verified:
                t["gp"] += arm.realized_gp_cents
                t["revenue"] += arm.recognized_revenue_cents

    control_count = totals["no_marketing_holdout"]
    control_interval = _wilson_interval(control_count["customers"], control_count["assigned"])
    reviewed = []
    for name in EXPERIMENT_ARMS:
        counts = totals[name]
        lb, ub = _wilson_interval(counts["customers"], counts["assigned"])
        delivered = counts["delivered"]
        complaint_rate = counts["complaints"] / delivered if delivered else 0.0
        optout_rate = counts["optouts"] / delivered if delivered else 0.0
        risk_hold = (name != "no_marketing_holdout"
                     and (complaint_rate > 0.01 or optout_rate > 0.05))
        reviewed.append({
            "arm": name,
            "assigned_accounts": counts["assigned"],
            "paying_customers": counts["customers"],
            "observed_customer_rate": round(counts["customers"] / counts["assigned"], 6),
            "conservative_rate_bounds": [lb, ub],
            "observed_gp_per_account_cents": (
                round(counts["gp"] / counts["assigned"], 2) if all_finance else None
            ),
            "safety_hold": risk_hold,
            # Interval non-overlap is a conservative screening heuristic
            # and does NOT prove causal lift or multiple-test significance.
            "customer_rate_bounds_above_holdout": (
                lb > control_interval[1] if name != "no_marketing_holdout" else False
            ),
        })
    safe = [row for row in reviewed
            if row["arm"] != "no_marketing_holdout" and not row["safety_hold"]]
    candidate = None
    action = "CONTINUE_CONTROLLED_EXPLORATION_AND_MEASURE_CUSTOMERS"
    if not safe:
        action = "REVIEW_OUTREACH_COMPLAINTS_AND_UNSUBSCRIBES"
    elif len(validated) < 2:
        action = "COLLECT_SECOND_COMPARABLE_MARKET_WAVE"
    else:
        # Require independent waves to show each arm above the contemporaneous
        # holdout; a pooled rate alone can hide market and time confounding.
        eligible = []
        for result in safe:
            arm = result["arm"]
            across_waves = all(
                {r.arm: r for r in wave.arm_outcomes}[arm].paying_customers
                / {r.arm: r for r in wave.arm_outcomes}[arm].assigned_accounts
                > {r.arm: r for r in wave.arm_outcomes}["no_marketing_holdout"].paying_customers
                / {r.arm: r for r in wave.arm_outcomes}["no_marketing_holdout"].assigned_accounts
                for _, _, wave, _ in validated
            )
            if (across_waves
                and result["customer_rate_bounds_above_holdout"]
                and result["paying_customers"] > 0
                and (not all_finance
                     or result["observed_gp_per_account_cents"] is not None
                     and result["observed_gp_per_account_cents"] > 0)):
                eligible.append(result)
        if eligible:
            metric = ("observed_gp_per_account_cents"
                      if all_finance else "observed_customer_rate")
            selected = max(eligible, key=lambda x: (x[metric], x["arm"]))
            candidate = selected["arm"]
            action = "HUMAN_REVIEW_REPLICATED_OFFER_RESULT_WITH_EXISTING_CAUSAL_SPECIALIST"
        elif all_finance and all(
            row["observed_gp_per_account_cents"] is not None
            and row["observed_gp_per_account_cents"] <= 0
            for row in safe
        ):
            action = "REVIEW_REALIZED_MARGIN_BEFORE_ANY_CAMPAIGN_EXPANSION"
    return {
        "schema_version": "empire.gtm.multiwave_learning.v1",
        "status": "REPLICATED_CANDIDATE_FOR_HUMAN_CAUSAL_REVIEW" if candidate else
                  "CONTINUE_LEARNING_NO_COMMERCIAL_WINNER",
        "waves_reviewed": len(validated), "comparable_pool_ready": True,
        "source_holds": [], "proposed_offer": candidate,
        "next_learning_action": action,
        "cohort_trend": {
            "observed_holdout_customer_rates_by_wave": single_wave_rates,
            "marketing_outcome_receipts_all_financially_verified": all_finance,
        },
        "arm_statistics": reviewed,
        "causal_lift_or_significance_claimed": False,
        "auto_reallocation": False, "budget_mutation": False, "campaign_activated": False,
        "execution_authority": "NONE",
    }

# Adaptive campaign journey is a read-only ADAPTER of the pre-existing Revenue
# CRM journey and channel-evidence contracts. The CRM and Sales Director retain
# exclusive authority to record identity, permission, conversations and sends.
@dataclass(frozen=True)
class TrustedJourneyProjection:
    account_route: TrustedAccountRoute
    crm_row: Mapping[str, object]
    canonical_account_to_crm_binding_verified: bool
    crm_snapshot_observed_at: datetime
    channel_receipts: tuple[object, ...]


_CRM_JOURNEY_FIELDS = frozenset({
    "tenant_id", "prospect_id", "prospect_status", "niche",
    "conversation_id", "conversation_state", "conversation_updated_at",
    "closer_case_id", "closer_state", "closer_updated_at",
    "fulfilment_order_id", "fulfilment_state", "fulfilment_updated_at",
})
_CHANNEL_PRIORITY = ("email", "sms", "web_push")
_JOURNEY_REVIEW_TYPES = (
    "STOP_CONTACT", "HOLD_CANONICAL_SOURCE", "EXISTING_CUSTOMER_REVIEW",
    "FULFILMENT_OWNER_REVIEW", "PAYMENT_STATUS_OWNER_REVIEW",
    "PROPOSAL_AND_TERMS_REVIEW", "SAME_DAY_BUYER_CONVERSATION_REVIEW",
    "WARM_INTRO_OWNER_REVIEW", "OFFER_EXPERIMENT_OWNER_REVIEW",
    "HOLD_CHANNEL_EVIDENCE", "HOLD_INBOUND_RESPONSE_BASIS",
    "INTERNAL_ACCOUNT_RESEARCH",
)


def review_adaptive_buyer_journey(
    projection: TrustedJourneyProjection, *,
    verified_signals: Iterable[TrustedCampaignSignal],
    now: datetime,
    learning_waves: Iterable[TrustedCampaignLearningWave] | None = None,
    buyer_value_case: TrustedBuyerValueCase | None = None,
) -> dict:
    """Reconcile real CRM stage, channel proof, account route and offer learning.

    No CRM name/person/contact ID is returned. Verified stage is not consent.
    Verified opt-in is not legal permission to send or an execution grant.
    A client-supplied boolean cannot replace owner-authenticated projections.
    """
    from empire_os.revenue_crm_journeys import preview_crm_journey
    from empire_os.revenue_crm_channel_evidence import (
        CHANNELS, TrustedChannelEvidence, canonical_uuid,
        review_channel_evidence,
    )
    if type(projection) is not TrustedJourneyProjection:
        raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_PROJECTION_REQUIRED")
    now = _aware(now)
    route = projection.account_route
    if type(route) is not TrustedAccountRoute:
        raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_ACCOUNT_ROUTE_REQUIRED")
    _context(route.context)
    if type(projection.canonical_account_to_crm_binding_verified) is not bool:
        raise CampaignIntelligenceHeld("JOURNEY_IDENTITY_BINDING_GATE_INVALID")
    if not isinstance(projection.crm_row, Mapping):
        raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_CRM_RECORD_REQUIRED")
    crm = {k: projection.crm_row[k] for k in _CRM_JOURNEY_FIELDS
           if k in projection.crm_row}
    try:
        tenant = canonical_uuid(crm.get("tenant_id"))
        prospect = canonical_uuid(crm.get("prospect_id"))
    except ValueError as exc:
        raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_CRM_ID_INVALID") from exc
    # CRM identifiers are real UUIDs; marketing experiments use different
    # opaque keys. Owner-supplied correspondence MUST be independently attested.
    if type(projection.channel_receipts) is not tuple:
        raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_CHANNEL_SHAPE_INVALID")
    if len(projection.channel_receipts) > len(CHANNELS):
        raise CampaignIntelligenceHeld("TOO_MANY_JOURNEY_CHANNEL_RECEIPTS")
    if projection.canonical_account_to_crm_binding_verified is not True:
        return {
            "schema_version": "empire.gtm.adaptive_buyer_journey_review.v1",
            "recommended_play": "HOLD_CANONICAL_SOURCE",
            "reason": "ACCOUNT_TO_CRM_IDENTITY_BINDING_NOT_PROVEN",
            "crm_journey_stage": None, "preferred_human_channel_review": None,
            "offer_learning_candidate_for_review": None,
            "channel_review_states": {},
            "timing": "NO_EXTERNAL_CONTACT",
            "personal_identifiers_disclosed": False,
            "send_authorized": False, "auto_sequence_enabled": False,
            "auto_paid_retargeting": False, "crm_mutation": False,
            "execution_authority": "NONE",
        }
    observed = _aware(projection.crm_snapshot_observed_at)
    if observed > now or now - observed > timedelta(hours=24):
        raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_CRM_SNAPSHOT_STALE")
    crm["tenant_id"] = tenant
    crm["prospect_id"] = prospect
    preview = preview_crm_journey(crm, now=now)
    # Preserve the same source-attested receipts for both the journey
    # and value-first stages, even if the caller passes a generator.
    source_signals = tuple(verified_signals)
    route_review = review_account_buying_route(
        route, verified_signals=source_signals, now=now,
    )
    channel_reviews = {}
    seen_channels = set()
    for receipt in projection.channel_receipts:
        if type(receipt) is not TrustedChannelEvidence:
            raise CampaignIntelligenceHeld("UNTRUSTED_JOURNEY_CHANNEL_RECEIPT")
        if receipt.channel in seen_channels:
            raise CampaignIntelligenceHeld("DUPLICATE_JOURNEY_CHANNEL_RECEIPT")
        seen_channels.add(receipt.channel)
        try:
            review = review_channel_evidence(
                {"tenant_id": tenant, "prospect_id": prospect,
                 "prospect_status": crm.get("prospect_status")},
                channel=receipt.channel, evidence=receipt, now=now,
            )
        except ValueError as exc:
            raise CampaignIntelligenceHeld("JOURNEY_CHANNEL_IDENTITY_OR_EVIDENCE_INVALID") from exc
        channel_reviews[receipt.channel] = review["review_status"]
    for channel in CHANNELS:
        if channel not in channel_reviews:
            channel_reviews[channel] = "HOLD_MISSING_EVIDENCE"
    available = [
        channel for channel in _CHANNEL_PRIORITY
        if channel_reviews[channel] == "REVIEW_ONLY_EVIDENCE_PRESENT"
    ]
    preferred = available[0] if available else None
    segment = preview["segment"]
    account_play = route_review["recommended_play"]
    if segment == "contact_hold" or account_play == "STOP_AND_SUPPRESS":
        play, timing = "STOP_CONTACT", "NO_EXTERNAL_CONTACT"
    elif account_play in ("HOLD_CANONICAL_ACCOUNT_IDENTITY",):
        play, timing = "HOLD_CANONICAL_SOURCE", "NO_EXTERNAL_CONTACT"
    elif account_play == "EXISTING_CUSTOMER_HUMAN_REVIEW":
        play, timing = "EXISTING_CUSTOMER_REVIEW", "OWNER_QUEUE"
    elif segment == "fulfilment_review":
        play, timing = "FULFILMENT_OWNER_REVIEW", "OWNER_QUEUE"
    elif segment == "awaiting_payment_review":
        play, timing = "PAYMENT_STATUS_OWNER_REVIEW", "OWNER_QUEUE"
    elif segment == "proposal_review":
        play, timing = "PROPOSAL_AND_TERMS_REVIEW", "OWNER_QUEUE"
    elif account_play == "COMMERCIAL_TERMS_HUMAN_REVIEW":
        play, timing = "PROPOSAL_AND_TERMS_REVIEW", "OWNER_QUEUE"
    elif account_play == "HOLD_INBOUND_REPLY_BASIS":
        play, timing = "HOLD_INBOUND_RESPONSE_BASIS", "NO_EXTERNAL_CONTACT"
    elif account_play == "SAME_BUSINESS_DAY_EXISTING_INBOUND_REVIEW":
        play, timing = "SAME_DAY_BUYER_CONVERSATION_REVIEW", "SAME_BUSINESS_DAY"
    elif segment == "engaged_conversation_review":
        if route.context.inbound_response_basis_verified is True:
            play, timing = "SAME_DAY_BUYER_CONVERSATION_REVIEW", "SAME_BUSINESS_DAY"
        else:
            play, timing = "HOLD_INBOUND_RESPONSE_BASIS", "NO_EXTERNAL_CONTACT"
    elif account_play == "PREPARE_VERIFIED_WARM_INTRO_FOR_OWNER_REVIEW":
        # A verified human-introduction path is NOT marketing channel
        # opt-in, and intro text still requires existing owner approval.
        play, timing = "WARM_INTRO_OWNER_REVIEW", "OWNER_QUEUE"
    elif account_play == "PREPARE_ONE_CONTACT_OFFER_FOR_OWNER_REVIEW":
        if preferred is not None:
            play, timing = "OFFER_EXPERIMENT_OWNER_REVIEW", "OWNER_QUEUE"
        else:
            play, timing = "HOLD_CHANNEL_EVIDENCE", "NO_EXTERNAL_CONTACT"
    else:
        play, timing = "INTERNAL_ACCOUNT_RESEARCH", "NO_EXTERNAL_CONTACT"
    learning_result = (
        review_multiwave_commercial_learning(learning_waves, now=now)
        if learning_waves is not None else None
    )
    candidate = (
        learning_result["proposed_offer"]
        if learning_result is not None
        and learning_result["status"] == "REPLICATED_CANDIDATE_FOR_HUMAN_CAUSAL_REVIEW"
        else None
    )
    # Do not show an apparent preferred outbound channel beside STOP, HOLD,
    # payment, fulfilment or existing-customer stages. The detailed evidence
    # remains inspectable for owners, but no channel is recommended there.
    offer_review_channel = (
        preferred if play == "OFFER_EXPERIMENT_OWNER_REVIEW" else None
    )
    if play != "OFFER_EXPERIMENT_OWNER_REVIEW":
        candidate = None
    value_preview = None
    if buyer_value_case is not None:
        if (type(buyer_value_case) is not TrustedBuyerValueCase
                or buyer_value_case.context != route.context):
            raise CampaignIntelligenceHeld("CROSS_ACCOUNT_ADAPTIVE_VALUE_CASE")
        reviewed_value = review_buyer_value_first_offer(
            buyer_value_case, verified_signals=source_signals, now=now,
        )
        # No prospecting propositions appear beside stop/payment/fulfilment
        # reviews. Existing buyer conversations may use a proof-backed brief;
        # only a buyer's genuine direct request earns a sales CTA review.
        show_value = play in (
            "OFFER_EXPERIMENT_OWNER_REVIEW",
            "SAME_DAY_BUYER_CONVERSATION_REVIEW",
        )
        value_preview = {
            "value_first_review_play": reviewed_value["review_play"],
            "value_deliverable_for_owner": (
                reviewed_value["value_first_deliverable"] if show_value else None
            ),
            "buyer_friction_resolution_for_owner": (
                reviewed_value["buyer_risk_resolution"] if show_value else None
            ),
            "commercial_cta_review_eligible": (
                play == "SAME_DAY_BUYER_CONVERSATION_REVIEW"
                and reviewed_value["commercial_cta_review_eligible"]
            ),
            "send_or_upsell_authorized": False,
        }
    return {
        "schema_version": "empire.gtm.adaptive_buyer_journey_review.v1",
        "recommended_play": play,
        "reason": "CRM_STAGE_CHANNEL_AND_ACCOUNT_EVIDENCE_RECONCILED",
        "crm_journey_stage": segment,
        "crm_stale_conversation_review": preview["engaged_conversation_stale_candidate"],
        "account_signal_action": route_review["account_signal_action"],
        "preferred_human_channel_review": offer_review_channel,
        "channel_review_states": dict(sorted(channel_reviews.items())),
        "channel_evidence_does_not_grant_send_authority": True,
        "editorial_interest_hypothesis_not_subscription":
            preview["editorial_interest_hypothesis_not_subscription"],
        "offer_learning_candidate_for_review": candidate,
        "buyer_value_first_review": value_preview,
        "offer_auto_promotion": False,
        "timing": timing,
        "personal_identifiers_disclosed": False,
        "send_authorized": False,
        "auto_sequence_enabled": False,
        "auto_paid_retargeting": False,
        "crm_mutation": False,
        "execution_authority": "NONE",
    }


def review_adaptive_buyer_journey_portfolio(
    packets: Iterable[
        tuple[TrustedJourneyProjection, Iterable[TrustedCampaignSignal]]
    ], *, now: datetime,
    learning_waves: Iterable[TrustedCampaignLearningWave] | None = None,
) -> dict:
    """Privacy-safe rollup without creating another CRM journey scheduler."""
    items = list(packets)
    if len(items) > 500:
        raise CampaignIntelligenceHeld("ADAPTIVE_JOURNEY_BATCH_TOO_LARGE")
    plays: Counter[str] = Counter()
    stages: Counter[str] = Counter()
    reviewed: set[tuple[str, str, str]] = set()
    crm_seen: set[tuple[str, str]] = set()
    from empire_os.revenue_crm_channel_evidence import canonical_uuid
    # Materialise once: a generator cannot be replayed for every account.
    learning = tuple(learning_waves) if learning_waves is not None else None
    for projection, signals in items:
        if type(projection) is not TrustedJourneyProjection:
            raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_PROJECTION_REQUIRED")
        route = projection.account_route
        _context(route.context)
        key = (route.context.tenant_ref, route.context.account_key,
               route.context.campaign_id)
        if key in reviewed:
            raise CampaignIntelligenceHeld("DUPLICATE_ADAPTIVE_ACCOUNT_JOURNEY")
        try:
            crm_key = (
                canonical_uuid(projection.crm_row.get("tenant_id")),
                canonical_uuid(projection.crm_row.get("prospect_id")),
            )
        except (ValueError, AttributeError) as exc:
            raise CampaignIntelligenceHeld("INVALID_ADAPTIVE_CRM_PORTFOLIO_KEY") from exc
        if crm_key in crm_seen:
            raise CampaignIntelligenceHeld("DUPLICATE_CANONICAL_CRM_PROSPECT_IN_PORTFOLIO")
        crm_seen.add(crm_key)
        reviewed.add(key)
        result = review_adaptive_buyer_journey(
            projection, verified_signals=signals, now=now,
            learning_waves=learning,
        )
        plays[result["recommended_play"]] += 1
        if result["crm_journey_stage"] is not None:
            stages[result["crm_journey_stage"]] += 1
    return {
        "schema_version": "empire.gtm.adaptive_buyer_journey_portfolio.v1",
        "accounts_reviewed": len(reviewed),
        "recommended_human_play_counts": dict(sorted(plays.items())),
        "crm_lifecycle_stage_counts": dict(sorted(stages.items())),
        "contact_identity_records_exposed": 0,
        "messages_scheduled": 0, "crm_writes": 0,
        "automatic_channel_activation": False,
        "execution_authority": "NONE",
    }


def review_authenticated_crm_campaign_handoff(
    authenticated_read: object, *,
    account_projection_owner: object,
    signal_owner: object,
    now: datetime,
    limit: int = 100,
    value_case_owner: object | None = None,
) -> dict:
    """Use EXISTING tenant-authenticated, read-only Revenue CRM repository.

    Caller must be the authenticated Revenue CRM route/service owner. It must
    provide source-attested canonical account joins and event receipts.
    Missing joins stay held, not coerced into contacts or subscribers. This
    function does not call the unauthenticated public CRM API, load secrets,
    instantiate a tenant repository, or add a new login/role/credential.
    """
    from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    from empire_os.revenue_crm_channel_evidence import canonical_uuid

    now = _aware(now)
    if (type(authenticated_read) is not AuthenticatedRevenueCrmRead
            or not isinstance(authenticated_read.repository, PostgresRevenueCrmRepository)
            or not callable(account_projection_owner)
            or not callable(signal_owner)
            or (value_case_owner is not None and not callable(value_case_owner))
            or type(limit) is not int or not 1 <= limit <= 500):
        raise CampaignIntelligenceHeld("AUTHENTICATED_CRM_OWNER_BOUNDARY_REQUIRED")
    repository = authenticated_read.repository
    try:
        tenant = canonical_uuid(authenticated_read.tenant_id)
        if tenant != repository.tenant_id:
            raise ValueError("authenticated tenant and dedicated repository differ")
    except (ValueError, TypeError, AttributeError):
        raise CampaignIntelligenceHeld("AUTHENTICATED_CRM_TENANT_MISMATCH") from None
    try:
        original = repository.prospects(limit=limit)
    except Exception:
        # Never leak a DSN, company, prospect ID or private database diagnostic.
        raise CampaignIntelligenceHeld("AUTHENTICATED_CRM_READ_UNAVAILABLE") from None
    if (not isinstance(original, (list, tuple))
            or len(original) > limit):
        raise CampaignIntelligenceHeld("BOUNDED_CRM_SOURCE_ROWS_REQUIRED")
    seen_crm = set()
    payloads = []
    value_review_counts: Counter[str] = Counter()
    private_experience_candidates = 0
    value_proof_held = 0
    rows_with_no_proven_canonical_join = 0
    for item in original:
        if not isinstance(item, Mapping):
            raise CampaignIntelligenceHeld("CANONICAL_CRM_ROW_SHAPE_INVALID")
        try:
            own_tenant = canonical_uuid(item.get("tenant_id"))
            prospect = canonical_uuid(item.get("prospect_id"))
        except (ValueError, TypeError, AttributeError):
            raise CampaignIntelligenceHeld("CANONICAL_CRM_ROW_IDENTITY_INVALID") from None
        if own_tenant != tenant or prospect in seen_crm:
            raise CampaignIntelligenceHeld("DUPLICATE_OR_CROSS_TENANT_CRM_SOURCE")
        seen_crm.add(prospect)
        try:
            joined = account_projection_owner(item)
        except Exception:
            raise CampaignIntelligenceHeld("ACCOUNT_TO_CRM_OWNER_JOIN_UNAVAILABLE") from None
        if joined is None:
            rows_with_no_proven_canonical_join += 1
            continue
        if (type(joined) is not TrustedJourneyProjection
                or joined.canonical_account_to_crm_binding_verified is not True
                or not isinstance(joined.crm_row, Mapping)
                or any(
                    joined.crm_row.get(name) != item.get(name)
                    for name in _CRM_JOURNEY_FIELDS
                    if name in item
                )):
            raise CampaignIntelligenceHeld("FORGED_OR_UNBOUND_CRM_JOURNEY_PROJECTION")
        try:
            joined_tenant = canonical_uuid(joined.crm_row.get("tenant_id"))
            joined_prospect = canonical_uuid(joined.crm_row.get("prospect_id"))
        except (ValueError, TypeError, AttributeError):
            raise CampaignIntelligenceHeld("FORGED_OR_UNBOUND_CRM_JOURNEY_PROJECTION") from None
        if joined_tenant != tenant or joined_prospect != prospect:
            raise CampaignIntelligenceHeld("FORGED_OR_UNBOUND_CRM_JOURNEY_PROJECTION")
        try:
            trusted_signals = signal_owner(joined)
            if type(trusted_signals) not in (list, tuple):
                raise ValueError("typed source-bound signals required")
        except Exception:
            raise CampaignIntelligenceHeld("CANONICAL_ACCOUNT_SIGNAL_OWNER_UNAVAILABLE") from None
        payloads.append((joined, trusted_signals))
        if value_case_owner is not None:
            try:
                value_case = value_case_owner(joined)
            except Exception:
                raise CampaignIntelligenceHeld("CANONICAL_VALUE_CASE_OWNER_UNAVAILABLE") from None
            if value_case is None:
                value_proof_held += 1
            else:
                if (type(value_case) is not TrustedBuyerValueCase
                        or value_case.context != joined.account_route.context):
                    raise CampaignIntelligenceHeld("CROSS_ACCOUNT_CRM_VALUE_CASE")
                result = review_buyer_value_first_offer(
                    value_case, verified_signals=trusted_signals, now=now,
                )
                value_review_counts[result["review_play"]] += 1
                if result["offer_candidate"] is not None:
                    private_experience_candidates += 1
    reviewed = review_adaptive_buyer_journey_portfolio(payloads, now=now)
    return {
        "schema_version": "empire.gtm.tenant_crm_campaign_owner_handoff.v1",
        "mode": "OBSERVE",
        "authenticated_tenant_source_verified": True,
        "canonical_crm_rows_read": len(original),
        "canonical_account_join_unavailable": rows_with_no_proven_canonical_join,
        "bound_account_journeys_reviewed": reviewed["accounts_reviewed"],
        "human_next_play_counts": reviewed["recommended_human_play_counts"],
        "buyer_value_first_review_counts": (
            dict(sorted(value_review_counts.items()))
            if value_case_owner is not None else None
        ),
        "buyer_value_case_unverified_count": (
            value_proof_held if value_case_owner is not None else None
        ),
        "proof_first_private_page_candidate_count": (
            private_experience_candidates
            if value_case_owner is not None else None
        ),
        "read_result_may_be_partial": len(original) == limit,
        "canonical_crm_contacts_returned": 0,
        "marketing_subscription_inferred": False,
        "crm_mutation": False,
        "sender_enabled": False,
        "execution_authority": "NONE",
    }

# Value-first commercial offer selection extends this existing campaign
# intelligence owner, not the central product catalog or Sales Director.
_VALUE_PROBLEMS = {
    "supply_territory_fit": (
        "buyer_inventory_fit_offer", "canonical_inventory",
        "verified_supply_acceptance_fit",
        "Prepare a bounded inventory/territory fit-check with the buyer's acceptance criteria.",
        "Check buyer territory and lead acceptance criteria",
        "Show a verified match or say explicitly there is no matching inventory.",
    ),
    "missed_demand_followup": (
        "revenue_leak_signal_offer", "canonical_first_party_analytics",
        "verified_conversion_bottleneck",
        "Prepare a measured demand-to-response gap brief with limitations.",
        "Review which measured response handoff fails",
        "Propose one controlled response-process improvement for review.",
    ),
    "market_expansion_decision": (
        "verified_market_opportunity_brief", "verified_public_market_source",
        "verified_territory_market_signal",
        "Prepare a one-page market evidence brief, distinguishing research from demand.",
        "Review which territories match the buyer's supplied criteria",
        "Compare verified observations and unknowns without guaranteeing returns.",
    ),
}
_FRICTION_RESOLUTION = {
    "quality_uncertainty": "Present observed acceptance rules and rejection handling; no guaranteed lead quality.",
    "proof_uncertainty": "Show source dates, evidence gaps and an independently checkable sample.",
    "terms_uncertainty": "Explain scope and acceptance conditions; use only approved written commercial terms.",
    "delivery_uncertainty": "Show verified fulfilment capacity before suggesting commitments.",
    "integration_effort": "Provide a bounded implementation outline; do not assume integration access.",
    "budget_uncertainty": "Show product scope before discussing prices; never invent ROI, savings or guarantees.",
}
_DIRECT_BUYER_REQUEST = frozenset({
    "optin_enquiry", "verified_social_inbound_enquiry", "demo_request",
    "direct_buyer_question", "pricing_request", "meeting_booked",
})


@dataclass(frozen=True)
class TrustedBuyerValueProblem:
    tenant_ref: str
    account_key: str
    market_scope: str
    problem_code: str
    observed_at: datetime
    buyer_directly_stated_problem: bool
    canonical_crm_evidence_verified: bool
    friction_code: str | None = None
    friction_receipt_verified: bool = False


@dataclass(frozen=True)
class TrustedOfferCapability:
    tenant_ref: str
    market_scope: str
    offer_arm: str
    capability_source: str
    proof_kind: str
    proof_key: str
    verified_at: datetime
    source_receipt_verified: bool
    currently_deliverable: bool
    verified_sufficient_market_fit: bool
    paid_catalog_product: Mapping | None = None


@dataclass(frozen=True)
class TrustedBuyerValueCase:
    context: AccountIntelligenceContext
    problem: TrustedBuyerValueProblem | None
    capabilities: tuple[TrustedOfferCapability, ...]


def review_buyer_value_first_offer(
    case: TrustedBuyerValueCase, *,
    verified_signals: Iterable[TrustedCampaignSignal],
    now: datetime,
) -> dict:
    """Choose source-grounded buyer value before any commercial CTA.

    Genuine CRM-stated need is not created from public-company research.
    This API returns only a safe internal brief and experiment-selection
    hypothesis. It cannot send messages, quote costs or sign binding terms.
    """
    from empire_os.commercial_offer_book import product_ready
    if type(case) is not TrustedBuyerValueCase:
        raise CampaignIntelligenceHeld("TRUSTED_VALUE_CASE_REQUIRED")
    _context(case.context)
    now = _aware(now)
    ctx = case.context
    signals = tuple(verified_signals)
    intent = review_account_intelligence(ctx, signals, now=now)
    if type(case.capabilities) is not tuple or len(case.capabilities) > 12:
        raise CampaignIntelligenceHeld("BOUNDED_VALUE_CAPABILITIES_REQUIRED")
    problem = case.problem
    active_problem = False
    problem_code = None
    friction = None
    if problem is not None:
        if type(problem) is not TrustedBuyerValueProblem:
            raise CampaignIntelligenceHeld("TRUSTED_BUYER_PROBLEM_REQUIRED")
        if (problem.tenant_ref != ctx.tenant_ref
                or problem.account_key != ctx.account_key
                or problem.market_scope != ctx.market_scope
                or problem.problem_code not in _VALUE_PROBLEMS
                or problem.friction_code not in (None, *_FRICTION_RESOLUTION)):
            raise CampaignIntelligenceHeld("CROSS_ACCOUNT_OR_UNSUPPORTED_BUYER_PROBLEM")
        observed = _aware(problem.observed_at)
        if observed > now + timedelta(minutes=1):
            raise CampaignIntelligenceHeld("FUTURE_BUYER_PROBLEM_EVIDENCE")
        if (type(problem.buyer_directly_stated_problem) is not bool
                or type(problem.canonical_crm_evidence_verified) is not bool
                or type(problem.friction_receipt_verified) is not bool):
            raise CampaignIntelligenceHeld("UNVERIFIED_BUYER_PROBLEM_SOURCE")
        active_problem = (
            problem.buyer_directly_stated_problem
            and problem.canonical_crm_evidence_verified
            and now - observed <= timedelta(days=45)
        )
        if active_problem:
            problem_code = problem.problem_code
            if problem.friction_code is not None and problem.friction_receipt_verified:
                friction = problem.friction_code
    statuses: dict[str, str] = {}
    seen: set[str] = set()
    for capability in case.capabilities:
        if type(capability) is not TrustedOfferCapability:
            raise CampaignIntelligenceHeld("TRUSTED_OFFER_CAPABILITY_REQUIRED")
        if capability.offer_arm in seen:
            raise CampaignIntelligenceHeld("DUPLICATE_CANONICAL_OFFER_CAPABILITY")
        seen.add(capability.offer_arm)
        if capability.offer_arm not in {
            value[0] for value in _VALUE_PROBLEMS.values()
        }:
            raise CampaignIntelligenceHeld("UNKNOWN_OFFER_ARM")
        if (capability.tenant_ref != ctx.tenant_ref
                or capability.market_scope != ctx.market_scope):
            raise CampaignIntelligenceHeld("CROSS_TENANT_OFFER_PROOF")
        expected = next(
            value for value in _VALUE_PROBLEMS.values()
            if value[0] == capability.offer_arm
        )
        if (capability.capability_source != expected[1]
                or capability.proof_kind != expected[2]
                or not _opaque(capability.proof_key)):
            raise CampaignIntelligenceHeld("OFFER_PROOF_OR_PROVENANCE_INVALID")
        when = _aware(capability.verified_at)
        if when > now + timedelta(minutes=1):
            raise CampaignIntelligenceHeld("OFFER_PROOF_FROM_FUTURE")
        for flag in ("source_receipt_verified", "currently_deliverable",
                     "verified_sufficient_market_fit"):
            if type(getattr(capability, flag)) is not bool:
                raise CampaignIntelligenceHeld("OFFER_PROOF_TRUST_GATE_UNKNOWN")
        if capability.paid_catalog_product is not None and not isinstance(
            capability.paid_catalog_product, Mapping
        ):
            raise CampaignIntelligenceHeld("OFFER_CATALOG_PRODUCT_INVALID")
        max_age_days = 7 if capability.offer_arm == "buyer_inventory_fit_offer" else 30
        if now - when > timedelta(days=max_age_days):
            status = "HOLD_STALE_PROOF"
        elif not capability.source_receipt_verified:
            status = "HOLD_SOURCE_UNVERIFIED"
        elif not capability.currently_deliverable:
            status = "HOLD_UNAVAILABLE_DELIVERY"
        elif not capability.verified_sufficient_market_fit:
            status = "HOLD_UNVERIFIED_MARKET_FIT"
        elif (capability.paid_catalog_product is not None
              and not product_ready(capability.paid_catalog_product)):
            status = "HOLD_UNVERIFIED_PAID_PRODUCT"
        else:
            status = "VERIFIED_VALUE_PREVIEW_AVAILABLE"
        statuses[capability.offer_arm] = status
    selected = None
    if active_problem and ctx.canonical_account_verified and ctx.suppression_clear:
        matching = _VALUE_PROBLEMS[problem_code][0]
        if statuses.get(matching) == "VERIFIED_VALUE_PREVIEW_AVAILABLE":
            selected = matching
    else:
        matching = None
    stop = intent["action"] == "STOP_AND_SUPPRESS"
    direct_kinds = {
        signal.kind for signal in signals
        if signal.kind in _DIRECT_BUYER_REQUEST
        and now - _aware(signal.observed_at) <= timedelta(days=45)
    }
    qualified_cta = (
        bool(direct_kinds)
        and intent["action"] == "SAME_BUSINESS_DAY_SALES_REVIEW"
        and active_problem and selected is not None
    )
    if stop:
        play = "STOP_CONTACT_AND_SUPPRESS"
    elif not ctx.canonical_account_verified:
        play = "HOLD_ACCOUNT_IDENTITY"
    elif not active_problem:
        play = "RESEARCH_BUYER_NEED_BEFORE_PERSONALIZATION"
    elif selected is None:
        play = "VERIFY_DELIVERABLE_BUYER_VALUE_BEFORE_OFFER"
    elif qualified_cta:
        play = "SAME_DAY_RESPOND_WITH_VALUE_THEN_REVIEW_CTA"
    else:
        play = "PREPARE_PROOF_FIRST_VALUE_BRIEF_NO_SALES_CTA"
    supported = _VALUE_PROBLEMS[problem_code] if selected is not None else None
    # Reuse the existing GTM demo specialist rather than creating a second
    # video/content system. A demo plan is NOT a rendered video or an
    # offer commitment, even when proof source receipts are current.
    demo_outline = None
    if selected is not None and supported is not None and not stop:
        from empire_os.gtm_offer_strategy import (
            NicheOfferContext, build_demo_asset_plan,
        )
        capability = next(x for x in case.capabilities if x.offer_arm == selected)
        niche = ctx.market_scope.split(":")[1]
        demo = build_demo_asset_plan(
            context=NicheOfferContext(
                niche=niche, metro=None, pe_backed=None,
                high_cash_flow_evidence=None, founder_network_fit=None,
                opportunity_evidence_refs=(),
            ),
            capability_evidence_refs=(capability.proof_key,),
        )
        demo_outline = {
            "format": demo["format"],
            "lead_magnet": demo["lead_magnet"],
            "proof_surfaces_for_owner_to_verify": demo["proof_surfaces"],
            "target_duration_seconds": demo["target_duration_seconds"],
            "asset_created_or_published": False,
            "public_case_study_or_roi_claim": False,
        }
    return {
        "schema_version": "empire.gtm.buyer_value_first_offer.v1",
        "review_play": play,
        "buyer_problem_proven_by_first_party": active_problem,
        "buyer_problem_type": problem_code,
        "offer_candidate": selected if not stop else None,
        "offer_proof_statuses": dict(sorted(statuses.items())),
        "value_first_deliverable": (
            supported[3] if supported and not stop else None
        ),
        "proof_based_demo_outline": demo_outline,
        "buyer_risk_resolution": (
            _FRICTION_RESOLUTION[friction] if friction and not stop else None
        ),
        "buyer_friction_confirmed": friction,
        "recommended_next_experiment": (
            supported[4] if supported and not stop else None
        ),
        "owner_reviewed_next_step": (
            supported[5] if supported and not stop else None
        ),
        "commercial_cta_review_eligible": qualified_cta and not stop,
        "cta_requires_explicit_buyer_request": True,
        "paid_price_quoted_cents": None,
        "roi_or_results_guaranteed": False,
        "customer_identity_or_proof_keys_exposed": False,
        "auto_send": False, "auto_follow_up": False,
        "campaign_auto_enrolled": False,
        "execution_authority": "NONE",
    }


def review_buyer_value_first_portfolio(
    cases: Iterable[
        tuple[TrustedBuyerValueCase, Iterable[TrustedCampaignSignal]]
    ], *, now: datetime,
) -> dict:
    """Review canonical accounts once, emit only action/proof readiness totals."""
    values = list(cases)
    if len(values) > 500:
        raise CampaignIntelligenceHeld("VALUE_PORTFOLIO_LIMIT_EXCEEDED")
    seen = set()
    statuses: Counter[str] = Counter()
    chosen: Counter[str] = Counter()
    experience_candidates = 0
    for case, signals in values:
        if type(case) is not TrustedBuyerValueCase:
            raise CampaignIntelligenceHeld("TRUSTED_VALUE_CASE_REQUIRED")
        _context(case.context)
        identity = (case.context.tenant_ref, case.context.account_key,
                    case.context.campaign_id)
        if identity in seen:
            raise CampaignIntelligenceHeld("DUPLICATE_VALUE_PORTFOLIO_ACCOUNT")
        seen.add(identity)
        outcome = review_buyer_value_first_offer(
            case, verified_signals=signals, now=now,
        )
        statuses[outcome["review_play"]] += 1
        if outcome["offer_candidate"] is not None:
            chosen[outcome["offer_candidate"]] += 1
            experience_candidates += 1
    return {
        "schema_version": "empire.gtm.buyer_value_first_portfolio.v1",
        "accounts_reviewed": len(seen),
        "buyer_value_next_play_counts": dict(sorted(statuses.items())),
        "evidence_backed_offer_candidate_counts": dict(sorted(chosen.items())),
        "proof_first_private_page_candidate_count": experience_candidates,
        "public_buyer_list_exposed": False,
        "messages_or_quotes_sent": 0,
        "execution_authority": "NONE",
    }

# Proof-backed offer experiences are PRIVATE previews. Website, consent,
# tracking and public deployment remain with their existing owners.
_OFFER_EXPERIENCE_EDITORIAL = {
    "buyer_inventory_fit_offer": {
        "eyebrow": "Buyer inventory fit",
        "headline": "Better-fit opportunities start with better evidence.",
        "intro": (
            "See how territory, category and acceptance criteria can be checked "
            "against separately verified availability before a buying decision."
        ),
        "sections": (
            ("Define the buy box", "Agree the exact categories, territories and rejection criteria."),
            ("Verify actual availability", "Review current source records, their scope and any gaps."),
            ("Make a measured decision", "Review what fits and what cannot yet be supported."),
        ),
        "questions": (
            ("Is inventory guaranteed?", "No. Availability and buyer acceptance must be verified for the relevant corridor."),
            ("Will every enquiry qualify?", "No. An acceptance check should make rejection rules explicit."),
        ),
    },
    "revenue_leak_signal_offer": {
        "eyebrow": "Demand-to-response intelligence",
        "headline": "Find the gaps between an enquiry and a useful response.",
        "intro": (
            "Review measured handoff evidence and identify which conversion "
            "or response stage deserves a controlled improvement."
        ),
        "sections": (
            ("Trace the handoff", "Confirm the observed stages and the sources behind them."),
            ("Locate a measurable gap", "Separate supported conversion gaps from assumptions."),
            ("Test one practical fix", "Choose a small, governed workflow experiment and measure its outcome."),
        ),
        "questions": (
            ("Are projected savings guaranteed?", "No. Cost and profit claims require verified actual financial receipts."),
            ("Will the system contact leads automatically?", "No. Contact channels and permissions remain separately governed."),
        ),
    },
    "verified_market_opportunity_brief": {
        "eyebrow": "Evidence-based market choices",
        "headline": "Choose your next territory with evidence, not guesswork.",
        "intro": (
            "Compare independently sourced observations with your buying criteria "
            "and identify what remains unproven before committing resources."
        ),
        "sections": (
            ("Set the market criteria", "Define geography, category and minimum source quality."),
            ("Review the observations", "Inspect verifiable public-market evidence and its dates."),
            ("Define the next test", "Narrow the field and check unknowns before any spend."),
        ),
        "questions": (
            ("Does market activity prove buyer demand?", "No. Research signals are not confirmed purchasing intent."),
            ("Are financial returns projected?", "No. Revenue and return claims require independently verified outcomes."),
        ),
    },
}
# A private offer preview must answer the questions the prospect is already
# carrying, and must state the unknowns rather than hide them behind a form.
# These labels are editorial disclosures, not scores or source attestations.
_PROSPECT_DECISION_QUESTIONS = (
    ("buyer_fit", "Is this relevant to my business?"),
    ("deliverable", "What exactly will I get?"),
    ("evidence_trust", "Why should I believe the evidence?"),
    ("business_value", "What business value might this create?"),
    ("price_and_risk", "What will I pay and what is the risk?"),
    ("delivery_timing", "How quickly can we start and deliver?"),
    ("differentiation", "Why choose Empire AI?"),
    ("working_next_step", "What happens if I want to proceed?"),
)


def review_prospect_question_coverage(
    verified_value_report: Mapping[str, object], *,
    market_label: str,
    source_review_day: str,
) -> dict:
    """Self-critical prospect FAQ coverage from an already verified value case.

    Does not conjure approved pricing, delivery capacity, case-study results
    or a published CTA; those belong to independent catalog, fulfilment,
    finance and website owners. Reports open questions rather than claiming
    that the preview solves an entire commercial purchase decision.
    """
    if (not isinstance(verified_value_report, Mapping)
            or verified_value_report.get("offer_candidate") not in _OFFER_EXPERIENCE_EDITORIAL
            or verified_value_report.get("buyer_problem_proven_by_first_party") is not True
            or type(market_label) is not str
            or market_label not in ("UK solar buyers", "US roofing buyers")
            or type(source_review_day) is not str
            or len(source_review_day) != 10):
        raise CampaignIntelligenceHeld("PROSPECT_QUESTION_SOURCE_PROOF_REQUIRED")
    arm = verified_value_report["offer_candidate"]
    key_to_answer = {
        "buyer_fit": (
            "REVIEW_ANSWERED",
            f"This evidence-led first review is scoped to {market_label} and "
            "an independently stated buying question. Specific acceptance "
            "criteria still need review.",
        ),
        "deliverable": (
            "REVIEW_ANSWERED",
            str(verified_value_report["value_first_deliverable"]),
        ),
        "evidence_trust": (
            "PARTIALLY_ANSWERED",
            f"Source capability last reviewed {source_review_day}; "
            "request the underlying source, coverage and limitations. "
            "This is not an independently verified customer case study.",
        ),
        "business_value": (
            "PARTIALLY_ANSWERED",
            "The first deliverable can inform a business decision. "
            "No financial impact or incremental lift is proven yet.",
        ),
        "price_and_risk": (
            "UNANSWERED_REQUIRES_OWNER",
            "A price, contract, acceptance rules and cancellation/risk terms "
            "must come from an approved commercial offer, not this preview.",
        ),
        "delivery_timing": (
            "UNANSWERED_REQUIRES_OWNER",
            "Start date, turnaround and delivery capacity are not independently "
            "confirmed here. Do not invent a timeline.",
        ),
        "differentiation": (
            "PARTIALLY_ANSWERED",
            "Empire AI proposes checking source provenance and buyer-fit "
            "criteria before making an offer. No competitor comparison or "
            "unique performance advantage has been independently proven.",
        ),
        "working_next_step": (
            "UNANSWERED_REQUIRES_OWNER",
            "This is a private review, not an active offer page. The existing "
            "website owner must connect a tested, approved first-party enquiry "
            "route before a visitor can act.",
        ),
    }
    rows = [
        {"question_key": key, "question": question,
         "coverage": key_to_answer[key][0], "answer": key_to_answer[key][1]}
        for key, question in _PROSPECT_DECISION_QUESTIONS
    ]
    return {
        "schema_version": "empire.gtm.prospect_decision_question_coverage.v1",
        "questions_reviewed": len(rows),
        "answered_at_review_level": sum(
            x["coverage"] == "REVIEW_ANSWERED" for x in rows
        ),
        "partially_answered": sum(
            x["coverage"] == "PARTIALLY_ANSWERED" for x in rows
        ),
        "owner_evidence_needed": sum(
            x["coverage"] == "UNANSWERED_REQUIRES_OWNER" for x in rows
        ),
        "open_question_keys": [
            x["question_key"] for x in rows
            if x["coverage"] == "UNANSWERED_REQUIRES_OWNER"
        ],
        "questions": rows,
        "all_commercial_questions_answered": False,
        "conversion_ready_for_live_site": False,
        "execution_authority": "NONE",
    }


_PROOF_SURFACE_EDITORIAL = {
    "source_signal": "Source observations",
    "qualification": "Acceptance and qualification",
    "buyer_routing": "Buyer routing boundaries",
    "crm_followup": "CRM follow-up process",
    "pipeline_signal": "Observed pipeline evidence",
    "conversion": "Conversion evidence",
    "followup": "Follow-up process",
    "current_process": "Current process",
    "automation": "Automation controls",
    "economic_evidence": "Verifiable financial evidence",
}


def build_private_buyer_offer_experience(
    case: TrustedBuyerValueCase, *,
    verified_signals: Iterable[TrustedCampaignSignal],
    now: datetime,
) -> dict:
    """Create a self-contained, review-only page and demo storyboard.

    Never renders customer PII, source tokens, account keys, monetary amounts,
    URLs, cookies, scripts or actionable forms. Unverified buyer needs,
    suppressed accounts and undeliverable offers cannot produce a page.
    """
    from html import escape
    report = review_buyer_value_first_offer(
        case, verified_signals=verified_signals, now=now,
    )
    if report["offer_candidate"] is None:
        return {
            "schema_version": "empire.gtm.private_buyer_offer_experience.v1",
            "status": "HOLD_NO_SUPPORTED_PUBLIC_FACING_VALUE",
            "review_play": report["review_play"],
            "offer_arm": None,
            "private_html": None,
            "demo_storyboard": None,
            "publication_authorized": False,
            "working_first_party_cta_present": False,
            "execution_authority": "NONE",
        }
    arm = report["offer_candidate"]
    editorial = _OFFER_EXPERIENCE_EDITORIAL[arm]
    demo = report["proof_based_demo_outline"]
    if not isinstance(demo, Mapping):
        raise CampaignIntelligenceHeld("VERIFIED_DEMO_PLAN_MISSING")
    scope = case.context.market_scope
    market_label = {
        "GB:solar:buyers": "UK solar buyers",
        "US:roofing:buyers": "US roofing buyers",
    }.get(scope)
    if not market_label:
        raise CampaignIntelligenceHeld("OFFER_EXPERIENCE_MARKET_INVALID")
    proof_statuses = report["offer_proof_statuses"]
    if proof_statuses.get(arm) != "VERIFIED_VALUE_PREVIEW_AVAILABLE":
        raise CampaignIntelligenceHeld("OFFER_EXPERIENCE_PROOF_NOT_READY")
    cap = next(c for c in case.capabilities if c.offer_arm == arm)
    verified_day = _aware(cap.verified_at).date().isoformat()
    questions_review = review_prospect_question_coverage(
        report, market_label=market_label, source_review_day=verified_day,
    )
    storefront_questions = "".join(
        f'<details><summary>{escape(item["question"])}</summary>'
        f'<p>{escape(item["answer"])}</p></details>'
        for item in questions_review["questions"]
    )
    storyboard = [
        {
            "step": idx + 1,
            "segment_seconds": 60,
            "title": headline,
            "what_to_show": detail,
            "live_customer_example_included": False,
        }
        for idx, (headline, detail) in enumerate(editorial["sections"])
    ]
    faq_cards = "".join(
        f"<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>"
        for q, a in editorial["questions"]
    )
    steps = "".join(
        (
            '<article class="step"><span class="number">'
            f'{idx:02d}</span><h3>{escape(title)}</h3>'
            f'<p>{escape(description)}</p></article>'
        )
        for idx, (title, description) in enumerate(editorial["sections"], 1)
    )
    proof_labels = [
        _PROOF_SURFACE_EDITORIAL[code]
        for code in demo["proof_surfaces_for_owner_to_verify"]
        if code in _PROOF_SURFACE_EDITORIAL
    ]
    proof_list = "".join(f"<li>{escape(item)}</li>" for item in proof_labels)
    friction = report["buyer_risk_resolution"]
    friction_block = (
        f'<div class="notice"><strong>Your documented concern</strong>'
        f'<p>{escape(friction)}</p></div>'
        if friction else ""
    )
    note = (
        "A verified direct enquiry is available for a human-reviewed next step."
        if report["commercial_cta_review_eligible"]
        else "First review the evidence; a sales conversation is not presumed."
    )
    # The preview has no web form, CTA link, contact identifier or external
    # dependency. The publishing owner must supply verified legal/brand/CTA
    # approval, security headers, a real landing route and consent text.
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'; frame-ancestors 'none'">
<title>Evidence-first buyer brief | Empire AI</title>
<style>
:root{{--ink:#edf3fc;--muted:#b5c4d9;--line:#32445b;--accent:#8be3f5}}
*{{box-sizing:border-box}}body{{margin:0;background:#08121e;color:var(--ink);font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.6}}
main{{max-width:1100px;margin:auto;padding:30px clamp(20px,5vw,64px) 88px}}
a{{color:inherit}}.strip{{border:1px solid #4d7090;color:#bdd7e8;padding:9px 14px;border-radius:99px;font-size:12px;font-weight:700;letter-spacing:.12em;display:inline-block}}
header{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:85px}}
.brand{{font-size:18px;font-weight:780;letter-spacing:-.02em}}
.kicker{{color:var(--accent);font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:12px}}
h1{{font-size:clamp(42px,6.5vw,80px);line-height:1.08;letter-spacing:-.052em;max-width:920px;margin:18px 0 24px}}
.lead{{font-size:clamp(18px,2vw,22px);color:var(--muted);max-width:750px}}
.meta{{display:flex;flex-wrap:wrap;gap:14px;margin-top:35px}}
.pill{{border:1px solid var(--line);border-radius:99px;padding:10px 16px;color:#cfdeef;font-size:13px}}
section{{margin-top:100px}}
h2{{font-size:clamp(29px,4vw,45px);line-height:1.12;letter-spacing:-.04em;margin-bottom:15px}}
.sub{{color:var(--muted);max-width:740px}}
.steps{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:32px}}
.step{{border:1px solid var(--line);border-radius:18px;padding:25px;background:#101f30}}
.number{{color:var(--accent);font-weight:700;letter-spacing:.1em}}
h3{{font-size:20px;line-height:1.25;margin:45px 0 8px}}
.step p,details p{{color:var(--muted);font-size:15px}}
.proof{{display:grid;grid-template-columns:1fr 1fr;gap:30px;background:#14283a;border:1px solid #34627d;padding:32px;border-radius:22px}}
.proof ul{{padding-left:20px;color:#d2e3f1}}
details{{border-bottom:1px solid var(--line);padding:20px 0}}
summary{{font-weight:650;cursor:pointer}}
.notice{{border-left:3px solid var(--accent);padding:17px 23px;background:#102739;margin-top:25px}}
.notice p{{margin-bottom:0;color:var(--muted)}}
.next{{border-radius:24px;border:1px solid #426f81;padding:32px 36px;background:linear-gradient(120deg,#123247,#0e1e2f)}}
footer{{color:#849bb3;font-size:13px;border-top:1px solid var(--line);margin-top:95px;padding-top:24px}}
@media(max-width:720px){{header{{margin-bottom:60px}}.steps,.proof{{grid-template-columns:1fr}}section{{margin-top:65px}}h3{{margin-top:26px}}}}
</style>
</head>
<body>
<main>
<header><div class="brand">Empire AI<span style="color:#8be3f5"> / Intelligence</span></div><span class="strip">PRIVATE PREVIEW — NOT LIVE</span></header>
<div class="kicker">{escape(editorial["eyebrow"])}</div>
<h1>{escape(editorial["headline"])}</h1>
<p class="lead">{escape(editorial["intro"])}</p>
<div class="meta"><div class="pill">{escape(market_label)}</div><div class="pill">Source reviewed: {escape(verified_day)}</div><div class="pill">Availability must be rechecked</div></div>
<section><p class="kicker">How the review works</p><h2>Three evidence-led steps.</h2><p class="sub">A useful starting point—not a claim of inventory, cost savings or a buying commitment.</p><div class="steps">{steps}</div></section>
<section><p class="kicker">What must be verified</p><div class="proof"><div><h2>Show the source. Explain the limits.</h2><p class="sub">These are proof surfaces for an owner-reviewed walkthrough, not verified customer outcomes.</p></div><div><ul>{proof_list}</ul></div></div></section>
<section><p class="kicker">Questions a buyer will ask</p><h2>Real answers. Clear unknowns.</h2><p class="sub">Two questions are answered at review level; others are partial or need independent commercial verification. Missing details are not hidden behind a sales call.</p>{storefront_questions}{faq_cards}{friction_block}</section>
<section><div class="next"><p class="kicker">Next step — human review only</p><h2>Start with a source-backed brief.</h2><p class="sub">{escape(note)} No form, external link or automatic contact has been activated.</p></div></section>
<footer>Empire AI · Internal proof-first offer preview · No implied customer endorsement, lead guarantee, financial result or marketing permission.</footer>
</main></body></html>"""
    return {
        "schema_version": "empire.gtm.private_buyer_offer_experience.v1",
        "status": "PRIVATE_OPERATOR_PREVIEW_READY",
        "review_play": report["review_play"],
        "offer_arm": arm,
        "market_scope": scope,
        "private_html": html,
        "demo_storyboard": storyboard,
        "demo_target_seconds": sum(x["segment_seconds"] for x in storyboard),
        "source_proof_day": verified_day,
        "proof_surface_review_names": proof_labels,
        "prospect_question_coverage": questions_review,
        "publication_authorized": False,
        "working_first_party_cta_present": False,
        "financial_results_or_inventory_quantity_claimed": False,
        "customer_or_account_identity_exposed": False,
        "legal_privacy_consent_and_landing_owner_signoff_required": True,
        "execution_authority": "NONE",
    }

# Commercial proof experience -> existing published research route -> canonical
# first-party enquiry -> authenticated CRM -> independently verified economics.
# The campaign owner reads receipts; it never becomes the website intake or
# Revenue Pulse writer. No browser-provided identity or UTM gets trusted.
@dataclass(frozen=True)
class TrustedResearchEnquiry:
    campaign_id: str
    asset_id: str
    receipt_id: str  # actual UUID from owned_campaign_enquiries.read-only owner
    received_at: datetime
    release_website_binding_verified: bool
    canonical_intake_readback_verified: bool
    original_same_origin_admission_verified: bool


@dataclass(frozen=True)
class TrustedResearchCrmAttribution:
    campaign_id: str
    enquiry_receipt_id: str
    tenant_id: str  # independently authenticated canonical CRM UUID
    prospect_id: str
    recorded_at: datetime
    exact_intake_to_prospect_link_verified: bool
    authenticated_tenant_reader_verified: bool


@dataclass(frozen=True)
class TrustedResearchCommercialOutcome:
    campaign_id: str
    tenant_id: str
    prospect_id: str
    order_id: str
    finance_event_key: str
    paid_at: datetime
    delivered_at: datetime | None
    recognized_at: datetime | None
    actual_cost_verified: bool
    payment_settlement_verified: bool
    fulfilment_verified: bool
    recognized_revenue_event_verified: bool
    canonical_order_prospect_join_verified: bool
    recognized_revenue_cents: int | None
    actual_cost_cents: int | None
    realized_gp_cents: int | None


def review_released_research_route(
    *, root: object, campaign_id: str, now: datetime,
) -> dict:
    """Read the existing signed release, not the mutable campaign planner.

    A released research form is an operational endpoint; it does not imply
    the *new* value-first proof HTML is approved or published there.
    """
    from pathlib import Path
    from empire_os.owned_campaign_release import load_release
    from empire_os.owned_campaign_preflight import _landing
    from empire_os.owned_campaign_content import PRIVACY
    now = _aware(now)
    if not _CAMPAIGN.fullmatch(campaign_id):
        raise CampaignIntelligenceHeld("INVALID_RESEARCH_CAMPAIGN_ID")
    if not isinstance(root, Path):
        raise CampaignIntelligenceHeld("EXPLICIT_CANONICAL_REPOSITORY_ROOT_REQUIRED")
    snapshot = load_release(root=root)
    if snapshot is None:
        return {
            "schema_version": "empire.gtm.released_research_conversion_route.v1",
            "status": "HOLD_UNVERIFIED_WEBSITE_RELEASE",
            "current_research_path": None,
            "canonical_enquiry_post_path": None,
            "active_proof_experience_published": False,
            "live_http_verified_here": False,
            "execution_authority": "NONE",
        }
    matches = [x for x in snapshot["campaigns"] if x.get("campaign_id") == campaign_id]
    if len(matches) != 1:
        return {
            "schema_version": "empire.gtm.released_research_conversion_route.v1",
            "status": "HOLD_NO_MATCHING_RELEASED_CAMPAIGN",
            "current_research_path": None,
            "canonical_enquiry_post_path": None,
            "active_proof_experience_published": False,
            "live_http_verified_here": False,
            "execution_authority": "NONE",
        }
    c = matches[0]
    landing = _landing(c)
    path = "/research/" + campaign_id
    if (c.get("conversion_plan", {}).get("landing_path") != path
            or landing.get("asset_id") != campaign_id + ":landing"
            or landing.get("privacy_notice") != PRIVACY
            or c.get("outbound_authorized", False) is not False
            or c.get("automatic_followup", False) is not False):
        raise CampaignIntelligenceHeld("RELEASED_RESEARCH_JOURNEY_CONTRACT_CHANGED")
    return {
        "schema_version": "empire.gtm.released_research_conversion_route.v1",
        "status": "EXISTING_RELEASE_VERIFIED_RESEARCH_ROUTE",
        "current_research_path": path,
        "canonical_enquiry_post_path": "/api/research/enquiry",
        "canonical_event_post_path": "/api/research/event",
        "source_research_campaign_id": campaign_id,
        "source_asset_id": landing["asset_id"],
        "first_party_form_fields": (
            "campaign_id", "asset_id", "reply_email", "research_question"
        ),
        "optional_form_fields": ("company", "role"),
        "form_reply_not_marketing_subscription": True,
        "origin_policy_enforced_by_existing_gateway": True,
        "released_campaign_is_first_party_owner_only": True,
        "active_proof_experience_published": False,
        "live_http_verified_here": False,
        "execution_authority": "NONE",
    }


def reconcile_first_party_conversion_journey(
    *,
    root: object,
    released_route: Mapping[str, object],
    enquiries: Iterable[TrustedResearchEnquiry] | None,
    crm_links: Iterable[TrustedResearchCrmAttribution] | None,
    commercial_outcomes: Iterable[TrustedResearchCommercialOutcome] | None,
    now: datetime,
    finance_window_complete: bool = False,
) -> dict:
    """End-to-end source-receipt join, not automatic attribution or payment.

    Browser form submission is never identity, permission, order or sales
    proof. The website owner supplies persisted enquiry readback; CRM owner
    supplies exact tenant/prospect linkage; Finance supplies settled payment,
    fulfilment, recognized revenue and independently evidenced costs.
    """
    from uuid import UUID
    from empire_os.revenue_crm_channel_evidence import canonical_uuid
    now = _aware(now)
    if (not isinstance(released_route, Mapping)
            or released_route.get("status") != "EXISTING_RELEASE_VERIFIED_RESEARCH_ROUTE"
            or released_route.get("canonical_enquiry_post_path") != "/api/research/enquiry"
            or released_route.get("execution_authority") != "NONE"
            or type(finance_window_complete) is not bool):
        raise CampaignIntelligenceHeld("EXISTING_CANONICAL_RELEASE_REQUIRED")
    campaign = released_route.get("source_research_campaign_id")
    asset = released_route.get("source_asset_id")
    if (type(campaign) is not str or not _CAMPAIGN.fullmatch(campaign)
            or asset != campaign + ":landing"
            or released_route.get("current_research_path") != "/research/" + campaign):
        raise CampaignIntelligenceHeld("ENQUIRY_CAMPAIGN_ASSET_BOUNDARY_INVALID")
    # Release attestations cannot arrive from a browser/body or arbitrary
    # mapping. Recompute from the existing immutable website release on each
    # review; stale/revoked releases fail closed even with old intake receipts.
    canonical_route = review_released_research_route(
        root=root, campaign_id=campaign, now=now,
    )
    if (canonical_route.get("status") != "EXISTING_RELEASE_VERIFIED_RESEARCH_ROUTE"
            or dict(released_route) != canonical_route):
        raise CampaignIntelligenceHeld("RESEARCH_RELEASE_READBACK_MISMATCH")
    if (crm_links is not None and enquiries is None
            or commercial_outcomes is not None and crm_links is None
            or finance_window_complete and commercial_outcomes is None):
        raise CampaignIntelligenceHeld("UNSUPPORTED_DOWNSTREAM_WITHOUT_UPSTREAM_PROOF")
    def check_uuid(value):
        try:
            raw = canonical_uuid(value)
            if raw == "00000000-0000-0000-0000-000000000000":
                raise ValueError("zero id")
            return raw
        except (ValueError, TypeError, AttributeError):
            raise CampaignIntelligenceHeld("CANONICAL_JOURNEY_RECEIPT_UUID_REQUIRED") from None

    def bounded(rows, cls, ceiling):
        if rows is None:
            return None
        if type(rows) not in (tuple, list):
            raise CampaignIntelligenceHeld("TRUSTED_CANONICAL_READER_BATCH_REQUIRED")
        if len(rows) > ceiling or any(type(x) is not cls for x in rows):
            raise CampaignIntelligenceHeld("TRUSTED_CANONICAL_READER_BATCH_REQUIRED")
        return rows

    incoming = bounded(enquiries, TrustedResearchEnquiry, 500)
    linked = bounded(crm_links, TrustedResearchCrmAttribution, 500)
    outcomes = bounded(commercial_outcomes, TrustedResearchCommercialOutcome, 1000)
    enq: dict[str, TrustedResearchEnquiry] = {}
    for x in incoming or ():
        ref = check_uuid(x.receipt_id)
        ts = _aware(x.received_at)
        if (x.campaign_id != campaign or x.asset_id != asset
                or any(type(flag) is not bool or flag is not True for flag in (
                    x.release_website_binding_verified,
                    x.canonical_intake_readback_verified,
                    x.original_same_origin_admission_verified,
                ))
                or not ts <= now or now - ts > timedelta(days=180)):
            raise CampaignIntelligenceHeld("FIRST_PARTY_ENQUIRY_SOURCE_CONFLICT")
        if ref in enq:
            raise CampaignIntelligenceHeld("DUPLICATE_ENQUIRY_RECEIPT_REPLAY")
        enq[ref] = x
    prospects: dict[tuple[str, str], TrustedResearchCrmAttribution] = {}
    matched_receipts: set[str] = set()
    tenant_set: set[str] = set()
    for x in linked or ():
        ref = check_uuid(x.enquiry_receipt_id)
        tenant = check_uuid(x.tenant_id)
        pid = check_uuid(x.prospect_id)
        key = (tenant, pid)
        ts = _aware(x.recorded_at)
        if (x.campaign_id != campaign or ref not in enq
                or ts < enq[ref].received_at or ts > now
                or x.exact_intake_to_prospect_link_verified is not True
                or x.authenticated_tenant_reader_verified is not True):
            raise CampaignIntelligenceHeld("CANONICAL_CRM_ENQUIRY_BINDING_INVALID")
        if key in prospects or ref in matched_receipts:
            raise CampaignIntelligenceHeld("DUPLICATE_OR_AMBIGUOUS_CRM_ENQUIRY_BINDING")
        prospects[key] = x
        matched_receipts.add(ref)
        tenant_set.add(tenant)
    if len(tenant_set) > 1:
        raise CampaignIntelligenceHeld("CROSS_TENANT_CAMPAIGN_JOURNEY_JOIN")
    seen_orders: set[str] = set()
    seen_finance_events: set[str] = set()
    paid_people: set[tuple[str, str]] = set()
    recognized_orders = 0
    recognized_total = 0
    gp_total = 0
    gp_complete = True
    for x in outcomes or ():
        tenant, pid = check_uuid(x.tenant_id), check_uuid(x.prospect_id)
        order = check_uuid(x.order_id)
        key = (tenant, pid)
        if (x.campaign_id != campaign or key not in prospects
                or not _opaque(x.finance_event_key)
                or x.canonical_order_prospect_join_verified is not True
                or x.payment_settlement_verified is not True
                or type(x.fulfilment_verified) is not bool
                or type(x.recognized_revenue_event_verified) is not bool
                or type(x.actual_cost_verified) is not bool
                or order in seen_orders or x.finance_event_key in seen_finance_events):
            raise CampaignIntelligenceHeld("UNVERIFIED_DUPLICATE_OR_CROSS_ACCOUNT_FINANCE")
        seen_orders.add(order)
        seen_finance_events.add(x.finance_event_key)
        paid_at = _aware(x.paid_at)
        if paid_at < prospects[key].recorded_at or paid_at > now:
            raise CampaignIntelligenceHeld("FINANCE_SOURCE_CAUSAL_CLOCK_INVALID")
        paid_people.add(key)
        if x.fulfilment_verified:
            if x.delivered_at is None:
                raise CampaignIntelligenceHeld("UNVERIFIED_DELIVERY_TIMESTAMP")
            delivery = _aware(x.delivered_at)
            if delivery < paid_at or delivery > now:
                raise CampaignIntelligenceHeld("FINANCE_SOURCE_CAUSAL_CLOCK_INVALID")
        elif x.delivered_at is not None:
            raise CampaignIntelligenceHeld("UNVERIFIED_DELIVERY_PROVENANCE")
        if x.recognized_revenue_event_verified:
            if (not x.fulfilment_verified or x.recognized_at is None
                    or type(x.recognized_revenue_cents) is not int
                    or x.recognized_revenue_cents < 0):
                raise CampaignIntelligenceHeld("UNVERIFIED_REVENUE_RECOGNITION")
            recognized_at = _aware(x.recognized_at)
            if recognized_at < _aware(x.delivered_at) or recognized_at > now:
                raise CampaignIntelligenceHeld("FINANCE_SOURCE_CAUSAL_CLOCK_INVALID")
            recognized_orders += 1
            recognized_total += x.recognized_revenue_cents
            if x.actual_cost_verified:
                if (type(x.actual_cost_cents) is not int or x.actual_cost_cents < 0
                        or type(x.realized_gp_cents) is not int
                        or x.realized_gp_cents !=
                        x.recognized_revenue_cents - x.actual_cost_cents):
                    raise CampaignIntelligenceHeld("UNVERIFIED_ACTUAL_COST_OR_MARGIN")
                gp_total += x.realized_gp_cents
            else:
                if x.actual_cost_cents is not None or x.realized_gp_cents is not None:
                    raise CampaignIntelligenceHeld("UNVERIFIED_ACTUAL_COST_OR_MARGIN")
                gp_complete = False
        elif (x.recognized_at is not None or x.recognized_revenue_cents is not None
              or x.actual_cost_cents is not None or x.realized_gp_cents is not None
              or x.actual_cost_verified):
            raise CampaignIntelligenceHeld("UNVERIFIED_PREMATURE_REVENUE_CLAIM")
    ready_finance = outcomes is not None and finance_window_complete
    return {
        "schema_version": "empire.gtm.first_party_to_realized_profit.v1",
        "campaign_released_source_bound": True,
        "accepted_first_party_enquiry_receipts": len(enq) if incoming is not None else None,
        "authenticated_crm_enquiries_linked": len(prospects) if linked is not None else None,
        "finance_receipt_window_closed": ready_finance,
        "observed_paid_buyers": len(paid_people) if outcomes is not None else None,
        "recognized_order_count": recognized_orders if ready_finance else None,
        "recognized_campaign_revenue_cents": recognized_total if ready_finance else None,
        "realized_campaign_gp_cents": (
            gp_total if ready_finance and gp_complete and recognized_orders > 0
            else None
        ),
        "revenue_attribution_basis": (
            "EXACT_INTAKE_CRM_ORDER_JOIN_WITH_CLOSED_FINANCE_WINDOW"
            if ready_finance else "NO_COMPLETE_CANONICAL_FINANCE_WINDOW"
        ),
        "channel_or_roi_causal_lift_proven": False,
        "unlinked_enquiries_observed": (
            len(enq) - len(matched_receipts) if incoming is not None and linked is not None
            else None
        ),
        "identifying_or_payment_receipt_ids_exposed": 0,
        "first_party_form_created": False,
        "new_crm_or_payment_writer_created": False,
        "outreach_or_money_moved": False,
        "execution_authority": "NONE",
    }
