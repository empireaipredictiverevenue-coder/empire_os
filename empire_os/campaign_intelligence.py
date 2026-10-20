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
