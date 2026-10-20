"""Read-only operational assessment of Taylor Haren-style TAM-to-revenue campaigns.

Reuses Empire's TAM, outreach optimiser, owned campaign, analytics and measured
outcome snapshots. Plans one 30-60-day market touch, offer/creative experiments,
same-day signal review and paying-customer feedback. NEVER dispatches outreach,
enrols contacts, exports audiences, or changes any production source.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping

from empire_os.experiment_engine import ExperimentDefinition, plan_assignment

SCHEMA = "empire.gtm.tam_full_funnel_campaign_review.v1"
SOURCES = {
    "tam": ("runtime/tam_market_intelligence/latest.json",
            "empire.tam-market-intelligence.v1"),
    "optimizer": ("runtime/outreach_optimizer/latest.json",
                  "empire.adaptive-outreach-performance.v1"),
    "campaigns": ("runtime/campaigns_control/campaign_runtime_observer_latest.json",
                  "empire-campaign-runtime-observer-v1"),
    "outcomes": ("runtime/campaigns_control/campaign_measured_outcome_latest.json",
                 "empire-campaign-measured-outcome-v1"),
    "assets": ("runtime/astra/owned_campaign_deployed_release.json",
               "empire.owned-campaign-release.v1"),
}
DAYS_FRESH = 2
MAX_FILE_BYTES = 512 * 1024

# Deliberately separate measurement of clicks from independent customer proof.
FUNNEL = (
    "qualified_tam", "eligible_contacts", "messages_delivered",
    "verified_human_engagement", "consented_site_visits",
    "server_accepted_enquiries", "booked_meetings",
    "verified_paying_customers", "recognised_revenue",
)

WORKFLOW = (
    ("market", "TAM owner", "Reconcile full market, dedupe companies and roles, validate lawful contactability."),
    ("offer", "Sales Director", "Prepare outcome-first, low-friction offers for each market segment."),
    ("creative", "Outreach owner", "Randomise substantially different offer/copy/CTA arms using the existing experiment registry."),
    ("delivery", "Outreach owner", "Deliver one compliant touch per eligible market contact in a 30-60-day cycle; honor cooldowns and suppression."),
    ("signals", "Analytics owner", "Attribute actual clicks, independently verified website engagement and signup receipts."),
    ("response", "Sales Director", "Same-business-day review of verified opt-in/meeting events and sufficiently supported intent."),
    ("retargeting", "Paid media owner", "Only consider platform-compliant retargeting when specific permissions and budget are authorised."),
    ("revenue", "Revenue owner", "Link CRM, fulfilled orders and settled revenue receipts before declaring a winner."),
)


def _fresh(iso: Any, now: datetime) -> bool:
    if type(iso) is not str:
        return False
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return False
    return ts.tzinfo is not None and timedelta(minutes=-5) <= (
        now - ts.astimezone(timezone.utc)
    ) <= timedelta(days=DAYS_FRESH)


def _count(x: Any) -> int | None:
    return x if type(x) is int and 0 <= x <= 10**9 else None


def _safe_source(data: Any, name: str, now: datetime) -> dict[str, Any]:
    if (not isinstance(data, Mapping)
            or data.get("schema_version") != SOURCES[name][1]):
        return {"source_compatible": False, "fresh": False}
    return {
        "source_compatible": True,
        "fresh": _fresh(data.get("generated_at"), now) if name != "assets" else False,
    }


def read_existing_snapshots(root: Path) -> dict[str, dict[str, Any]]:
    """Fixed allowlisted paths; refuses symlinks/oversized snapshots."""
    results = {}
    for name, (rel, _) in SOURCES.items():
        p = root / rel
        try:
            if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("source unavailable or oversized")
            obj = json.loads(p.read_text(encoding="utf-8"))
            results[name] = obj if isinstance(obj, dict) else {}
        except (ValueError, OSError):
            results[name] = {}
    return results


def review_full_funnel_strategy(
    sources: Mapping[str, Any], *, now: datetime,
) -> dict[str, Any]:
    """Compute safe operational truth; NEVER infer metrics from adjacent stages."""
    if not isinstance(sources, Mapping) or now.tzinfo is None:
        raise ValueError("source map and aware clock required")
    now = now.astimezone(timezone.utc)
    raw = {name: sources.get(name, {}) for name in SOURCES}
    meta = {name: _safe_source(raw[name], name, now) for name in SOURCES}
    tam = raw["tam"] if meta["tam"]["source_compatible"] else {}
    opt = raw["optimizer"] if meta["optimizer"]["source_compatible"] else {}
    c = raw["campaigns"] if meta["campaigns"]["source_compatible"] else {}
    o = raw["outcomes"] if meta["outcomes"]["source_compatible"] else {}
    a = raw["assets"] if meta["assets"]["source_compatible"] else {}

    # Verified research SAMPLE can never be promoted into complete TAM.
    observed = _count(tam.get("observed_unique_entity_count"))
    tam_complete = (
        meta["tam"]["fresh"]
        and tam.get("source_population_complete") is True
        and tam.get("tenant_source_scope_verified") is True
        and tam.get("tam_inferred_from_observed_roster") is False
    )
    assets = a.get("campaign_ids")
    asset_count = len(assets) if isinstance(assets, list) and all(
        isinstance(i, str) and len(i) <= 150 for i in assets) else None
    runtime_count = _count(c.get("campaign_count")) if meta["campaigns"]["fresh"] else None
    asset_evidence = (
        asset_count if a.get("deployment_verified") is True
        and runtime_count == asset_count and c.get("status") == "VERIFIED_RUNTIME"
        else None
    )
    exact_matches = _count(o.get("exact_outcome_match_count")) if meta["outcomes"]["fresh"] else None
    outcomes_verified = bool(
        meta["outcomes"]["fresh"]
        and o.get("outcome_linkage_proved") is True
        and exact_matches is not None and exact_matches > 0
    )
    optimizer_active = (
        meta["optimizer"]["fresh"]
        and opt.get("learning_state") == "LEARNING"
        and opt.get("outbound_mutation") is False
    )
    safe_optimizer = {
        "fresh_learning_source": optimizer_active,
        "labelled_intent_examples": _count(opt.get("labelled_intent_count")) if optimizer_active else None,
        "revenue_winner_verified": bool(outcomes_verified and opt.get("winner_claim_allowed") is True),
    }

    exp = ExperimentDefinition(
        experiment_id="tam-full-funnel-offer-angle-20261020",
        hypothesis="An outcome-first offer produces more verified customers per eligible delivery than feature-led copy.",
        metric="verified_paying_customers_per_randomly_assigned_account",
        control_variant="no_marketing_holdout",
        treatment_variants=(
            "buyer_inventory_fit_offer", "revenue_leak_signal_offer",
            "verified_market_opportunity_brief",
        ),
        holdout_fraction=0.10,
        minimum_sample_size=50,
    ).as_dict()
    # Proposed tests are a design. No assignment or experiment activation.
    experiment = {
        "experiment_id": exp["experiment_id"],
        "design_status": "NOT_ACTIVATED",
        "primary_metric": exp["metric"],
        "holdout_fraction": exp["holdout_fraction"],
        "variants": [exp["control_variant"], *exp["treatment_variants"]],
        "randomisation_source": "existing_empire_experiment_engine",
        "test_window_weeks": 12,
        "variable_test_order": [
            "verified_market_and_audience", "offer_outcome",
            "pain_angle", "subject_and_short_copy", "CTA"
        ],
        "minimum_sample_size_is_design_not_significance_proof": True,
    }
    blockers = []
    if not tam_complete:
        # A verified, lawful *cohort* can be tested before an exhaustive TAM
        # census; the absence of a full census blocks market-wide claims,
        # not a narrowly scoped first wave.
        blockers.append("MARKET_WIDE_COVERAGE_UNVERIFIED_SCOPED_PILOT_ONLY")
    if not asset_evidence:
        blockers.append("CAMPAIGN_ASSET_AND_RUNTIME_COUPLING_UNVERIFIED")
    if not safe_optimizer["fresh_learning_source"]:
        blockers.append("OUTREACH_LEARNING_SOURCE_UNVERIFIED")
    if not outcomes_verified:
        blockers.append("PAID_CUSTOMER_REVENUE_OUTCOME_LINKAGE_MISSING")
    # These gates are NOT resolvable from the existing aggregate snapshots.
    blockers.extend((
        "RECIPIENT_LEVEL_LAWFULNESS_SUPPRESSION_AND_CADENCE_NOT_PROVEN",
        "MAIL_DELIVERABILITY_AND_SENDER_AUTHORITY_NOT_PROVEN",
        "FIRST_PARTY_HUMAN_CLICK_AND_SITE_CONSENT_NOT_PROVEN",
        "SAME_DAY_SALES_WORKFLOW_NOT_CONNECTED",
        "RETARGETING_AUDIENCE_PERMISSION_AND_BUDGET_NOT_PROVEN",
    ))

    # The single highest-value operational TODO remains tied to the video:
    # market completeness, offer tests, delivery and whole-funnel evidence.
    return {
        "schema_version": SCHEMA,
        "status": "FULL_FUNNEL_TAM_STRATEGY_REVIEW_NOT_LIVE_ACTIVATION",
        "source_health": meta,
        "qualified_market": {
            "sampled_entities_observed": observed if meta["tam"]["source_compatible"] else None,
            "observation_fresh": meta["tam"]["fresh"],
            "complete_addressable_market_verified": tam_complete,
            "complete_market_size": None,  # Never impute from a sample.
            "eligible_permissioned_recipient_count": None,
        },
        "campaign_assets": {
            "existing_campaigns_runtime_verified": runtime_count,
            "deployed_assets_correlated_to_runtime": asset_evidence,
            "campaign_messages_sent_by_this_review": 0,
        },
        "existing_outreach_learning": safe_optimizer,
        "verified_commercial_feedback": {
            "exact_campaign_outcome_matches": exact_matches,
            "outcome_linkage_verified": outcomes_verified,
            "paid_customer_winning_variant": None,
            "attributed_recognised_revenue": None,
        },
        "experiment": experiment,
        "frequency_policy": {
            "single_touch_per_eligible_contact_per_wave": True,
            "repeat_wave_window_days": [30, 60],
            "recipient_level_dedup_suppression_and_last_contact_required": True,
            "automatic_email_sending": False,
        },
        "same_day_engagement_policy": {
            "suspected_human_click": "private_review_only_not_identity_proof",
            "website_engagement": "only_with_separate_verified_site_permission",
            "opt_in_or_booked_meeting": "owner_review_same_business_day",
            "cold_call_or_retargeting": "separate_compliance_and_channel_authority_required",
            "automatic_action": False,
        },
        "measurement_funnel": [
            {"stage": stage, "verified_value": None,
             "status": "NOT_LINKED_TO_CANONICAL_CAMPAIGN_RECEIPT"}
            for stage in FUNNEL
        ],
        "workflow_handoff": [
            {"stage": step, "existing_owner": owner, "instruction": action}
            for step, owner, action in WORKFLOW
        ],
        "twelve_week_learning_cycle": [
            "W1-2: map and validate full market, dedupe and suppress; establish baseline",
            "W3-4: prepare 3 outcome-first offers and deterministic audience/holdout split",
            "W5-8: run authorised single-touch waves only, capture actual funnel receipts and same-day review",
            "W9-10: compare eligible delivery to signups, meetings and verified customers",
            "W11-12: select commercially proven offer/audience winner or continue learning",
        ],
        "launch_blockers": blockers,
        "paid_media_budget_committed": False,
        "tracking_or_websites_changed": False,
        "external_messages_sent": False,
        "database_writes": False,
        "production_workflows_activated": False,
        "execution_authority": "NONE",
    }


_OPAQUE_CONTACT = re.compile(r"^[0-9a-f]{32}$")


def plan_compliant_market_touch(
    *, contact_lookup_key: str, market_scope_verified: bool,
    lawful_outreach_verified: bool, suppressed: bool,
    sending_domain_approved: bool, last_touch_verified: bool,
    last_touch_at: datetime | None, now: datetime,
) -> dict[str, Any]:
    """Plan ONE market wave touch using existing experiment arms; never send.

    last_touch_verified=True must mean canonical CRM history was actually
    checked and last_touch_at is the latest contact across all campaigns.
    Anonymous lookup keys are only for in-memory arm assignment.
    """
    if type(contact_lookup_key) is not str or not _OPAQUE_CONTACT.fullmatch(contact_lookup_key):
        raise ValueError("opaque CRM contact lookup key required")
    if now.tzinfo is None:
        raise ValueError("timezone-aware current time required")
    if last_touch_at is not None and last_touch_at.tzinfo is None:
        raise ValueError("timezone-aware last touch required")
    blockers = []
    if market_scope_verified is not True:
        blockers.append("COMPLETE_MARKET_MEMBERSHIP_UNVERIFIED")
    if lawful_outreach_verified is not True:
        blockers.append("CHANNEL_AND_RECIPIENT_OUTREACH_PERMISSION_UNVERIFIED")
    if suppressed is not False:
        blockers.append("CONTACT_SUPPRESSED_OR_SUPPRESSION_UNVERIFIED")
    if sending_domain_approved is not True:
        blockers.append("SENDING_IDENTITY_AND_DELIVERABILITY_UNVERIFIED")
    if last_touch_verified is not True:
        blockers.append("CROSS_CAMPAIGN_CONTACT_HISTORY_UNVERIFIED")
    if last_touch_at is not None:
        age = now.astimezone(timezone.utc) - last_touch_at.astimezone(timezone.utc)
        if age < timedelta(0):
            blockers.append("CONTACT_HISTORY_FUTURE_CLOCK")
        elif age < timedelta(days=30):
            blockers.append("MARKET_WAVE_30_DAY_COOLDOWN")
    if blockers:
        return {
            "status": "HOLD", "blockers": blockers, "planned_arm": None,
            "sent": False, "automatic_activation": False,
        }
    definition = ExperimentDefinition(
        experiment_id="tam-full-funnel-offer-angle-20261020",
        hypothesis="Compare qualifying offers on real customer outcomes.",
        metric="verified_paying_customers_per_randomly_assigned_account",
        control_variant="no_marketing_holdout",
        treatment_variants=(
            "buyer_inventory_fit_offer", "revenue_leak_signal_offer",
            "verified_market_opportunity_brief",
        ),
        holdout_fraction=0.1,
        minimum_sample_size=50,
    )
    assignment = plan_assignment(definition, subject_key=contact_lookup_key)
    return {
        "status": "PLAN_ONLY_FOUNDATION_CHECKS_PASSED",
        "planned_arm": assignment.arm,
        "holdout": assignment.assignment_kind == "holdout_control",
        "blockers": ["PRODUCTION_SENDING_AUTHORITY_NOT_CONFERRED_BY_PLAN"],
        "sent": False, "automatic_activation": False,
    }


def triage_same_day_signal(
    *, kind: str, independent_provenance_verified: bool,
    lawful_contact_permission_verified: bool,
    suppression_clear: bool,
) -> dict[str, Any]:
    """Route policy recommendation to EXISTING owners, never contact anyone."""
    kinds = {
        "email_click": "weak_interest_research_review",
        "consented_site_visit": "engagement_research_review",
        "server_accepted_enquiry": "same_business_day_sales_review",
        "booked_meeting": "same_business_day_sales_review",
        "settled_revenue": "revenue_owner_receipt_review",
    }
    if kind not in kinds:
        raise ValueError("unsupported signal kind")
    action = "HOLD_UNTRUSTED_OR_UNPERMITTED_SIGNAL"
    if independent_provenance_verified and lawful_contact_permission_verified and suppression_clear:
        action = kinds[kind]
    elif independent_provenance_verified:
        action = "INTERNAL_REVIEW_NO_OUTREACH"
    return {
        "action": action, "owner": "existing_sales_director" if kind != "settled_revenue" else "existing_revenue_owner",
        "outbound_dispatched": False, "retargeting_authorized": False,
        "human_identity_verified_by_event": False,
    }


def review_paid_customer_winners(
    arms: Mapping[str, Any], *, outcome_receipts_verified: bool,
) -> dict[str, Any]:
    """Rank only independently verified paying-customer conversion per send.

    Not a causal-lift estimate or automated scale decision.
    """
    if not isinstance(arms, Mapping) or not 2 <= len(arms) <= 10:
        raise ValueError("two to ten experiment arms required")
    if outcome_receipts_verified is not True:
        return {"winner": None, "status": "CUSTOMER_RECEIPTS_NOT_VERIFIED",
                "automatic_scaling": False}
    ranking = []
    for key, row in arms.items():
        if type(key) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{2,50}", key):
            raise ValueError("invalid experiment arm")
        if not isinstance(row, Mapping) or set(row) != {"eligible_delivered", "paid_customers"}:
            raise ValueError("invalid arm metrics")
        n, pay = row["eligible_delivered"], row["paid_customers"]
        if type(n) is not int or type(pay) is not int or n < 50 or pay < 0 or pay > n:
            raise ValueError("insufficient or invalid verified arm metrics")
        ranking.append((pay / n, pay, key))
    ranking.sort(reverse=True)
    if ranking[0][1] == 0:
        return {"winner": None, "status": "NO_OBSERVED_PAYING_CUSTOMER_WINNER",
                "automatic_scaling": False}
    return {"winner": ranking[0][2], "status": "DESCRIPTIVE_WINNER_FOR_HUMAN_REVIEW",
            "paid_customer_rate": round(ranking[0][0], 6),
            "causal_lift_claimed": False, "automatic_scaling": False}




@dataclass(frozen=True)
class RecipientWaveEvidence:
    """Private, canonical CRM projection: no emails, names, URLs or free text."""

    contact_lookup_key: str
    company_lookup_key: str
    tenant_ref: str
    market_scope: str
    last_verified_at: datetime
    last_marketing_touch_at: datetime | None
    source_authority_verified: bool
    channel_lawfulness_verified: bool
    suppression_clear: bool
    contact_history_verified: bool
    sending_domain_approved: bool
    offer_evidence_verified: bool


_MARKET_SCOPES = frozenset({"GB:solar:buyers", "US:roofing:buyers"})
_LOOKUP_KEY = re.compile(r"^[0-9a-f]{32}$")
_TENANT_REF = re.compile(r"^tenant_[a-z0-9]{8,40}$")
_WAVE_LIMIT = 500


def assemble_verified_cohort_wave(
    lookup_keys: list[str] | tuple[str, ...], *,
    trusted_resolver: Callable[[str], RecipientWaveEvidence],
    tenant_ref: str, market_scope: str, now: datetime,
) -> dict[str, Any]:
    """Plan offer/holdout assignments over a TRUSTED owner-resolved cohort.

    Critically, a verified *subset* may be reviewed without falsely claiming
    the entire TAM is complete. This does not publish a send list, email, or
    contact identifier and does not grant delivery authority.
    """
    if (type(lookup_keys) not in (list, tuple)
            or not 1 <= len(lookup_keys) <= _WAVE_LIMIT
            or not callable(trusted_resolver)
            or type(tenant_ref) is not str or not _TENANT_REF.fullmatch(tenant_ref)
            or market_scope not in _MARKET_SCOPES
            or not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("trusted bounded cohort required")
    counts = {
        "source_contacts_checked": 0, "eligible_for_review": 0,
        "held_for_review": 0, "duplicate_lookup_keys_skipped": 0,
        "no_marketing_holdout": 0,
        "buyer_inventory_fit_offer": 0,
        "revenue_leak_signal_offer": 0,
        "verified_market_opportunity_brief": 0,
    }
    holds: dict[str, int] = {}
    seen = set()
    by_company: dict[str, str] = {}
    # Sort by opaque lookup key for repeatable one-contact-per-company choice.
    # A future canonical buyer-role ranker must be applied by the CRM owner.
    for key in sorted(lookup_keys):
        if type(key) is not str or not _LOOKUP_KEY.fullmatch(key) or key == "0" * 32:
            raise ValueError("nonidentifying lookup key required")
        if key in seen:
            counts["duplicate_lookup_keys_skipped"] += 1
            continue
        seen.add(key)
        counts["source_contacts_checked"] += 1
        try:
            row = trusted_resolver(key)
        except Exception:
            # Never leak a private CRM error, address or internal DSN.
            row = None
        reason = None
        if type(row) is not RecipientWaveEvidence:
            reason = "CANONICAL_CRM_RECORD_UNAVAILABLE"
        elif (row.contact_lookup_key != key
              or type(row.company_lookup_key) is not str
              or not _LOOKUP_KEY.fullmatch(row.company_lookup_key)
              or row.company_lookup_key == "0" * 32
              or row.tenant_ref != tenant_ref or row.market_scope != market_scope):
            reason = "TENANT_MARKET_OR_IDENTITY_MISMATCH"
        elif row.source_authority_verified is not True:
            reason = "CANONICAL_SOURCE_AUTHORITY_UNVERIFIED"
        elif (not isinstance(row.last_verified_at, datetime)
              or row.last_verified_at.tzinfo is None
              or now < row.last_verified_at
              or now - row.last_verified_at > timedelta(days=2)):
            reason = "CONTACT_VERIFICATION_STALE"
        elif row.offer_evidence_verified is not True:
            reason = "OFFER_OUTCOME_PROOF_MISSING"
        else:
            try:
                planned = plan_compliant_market_touch(
                    contact_lookup_key=row.company_lookup_key,
                    market_scope_verified=True,
                    lawful_outreach_verified=row.channel_lawfulness_verified,
                    suppressed=(row.suppression_clear is not True),
                    sending_domain_approved=row.sending_domain_approved,
                    last_touch_verified=row.contact_history_verified,
                    last_touch_at=row.last_marketing_touch_at,
                    now=now,
                )
            except ValueError:
                planned = {"status": "HOLD", "blockers": ["CONTACT_HISTORY_INVALID"]}
            if planned["status"] == "HOLD":
                reason = planned["blockers"][0]
            else:
                arm = planned["planned_arm"]
                prior = by_company.get(row.company_lookup_key)
                if prior is not None:
                    if arm != prior:
                        # Should be impossible with deterministic assignment.
                        raise ValueError("company experiment arm collision")
                    reason = "SECOND_CONTACT_SAME_COMPANY_WAVE"
                else:
                    by_company[row.company_lookup_key] = arm
                    counts["eligible_for_review"] += 1
                    counts[arm] += 1
        if reason:
            counts["held_for_review"] += 1
            holds[reason] = holds.get(reason, 0) + 1

    return {
        "schema_version": "empire.gtm.canonical_cohort_wave_review.v1",
        "status": "OFFLINE_SEGMENTED_WAVE_PLAN_NOT_SENT",
        "market_scope": market_scope,
        "counts": counts,
        "hold_reasons": dict(sorted(holds.items())),
        "verified_entire_tam": False,
        "contact_identities_or_emails_exposed": 0,
        "recipient_list_exported": False,
        "auto_email_sending_enabled": False,
        "retargeting_audience_exported": False,
        "source_owner_execution_approval_granted": False,
        "execution_authority": "NONE",
    }



_OFFER_DRAFTS = {
    "buyer_inventory_fit_offer": (
        "A quick buyer-fit check",
        "Would it help to check whether the lead types and territories you buy fit what "
        "Empire AI can verify as available? We would review supply evidence, buyer "
        "criteria and acceptance rules before suggesting anything, and say clearly "
        "if there isn't a match. Would a short buyer-fit check be useful?",
        "Would a short buyer-fit check be useful?",
    ),
    "revenue_leak_signal_offer": (
        "Local demand evidence",
        "When enquiries are lost between demand and response, it can be hard to "
        "tell which gaps matter. A territory-level evidence check could help "
        "separate measured opportunity from assumptions, including where our "
        "information is incomplete. We can outline the verified sources and "
        "open questions. Would a short evidence snapshot help?",
        "Would a short evidence snapshot help?",
    ),
    "verified_market_opportunity_brief": (
        "Choosing your next market",
        "If you're deciding which territories to pursue, comparing independently "
        "sourced market signals could help before committing budget. We can "
        "prepare a short brief showing observations, limits and the questions "
        "still unresolved. The result would be a starting point, not a promise "
        "of leads or returns. Would a one-page outline be useful?",
        "Would a one-page outline be useful?",
    ),
}


def review_three_offer_creatives(
    *, market_scope: str, verified_offer_evidence_refs: tuple[str, ...] = (),
    live_offer_and_landing_verified: bool = False,
) -> dict[str, Any]:
    """Draft real three-angle campaign copy using the EXISTING copy reviewer.

    Evidence-ref strings are *references*, not independent attestation, and
    therefore do not make campaigns send-ready.
    """
    if market_scope not in _MARKET_SCOPES:
        raise ValueError("approved video-pilot market required")
    if type(verified_offer_evidence_refs) is not tuple or len(verified_offer_evidence_refs) > 10:
        raise ValueError("bounded proof reference list required")
    if any(type(ref) is not str or len(ref) > 100 or not re.fullmatch(
        r"[a-zA-Z0-9_./:-]{8,100}", ref
    ) for ref in verified_offer_evidence_refs):
        raise ValueError("invalid proof reference")
    from empire_os.outreach_message_optimizer import review_message
    drafts = []
    for arm, (subject, body, cta) in _OFFER_DRAFTS.items():
        quality = review_message(subject=subject, body=body, cta=cta)
        if quality["human_copy_gate"]["eligible"] is not True:
            raise ValueError("offer copy failed existing human copy gate")
        drafts.append({
            "arm": arm, "subject": subject, "body": body, "cta": cta,
            "existing_copy_quality_score": quality["structural_score"],
            "existing_copy_hard_gate_passed": True,
            "experiment_eligible": False,
            "send_authorized": False,
        })
    return {
        "schema_version": "empire.gtm.three_outcome_offer_drafts.v1",
        "market_scope": market_scope,
        "drafts": drafts,
        "offer_evidence_references_supplied": len(verified_offer_evidence_refs),
        "offer_and_landing_owner_attested": live_offer_and_landing_verified is True,
        "offer_truth_independently_verified": False,
        "production_sender_and_recipients_verified": False,
        "copy_sent": False,
        "authority": "DRAFT_ONLY",
    }


BUYER_SOURCE_PATHS = {
    "buyer_qualification": (
        "runtime/buyer_network_intelligence/founder_qualification_actions_latest.json",
        "empire.buyer_qualification_actions.v1",
    ),
    "relationships": (
        "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json",
        "empire.commercial_relationship_registry.v1",
    ),
}


def read_existing_buyer_sources(root: Path) -> dict[str, dict[str, Any]]:
    """Existing root-private buyer data. Never echo or export any contact row."""
    found: dict[str, dict[str, Any]] = {}
    for key, (rel, _) in BUYER_SOURCE_PATHS.items():
        path = root / rel
        try:
            mode = path.stat().st_mode
            if (path.is_symlink() or not path.is_file()
                    or mode & 0o077 or path.stat().st_size > 2_500_000):
                raise ValueError("unapproved private source")
            data = json.loads(path.read_text(encoding="utf-8"))
            found[key] = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            found[key] = {}
    return found


def review_current_buyer_contactability(
    snapshots: Mapping[str, Any] | None, *, now: datetime,
) -> dict[str, Any]:
    """Source-bound real eligibility census; does not make contacts sendable.

    Buyer evidence is an *independent* owner surface from the old TAM
    research snapshot. A research target or prior Gmail thread never
    supplies consent, deliverability, current suppression or send authority.
    """
    now = now.astimezone(timezone.utc)
    data = snapshots or {}
    qualification = data.get("buyer_qualification", {})
    relationships = data.get("relationships", {})
    q_valid = (
        isinstance(qualification, Mapping)
        and qualification.get("schema_version") == BUYER_SOURCE_PATHS["buyer_qualification"][1]
        and qualification.get("mode") == "OBSERVE"
        and qualification.get("execution_authority") in ("none", "NONE")
        and qualification.get("outbound_enabled") is False
        and qualification.get("outbound_sent") is False
        and _fresh(qualification.get("generated_at"), now)
        and isinstance(qualification.get("targets"), list)
        and len(qualification["targets"]) <= 500
    )
    r_valid = (
        isinstance(relationships, Mapping)
        and relationships.get("schema_version") == BUYER_SOURCE_PATHS["relationships"][1]
        and relationships.get("mode") == "OBSERVE"
        and relationships.get("execution_authority") in ("none", "NONE")
        and relationships.get("outbound_authorized") is False
        and relationships.get("outbound_sent") is False
        and _fresh(relationships.get("generated_at"), now)
        and isinstance(relationships.get("relationships"), list)
        and len(relationships["relationships"]) <= 10_000
    )
    result = {
        "source_status": "VERIFIED_READONLY_BUYER_SNAPSHOTS" if q_valid and r_valid
                         else "HOLD_BUYER_SOURCE_MISSING_STALE_OR_INCOMPATIBLE",
        "shortlisted_buyer_targets": None,
        "research_target_sectors": None,
        "research_geography_and_live_buying_role_verified": False,
        "reviewed_relationships": None,
        "buyer_contact_verified_count": None,
        "qualifying_contacts_for_wave": None,
        "permitted_email_recipients": None,
        "existing_auto_send_authority": False,
        "private_contacts_exposed": 0,
        "outbound_enabled_by_review": False,
    }
    if not q_valid or not r_valid:
        return result
    targets = qualification["targets"]
    rows = relationships["relationships"]
    if (not all(isinstance(row, Mapping) for row in targets)
            or not all(isinstance(row, Mapping) for row in rows)
            or _count(qualification.get("contact_verified_for_outbound_count")) is None):
        result["source_status"] = "HOLD_BUYER_RECORD_COUNTS_INVALID"
        return result
    # Numbers describe exactly what these sources know, not the market's
    # total addressable population or an independently authenticated send list.
    result["shortlisted_buyer_targets"] = len(targets)
    # Research classification only: this never establishes contactability,
    # geography, an accepting buyer or market size. The same target can
    # appear in multiple sectors, so totals intentionally may overlap.
    result["research_target_sectors"] = {
        sector: sum(
            isinstance(row.get("verticals"), list)
            and sector in row["verticals"]
            for row in targets
        )
        for sector in ("roofing", "solar", "hvac")
    }
    result["reviewed_relationships"] = len(rows)
    result["buyer_contact_verified_count"] = qualification[
        "contact_verified_for_outbound_count"
    ]
    # Two independent snapshots are not joined by email/company strings.
    # A recipient-level authoritative CRM join is required for send readiness.
    result["qualifying_contacts_for_wave"] = None
    result["permitted_email_recipients"] = None
    result["existing_auto_send_authority"] = (
        False if all(row.get("auto_send_authorized") is not True for row in rows)
        else None
    )
    return result



def review_authenticated_campaign_intelligence(
    *, now: datetime,
    account_packets: Iterable[tuple[Any, Iterable[Any]]] | None = None,
    experiment_arms: Iterable[Any] | None = None,
    funnel_stage_receipts: Iterable[Any] | None = None,
    account_route_packets: Iterable[tuple[Any, Iterable[Any]]] | None = None,
    learning_waves: Iterable[Any] | None = None,
    adaptive_journey_packets: Iterable[tuple[Any, Iterable[Any]]] | None = None,
    observer_snapshots: Mapping[str, Any] | None = None,
    authenticated_crm_owner_read: Any | None = None,
    account_projection_owner: Callable | None = None,
    signal_owner: Callable | None = None,
    value_case_owner: Callable | None = None,
    value_case_packets: Iterable[tuple[Any, Iterable[Any]]] | None = None,
    released_research_route: Mapping[str, Any] | None = None,
    released_research_repository_root: Path | None = None,
    source_enquiry_receipts: Iterable[Any] | None = None,
    source_crm_enquiry_links: Iterable[Any] | None = None,
    source_finance_outcome_receipts: Iterable[Any] | None = None,
    finance_outcome_window_complete: bool = False,
) -> dict[str, Any]:
    """One entry point for the existing CRM, Analytics and Finance owners.

    Sources are explicit. No optional real source silently becomes a zero
    count or a fake example. Owner-provided evidence is never sent or stored.
    """
    from empire_os.campaign_intelligence import (
        review_private_account_portfolio,
        evaluate_real_customer_experiment,
        diagnose_campaign_conversion_bottlenecks,
        review_account_route_portfolio,
        review_multiwave_commercial_learning,
        review_adaptive_buyer_journey_portfolio,
        review_authenticated_crm_campaign_handoff,
        review_buyer_value_first_portfolio,
        reconcile_first_party_conversion_journey,
    )
    if (authenticated_crm_owner_read is None
            and (account_projection_owner is not None or signal_owner is not None
                 or value_case_owner is not None)):
        raise ValueError("cannot enable CRM callbacks without authenticated tenant owner")
    # A single authenticated generator must feed both experiment and journey
    # review without the latter silently receiving an exhausted iterator.
    verified_waves = tuple(learning_waves) if learning_waves is not None else None
    return {
        "schema_version": "empire.gtm.full_funnel_decision_intelligence.v1",
        "source_status": (
            "EXISTING_OWNERS_MUST_SUPPLY_AUTHENTICATED_RECEIPT_ADAPTERS"
            if account_packets is None or experiment_arms is None
            or funnel_stage_receipts is None
            else "REVIEWED_OWNER_SUPPLIED_OFFLINE_EVIDENCE"
        ),
        "account_intelligence": (
            review_private_account_portfolio(account_packets, now=now)
            if account_packets is not None else None
        ),
        "verified_customer_experiment": (
            evaluate_real_customer_experiment(experiment_arms)
            if experiment_arms is not None else None
        ),
        "conversion_bottleneck_review": (
            diagnose_campaign_conversion_bottlenecks(funnel_stage_receipts)
            if funnel_stage_receipts is not None else None
        ),
        "account_buying_committee_routes": (
            review_account_route_portfolio(account_route_packets, now=now)
            if account_route_packets is not None else None
        ),
        "multiwave_campaign_learning": (
            review_multiwave_commercial_learning(verified_waves, now=now)
            if learning_waves is not None else None
        ),
        "adaptive_buyer_journeys": (
            review_adaptive_buyer_journey_portfolio(
                adaptive_journey_packets, now=now, learning_waves=verified_waves,
            ) if adaptive_journey_packets is not None else None
        ),
        "real_existing_source_connections": (
            review_real_commercial_observers(observer_snapshots, now=now)
            if observer_snapshots is not None else None
        ),
        "authenticated_tenant_crm_handoff": (
            review_authenticated_crm_campaign_handoff(
                authenticated_crm_owner_read,
                account_projection_owner=account_projection_owner,
                signal_owner=signal_owner,
                value_case_owner=value_case_owner,
                now=now,
            ) if authenticated_crm_owner_read is not None else None
        ),
        "buyer_value_first_offer_review": (
            review_buyer_value_first_portfolio(value_case_packets, now=now)
            if value_case_packets is not None else None
        ),
        "real_first_party_conversion_journey": (
            reconcile_first_party_conversion_journey(
                root=released_research_repository_root,
                released_route=released_research_route,
                enquiries=source_enquiry_receipts,
                crm_links=source_crm_enquiry_links,
                commercial_outcomes=source_finance_outcome_receipts,
                finance_window_complete=finance_outcome_window_complete,
                now=now,
            ) if released_research_route is not None else None
        ),
        "live_recipient_contact_or_messages": False,
        "production_training_or_model_mutation": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }


def recommend_next_real_execution_focus(review: Mapping[str, Any]) -> dict[str, Any]:
    """Prioritise first real customer pipeline bottleneck, not new scaffolding."""
    buyer = review.get("real_buyer_contactability") or {}
    campaigns = review.get("campaign_assets") or {}
    feedback = review.get("verified_commercial_feedback") or {}
    if buyer.get("source_status") != "VERIFIED_READONLY_BUYER_SNAPSHOTS":
        action = "RESTORE_PRIVATE_CANONICAL_BUYER_READ"
    elif buyer.get("buyer_contact_verified_count") == 0:
        action = "VERIFY_REAL_FIRST_WAVE_BUYER_CONTACTS_WITH_EXISTING_SALES_OWNER"
    elif buyer.get("permitted_email_recipients") is None:
        action = "PROVE_PERMISSIONED_SENDABLE_RECIPIENTS_WITH_EXISTING_SALES_OWNER"
    elif campaigns.get("deployed_assets_correlated_to_runtime") is None:
        action = "REPAIR_EXISTING_CAMPAIGN_OFFER_AND_LANDING_PROOF"
    elif review.get("first_market_wave_delivered_verified") is not True:
        action = "RUN_ONE_GOVERNED_MARKET_WAVE_USING_EXISTING_OUTREACH_OWNER"
    elif feedback.get("outcome_linkage_verified") is not True:
        action = "CONNECT_REAL_CAMPAIGN_AND_CUSTOMER_OUTCOME_RECEIPTS"
    else:
        action = "REVIEW_REAL_CUSTOMER_OFFER_EXPERIMENT_BEFORE_SCALING"
    return {
        "priority": action,
        "inferred_buyer_intent": False,
        "auto_send_authorized": False,
        "source_owner_mutation_granted": False,
        "execution_authority": "NONE",
    }



# Cross-owner, read-only evidence joins. Every input is an existing EmpireOS
# observer snapshot, not a direct CRM/ledger query or a new runtime producer.
# Do NOT join customers by name, domain, mailbox or public prospect strings.
REAL_OBSERVER_SOURCES = {
    "next_best": (
        "runtime/next_best_action/next_best_action_latest.json",
        "empire.next_best_action_snapshot.v1",
    ),
    "account_twin": (
        "runtime/account_twin/account_twin_latest.json",
        "empire.account_buyer_digital_twin_snapshot.v1",
    ),
    "consent_outcome": (
        "runtime/consent_suppression/outcome_linkage_latest.json",
        "empire-consent-outcome-linkage-v1",
    ),
    "campaign_output": (
        "runtime/campaigns_control/campaign_output_outcome_latest.json",
        "empire-campaign-output-outcome-v1",
    ),
    "campaign_measured": SOURCES["outcomes"],
    "order_payment": (
        "runtime/orders_payments_revenue_control/"
        "orders_payments_revenue_runtime_latest.json",
        "empire-orders-payments-revenue-runtime-control-v1",
    ),
}
REAL_OBSERVER_MAX_BYTES = 512 * 1024
NEXT_BEST_OPERATOR_PLAYS = (
    "verify_decision_maker", "research_more", "prepare_buyer_review",
    "conversation_follow_up", "terms_candidate", "payment_review",
    "fulfilment_review", "hold",
)


def read_real_commercial_observers(root: Path) -> dict[str, Mapping[str, Any]]:
    """Read ONLY fixed first-party observer snapshots, no PII returned by review.

    Neither this reader nor its reviewer connects directly to the tenant CRM,
    financial ledger or delivery endpoints. A file may be a valid observer
    while stale, and that will be disclosed rather than silently repaired.
    """
    root = Path(root).resolve()
    out: dict[str, Mapping[str, Any]] = {}
    for name, (relative_path, _) in REAL_OBSERVER_SOURCES.items():
        path = root / relative_path
        try:
            stat = path.lstat()
            if (not path.is_file() or path.is_symlink()
                    or stat.st_size > REAL_OBSERVER_MAX_BYTES
                    or stat.st_size <= 0 or (stat.st_mode & 0o002)):
                raise ValueError("untrusted or oversized observer file")
            raw = json.loads(path.read_text(encoding="utf-8"))
            out[name] = raw if isinstance(raw, dict) else {}
        except (OSError, ValueError, UnicodeError):
            out[name] = {}
    return out


def _valid_observer_source(
    payload: Mapping[str, Any], name: str, now: datetime,
) -> bool:
    return (
        isinstance(payload, Mapping)
        and payload.get("schema_version") == REAL_OBSERVER_SOURCES[name][1]
        and payload.get("mode") == "OBSERVE"
        and _fresh(payload.get("generated_at"), now)
    )


def review_real_commercial_observers(
    snapshots: Mapping[str, Any], *, now: datetime,
) -> dict[str, Any]:
    """Reconcile live, independent OBSERVE signals without fabricating buyers.

    8 global linked outbound-intent records are NOT 8 converted customers.
    5 campaign output-quality proofs are NOT 5 profitable campaigns.
    Unknown per-contact permissions, settlement and seller acceptance remain
    unknown until independently authenticated owners supply source receipts.
    """
    if not isinstance(snapshots, Mapping) or now.tzinfo is None:
        raise ValueError("current source map and aware clock required")
    now = now.astimezone(timezone.utc)
    raw = {
        name: snapshots.get(name, {}) for name in REAL_OBSERVER_SOURCES
    }
    state = {
        name: (
            "VERIFIED_CURRENT_OBSERVER" if _valid_observer_source(raw[name], name, now)
            else "HOLD_STALE_MISSING_OR_INCOMPATIBLE_SOURCE"
        )
        for name in REAL_OBSERVER_SOURCES
    }
    data = {
        name: raw[name] if state[name] == "VERIFIED_CURRENT_OBSERVER" else {}
        for name in REAL_OBSERVER_SOURCES
    }
    holds: set[str] = set()
    eligible_operator_plays: dict[str, int] | None = None
    reviewed_accounts: int | None = None
    nba = data["next_best"]
    if nba:
        actions = nba.get("actions")
        if (nba.get("execution_authority") == "none"
                and nba.get("outreach_authorized") is False
                and nba.get("payment_authorized") is False
                and nba.get("buyer_intent_inferred") is False
                and nba.get("commercial_intent_inferred") is False
                and isinstance(actions, list)
                and 0 <= len(actions) <= 500
                and nba.get("action_count") == len(actions)
                and all(
                    isinstance(item, Mapping)
                    and item.get("recommendation_only") is True
                    and item.get("execution_authority") == "none"
                    and item.get("mutation_authorized") is False
                    and item.get("external_execution_authorized") is False
                    and item.get("outreach_authorized") is False
                    and item.get("payment_authorized") is False
                    and item.get("buyer_intent_inferred") is False
                    and item.get("commercial_intent_inferred") is False
                    for item in actions
                )):
            from collections import Counter
            counted = Counter(
                item.get("recommended_action")
                if item.get("recommended_action") in NEXT_BEST_OPERATOR_PLAYS
                else "other_existing_action"
                for item in actions
            )
            eligible_operator_plays = dict(sorted(counted.items()))
            reviewed_accounts = len(actions)
        else:
            state["next_best"] = "HOLD_RECOMMENDATION_SOURCE_GOVERNANCE"
            holds.add("NEXT_BEST_PROVENANCE_INVALID")
    # The Digital Twin is NOT an independent revenue source. Its projection
    # can be used for freshness/coverage diagnostics but not for recognizing
    # payments, authorizing a marketing touch or creating a buyer.
    twin = data["account_twin"]
    twin_count: int | None = None
    if twin:
        twins = twin.get("twins")
        if (twin.get("execution_authority") == "none"
                and twin.get("buyer_intent_inferred") is False
                and twin.get("commercial_intent_inferred") is False
                and twin.get("outreach_authorized") is False
                and twin.get("payment_authorized") is False
                and isinstance(twins, list)
                and twin.get("twin_count") == len(twins)
                and len(twins) <= 500):
            twin_count = len(twins)
        else:
            state["account_twin"] = "HOLD_DIGITAL_TWIN_GOVERNANCE"
            holds.add("DIGITAL_TWIN_GOVERNANCE_INVALID")
    global_links = data["consent_outcome"]
    linked_events = None
    if global_links:
        governance = global_links.get("governance")
        linked = global_links.get("linked_outcomes")
        if (isinstance(governance, Mapping)
                and governance.get("db_write") is False
                and governance.get("outbound") is False
                and governance.get("funds") is False
                and isinstance(linked, list)
                and len(linked) <= 10000
                and global_links.get("linked_outcome_count") == len(linked)
                and all(isinstance(row, Mapping) for row in linked)):
            linked_events = len(linked)
        else:
            holds.add("GLOBAL_OUTCOME_LINKAGE_UNVERIFIED")
            state["consent_outcome"] = "HOLD_CONSENT_OUTCOME_GOVERNANCE"
    campaign_output = data["campaign_output"]
    campaign_measured = data["campaign_measured"]
    output_quality_campaign_count = None
    exact_campaign_matches = None
    output_linkages = None
    if campaign_output:
        if (campaign_output.get("db_write") is False
                and campaign_output.get("outbound") is False
                and campaign_output.get("campaign_state_mutated") is False
                and campaign_output.get("action_authority_granted") is False
                and _count(campaign_output.get("output_quality_campaign_count")) is not None
                and _count(campaign_output.get("outcome_linkage_campaign_count")) is not None
                and type(campaign_output.get("outcome_linkage_proved")) is bool):
            output_quality_campaign_count = campaign_output["output_quality_campaign_count"]
            output_linkages = campaign_output["outcome_linkage_campaign_count"]
        else:
            state["campaign_output"] = "HOLD_CAMPAIGN_OUTPUT_GOVERNANCE"
            holds.add("CAMPAIGN_OUTPUT_GOVERNANCE_INVALID")
    if campaign_measured:
        governance = campaign_measured.get("governance")
        if (isinstance(governance, Mapping)
                and governance.get("db_write") is False
                and governance.get("outbound") is False
                and _count(campaign_measured.get("exact_outcome_match_count")) is not None
                and type(campaign_measured.get("outcome_linkage_proved")) is bool):
            exact_campaign_matches = campaign_measured["exact_outcome_match_count"]
        else:
            state["campaign_measured"] = "HOLD_CAMPAIGN_OUTCOME_GOVERNANCE"
            holds.add("CAMPAIGN_OUTCOME_GOVERNANCE_INVALID")
    if exact_campaign_matches is not None and output_linkages is not None:
        if exact_campaign_matches != output_linkages:
            holds.add("INDEPENDENT_CAMPAIGN_OUTCOME_COUNTERS_DISAGREE")
            exact_campaign_matches = None
        elif (bool(exact_campaign_matches)
              != (campaign_output.get("outcome_linkage_proved") is True)
              or bool(exact_campaign_matches)
              != (campaign_measured.get("outcome_linkage_proved") is True)):
            holds.add("INDEPENDENT_CAMPAIGN_LINKAGE_PROOF_MISMATCH")
            exact_campaign_matches = None
    payments = data["order_payment"]
    payment_population_count = None
    observed_payment = None
    if payments:
        governance = payments.get("governance")
        semantics = payments.get("semantic_truth")
        if (isinstance(governance, Mapping)
                and governance.get("db_write") is False
                and governance.get("funds_movement") is False
                and governance.get("payment_write") is False
                and isinstance(semantics, Mapping)
                and type(semantics.get("real_payment_observed")) is bool
                and _count(payments.get("current_transaction_row_count")) is not None):
            payment_population_count = payments["current_transaction_row_count"]
            observed_payment = semantics["real_payment_observed"]
        else:
            state["order_payment"] = "HOLD_ORDER_PAYMENT_GOVERNANCE"
            holds.add("PAYMENT_CONTROL_SOURCE_INVALID")
    for name, status in state.items():
        if status != "VERIFIED_CURRENT_OBSERVER":
            holds.add("SOURCE_NOT_READY:" + name)
    return {
        "schema_version": "empire.gtm.live_commercial_observer_join.v1",
        "source_health": state,
        "integrated_current_observer_sources": sum(
            v == "VERIFIED_CURRENT_OBSERVER" for v in state.values()
        ),
        "total_observer_sources": len(REAL_OBSERVER_SOURCES),
        "existing_next_best_actions_reviewed": reviewed_accounts,
        "next_best_internal_play_counts": eligible_operator_plays,
        "fresh_account_twin_count": twin_count,
        "global_linked_event_records_not_sales": linked_events,
        "verified_campaign_output_quality_count": output_quality_campaign_count,
        "exact_campaign_outcome_linkage_count": exact_campaign_matches,
        "controlled_payment_source_row_count": payment_population_count,
        "payment_observed_within_checked_population": observed_payment,
        "campaign_verified_paying_customers": None,
        "recognized_campaign_revenue_cents": None,
        "margin_realized_cents": None,
        "source_holds": sorted(holds),
        "canonical_crm_contact_join_established": False,
        "outbound_execution_eligible_from_observers": False,
        "production_actions_executed": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }


def review_existing_research_release_entrypoints(root: Path) -> dict[str, Any]:
    """Existing, independently owned first-party site release: READ ONLY.

    This verifies immutable release metadata only. It does not check HTTP,
    inspect submitted contacts, claim that new value previews are published,
    or grant permission to post enquiries.
    """
    from empire_os.owned_campaign_release import load_release
    from empire_os.campaign_intelligence import review_released_research_route

    released = load_release(root=root)
    if released is None:
        return {
            "schema_version": "empire.gtm.existing_research_release_inventory.v1",
            "release_status": "HOLD_NO_VERIFIED_SIGNED_RELEASE",
            "verified_research_pages": None,
            "published_private_value_experiences": None,
            "real_enquiries_observed": None,
            "real_payments_observed": None,
            "source_owner": "existing_owned_campaign_website",
            "execution_authority": "NONE",
        }
    campaigns = released.get("campaigns", ())
    paths = [
        review_released_research_route(
            root=root, campaign_id=item["campaign_id"],
            now=datetime.now(timezone.utc),
        )
        for item in campaigns
    ]
    if not paths or any(
        value["status"] != "EXISTING_RELEASE_VERIFIED_RESEARCH_ROUTE"
        for value in paths
    ):
        raise ValueError("signed first-party release inconsistent with research router")
    return {
        "schema_version": "empire.gtm.existing_research_release_inventory.v1",
        "release_status": "EXISTING_RELEASED_RESEARCH_PATHS_VERIFIED",
        "verified_research_pages": len(paths),
        "existing_enquiry_route": "/api/research/enquiry",
        "published_private_value_experiences": 0,
        "real_enquiries_observed": None,
        "real_payments_observed": None,
        "actual_http_verified_in_this_report": False,
        "source_owner": "existing_owned_campaign_website",
        "execution_authority": "NONE",
    }


# Reuse the independent catalog, SEO and conversion owner interfaces.
# Never take direct privileged DB reads, create another analytics event table
# or infer paying buyers from browser submissions.
def read_existing_commercial_catalog_readonly(root: Path) -> dict[str, Any]:
    path = root / "runtime/commercial_catalog/latest.json"
    try:
        info = path.lstat()
        if (path.is_symlink() or not path.is_file() or not 0 < info.st_size <= 1_000_000
                or info.st_mode & 0o002):
            return {}
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def review_commercial_catalog_for_conversion(
    source: Mapping[str, Any] | None, *, now: datetime,
) -> dict[str, Any]:
    from empire_os.commercial_offer_book import product_ready

    base = {
        "schema_version": "empire.gtm.catalog_offer_conversion_readiness.v1",
        "source_status": "HOLD_MISSING_STALE_OR_UNTRUSTED_CATALOG",
        "products_catalogued": None,
        "active_products": None,
        "verified_commercial_terms_products": None,
        "buyer_specific_value_offer_match_verified": False,
        "delivery_capacity_or_start_date_verified": False,
        "pricing_or_terms_published_by_campaign_owner": False,
        "payment_or_revenue_inferred": False,
        "execution_authority": "NONE",
    }
    if not isinstance(source, Mapping):
        return base
    try:
        issued = datetime.fromisoformat(source["generated_at"].replace("Z", "+00:00"))
        if issued.tzinfo is None or issued > now or now - issued > timedelta(hours=36):
            return base
        if (source.get("schema_version") != "empire.commercial-product-catalog.v1"
                or source.get("execution_authority") != "none"
                or source.get("actual_revenue") is not False):
            return base
        rows = source.get("products")
        if (not isinstance(rows, list) or len(rows) > 500
                or any(not isinstance(row, Mapping) for row in rows)
                or source.get("product_count") != len(rows)):
            return base
        active = sum(row.get("active") is True for row in rows)
        ready = sum(product_ready(row) for row in rows)
        if (type(source.get("active_count")) is not int
                or type(source.get("binding_terms_ready_count")) is not int
                or source["active_count"] != active
                or source["binding_terms_ready_count"] != ready):
            return base
    except (ValueError, TypeError, AttributeError, KeyError):
        return base
    return {
        **base,
        "source_status": "CURRENT_CATALOG_PRODUCT_TERMS_REVIEWED",
        "products_catalogued": len(rows),
        "active_products": active,
        "verified_commercial_terms_products": ready,
    }


def review_existing_enquiry_aggregate_for_conversion(
    aggregate: Mapping[str, Any] | None, *,
    owner_operator_attestation_verified: bool,
    source_observed_at: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Interpret the *existing* privileged count-only SEO probe output.

    The observer cannot be invoked by this campaign owner and this function
    intentionally does not execute SQL. Count fields never establish
    unique visitors, a person identity, CRM admission, consent or a sale.
    """
    from scripts.probe_owned_research_enquiry_aggregate_readonly import SCHEMA, FIELDS
    result = {
        "schema_version": "empire.gtm.research_aggregate_conversion_readiness.v1",
        "source_status": "AWAIT_AUTHORIZED_DATABASE_OPERATOR",
        "accepted_research_enquiries": None,
        "page_view_events_not_unique_visitors": None,
        "cta_click_events_not_unique_buyers": None,
        "enquiry_started_events": None,
        "real_unique_visitor_to_lead_rate": None,
        "exact_campaign_conversions": None,
        "crm_matched_buyers": None,
        "sales_or_payment_inferred": False,
        "first_party_marketing_permission_inferred": False,
        "execution_authority": "NONE",
    }
    if (owner_operator_attestation_verified is not True or aggregate is None):
        return result
    if (not isinstance(source_observed_at, datetime)
            or not isinstance(now, datetime)
            or source_observed_at.tzinfo is None or now.tzinfo is None
            or source_observed_at > now
            or now - source_observed_at > timedelta(hours=24)):
        return {**result, "source_status": "HOLD_UNVERIFIED_OR_STALE_AGGREGATE_CAPTURE"}
    if (not isinstance(aggregate, Mapping)
            or aggregate.get("schema_version") != SCHEMA
            or aggregate.get("source") != "CANONICAL_EMPIREDB"
            or aggregate.get("mode") != "OBSERVE"
            or aggregate.get("read_only") is not True
            or aggregate.get("status") not in (
                "NO_RESEARCH_ENQUIRIES_IN_CANONICAL_SOURCE",
                "RESEARCH_ENQUIRIES_OBSERVED_SEPARATE_FROM_SALES",
            )
            or aggregate.get("aggregate_event_consistency_verified") is not True
            or aggregate.get("lead_transfer_enabled") is not False
            or aggregate.get("outbound_sent") is not False
            or aggregate.get("database_writes") is not False
            or aggregate.get("new_privileges_granted") is not False
            or aggregate.get("payment_executed") is not False
            or aggregate.get("customer_identifiers_disclosed") is not False
            or aggregate.get("contact_data_disclosed") is not False
            or aggregate.get("raw_customer_rows_read_by_operator") is not False
            or aggregate.get("individual_enquiry_text_disclosed") is not False
            or aggregate.get("commercial_sales_status_inferred") is not False
            or aggregate.get("execution_authority") != "NONE"):
        return {**result, "source_status": "HOLD_UNTRUSTED_AGGREGATE_EVIDENCE"}
    fields = {name: aggregate.get(name) for name in FIELDS}
    if (any(type(n) is not int or not 0 <= n <= 1_000_000_000
            for n in fields.values())
            or fields["research_campaigns_with_enquiries"] > fields["research_enquiry_rows"]
            or fields["server_received_submission_events"] != fields["research_enquiry_rows"]
            or fields["invalid_submission_events"] != 0
            or fields["enquiry_marketing_or_outbound_hold_violations"] != 0
            or (aggregate.get("status") == "NO_RESEARCH_ENQUIRIES_IN_CANONICAL_SOURCE")
               != (fields["research_enquiry_rows"] == 0)):
        return {**result, "source_status": "HOLD_UNTRUSTED_AGGREGATE_EVIDENCE"}
    return {
        **result,
        "source_status": "AUTHORIZED_AGGREGATE_RESEARCH_EVIDENCE_REVIEWED",
        "accepted_research_enquiries": fields["research_enquiry_rows"],
        "page_view_events_not_unique_visitors": fields["browser_page_view_events"],
        "cta_click_events_not_unique_buyers": fields["browser_cta_click_events"],
        "enquiry_started_events": fields["browser_enquiry_started_events"],
    }


def review_conversion_owner_release_board(
    *,
    release: Mapping[str, Any],
    catalog: Mapping[str, Any],
    research_aggregate: Mapping[str, Any],
    customer_money_join: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Small factual owner/action ledger, never autonomous task assignment."""
    release_ok = release.get("release_status") == "EXISTING_RELEASED_RESEARCH_PATHS_VERIFIED"
    catalog_ok = catalog.get("source_status") == "CURRENT_CATALOG_PRODUCT_TERMS_REVIEWED"
    enquiries_ready = research_aggregate.get("source_status") == "AUTHORIZED_AGGREGATE_RESEARCH_EVIDENCE_REVIEWED"
    money_ready = (isinstance(customer_money_join, Mapping)
                   and customer_money_join.get("finance_receipt_window_closed") is True
                   and customer_money_join.get("revenue_attribution_basis")
                   == "EXACT_INTAKE_CRM_ORDER_JOIN_WITH_CLOSED_FINANCE_WINDOW")
    tasks = [
        {
            "owner": "existing_flagship_website_owner",
            "status": "EXISTING_FORM_RELEASE_VERIFIED" if release_ok else "RELEASE_EVIDENCE_REQUIRED",
            "next_action": (
                "REVIEW_SOURCE_BACKED_PROOF_PAGES_AND_PUBLISH_ONLY_WITH_APPROVED_FORMS_AND_CLAIMS"
                if release_ok else "VERIFY_OR_RESTORE_SIGNED_FIRST_PARTY_RESEARCH_RELEASE"
            ),
            "proof_experience_published": False,
        },
        {
            "owner": "existing_commercial_catalog_and_fulfilment_owner",
            "status": "CATALOG_SNAPSHOT_VERIFIED_BUYER_DELIVERY_OPEN" if catalog_ok else "CATALOG_SOURCE_MISSING",
            "next_action": "VERIFY_OFFER_SPECIFIC_TERMS_RISK_AND_FULFILMENT_TIMELINE",
        },
        {
            "owner": "existing_seo_research_enquiry_database_owner",
            "status": "VERIFIED_AGGREGATE_COUNTS" if enquiries_ready else "AUTHORIZED_LOCAL_AGGREGATE_READ_HELD",
            "next_action": (
                "REVIEW_GENUINE_INBOUND_RESEARCH_COUNTS_WITHOUT_PROMOTING_TO_SALES"
                if enquiries_ready else "RUN_EXISTING_PRIVILEGED_COUNT_ONLY_RESEARCH_PROBE_WHEN_AUTHORIZED"
            ),
        },
        {
            "owner": "existing_tenant_crm_and_sales_owner",
            "status": "EXACT_ENQUIRY_TO_CRM_JOIN_VERIFIED" if (
                isinstance(customer_money_join, Mapping)
                and customer_money_join.get("authenticated_crm_enquiries_linked") is not None
            ) else "AUTHENTICATED_TENANT_CRM_JOIN_NOT_AVAILABLE",
            "next_action": "PROVE_REAL_FIRST_PARTY_ENQUIRY_TO_CANONICAL_TENANT_PROSPECT_JOIN",
        },
        {
            "owner": "existing_finance_and_revenue_owner",
            "status": "CLOSED_CANONICAL_CAMPAIGN_MONEY_WINDOW" if money_ready else "CAMPAIGN_FINANCIAL_EVENT_WINDOW_UNVERIFIED",
            "next_action": "RECONCILE_SETTLEMENT_FULFILMENT_REVENUE_AND_ACTUAL_COSTS_WITHOUT_ESTIMATES",
        },
    ]
    return {
        "schema_version": "empire.gtm.first_party_conversion_owner_board.v1",
        "tasks": tasks,
        "tasks_total": len(tasks),
        "website_source_verified": release_ok,
        "owner_approved_private_value_page_published": False,
        "buyer_specific_offer_terms_and_timing_verified": False,
        "real_enquiry_source_available": enquiries_ready,
        "revenue_and_cost_receipts_joined": money_ready,
        "automated_handoff_performed": False,
        "new_workers_or_duplicate_crm_created": False,
        "production_action_authority": "NONE",
    }


def review_released_product_page_alignment(
    root: Path, *, catalog_source: Mapping[str, Any] | None,
    catalog_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Join EXISTING signed campaign objectives to exact catalog product codes.

    This is an aggregate website-owner readiness check, not an inventory
    projection or permission to market to research-form submitters.
    """
    from empire_os.owned_campaign_release import load_release
    from empire_os.commercial_offer_book import product_ready

    held = {
        "schema_version": "empire.gtm.signed_research_product_alignment.v1",
        "status": "HOLD_UNSIGNED_RELEASE_OR_UNTRUSTED_CATALOG",
        "signed_research_pages": None,
        "research_question_pages_not_commercial_offers": None,
        "product_enquiry_pages": None,
        "product_enquiry_pages_with_exact_catalog_terms": None,
        "product_enquiry_pages_with_unverified_terms": None,
        "buyer_fit_verified": False,
        "offer_delivery_date_verified": False,
        "production_publication_authorized": False,
        "execution_authority": "NONE",
    }
    if (catalog_readiness.get("source_status")
            != "CURRENT_CATALOG_PRODUCT_TERMS_REVIEWED"
            or not isinstance(catalog_source, Mapping)):
        return held
    signed = load_release(root=root)
    if not isinstance(signed, Mapping):
        return held
    pages = signed.get("campaigns")
    products = catalog_source.get("products")
    if (not isinstance(pages, list) or not isinstance(products, list)
            or len(pages) > 100 or len(products) > 500
            or catalog_source.get("product_count") != len(products)
            or catalog_readiness.get("products_catalogued") != len(products)
            or catalog_readiness.get("verified_commercial_terms_products") != sum(
                product_ready(p) for p in products if isinstance(p, Mapping)
            )):
        return held
    code_map: dict[str, list[Mapping[str, Any]]] = {}
    for row in products:
        if not isinstance(row, Mapping):
            return held
        code = row.get("product_code")
        if isinstance(code, str) and code:
            code_map.setdefault(code, []).append(row)
    research_only = 0
    product_enquiry = 0
    linked_ready = 0
    seen_campaigns = set()
    for page in pages:
        if not isinstance(page, Mapping):
            return held
        cid = page.get("campaign_id")
        objective = page.get("campaign_objective")
        if (not isinstance(cid, str) or cid in seen_campaigns
                or page.get("conversion_plan", {}).get("landing_path")
                != "/research/" + cid):
            return held
        seen_campaigns.add(cid)
        if objective == "research_enquiry":
            # Product references are unnecessary and not implied for research.
            research_only += 1
        elif objective == "product_enquiry":
            product_enquiry += 1
            matches = code_map.get(page.get("product_code"), [])
            if len(matches) == 1 and product_ready(matches[0]):
                linked_ready += 1
        else:
            return held
    return {
        **held,
        "status": "EXACT_SIGNED_PAGE_CATALOG_CODE_ALIGNMENT_REVIEWED",
        "signed_research_pages": len(pages),
        "research_question_pages_not_commercial_offers": research_only,
        "product_enquiry_pages": product_enquiry,
        "product_enquiry_pages_with_exact_catalog_terms": linked_ready,
        "product_enquiry_pages_with_unverified_terms":
            product_enquiry - linked_ready,
    }


# These country/niche labels are drawn from the fixed signed website release
# contract. Unknown strings are NOT guessed from titles or marketing copy.
_RELEASE_MARKET_GEO = {
    "denver, co": "US",
    "atlanta": "US",
    "nyc": "US",
    "dallas-fort worth": "US",
}
_RELEASE_NICHE = frozenset({
    "roofing", "hvac", "general_contractor", "class_action_lawyer",
})
_RELEASE_NICHE_ALIASES = {
    "general contractor": "general_contractor",
    "class action lawyer": "class_action_lawyer",
}
_PROOF_OFFER_ARMS = frozenset({
    "buyer_inventory_fit_offer",
    "revenue_leak_signal_offer",
    "verified_market_opportunity_brief",
})
_PROOF_PLACEMENT_RISKS = {
    "NO_SIGNED_DESTINATION_RELEASE": ("critical", "existing_flagship_website_owner"),
    "CAMPAIGN_NOT_IN_SIGNED_RELEASE": ("critical", "existing_flagship_website_owner"),
    "UNKNOWN_SOURCE_MARKET": ("critical", "existing_flagship_website_owner"),
    "COUNTRY_SCOPE_MISMATCH": ("critical", "existing_flagship_website_owner"),
    "SECTOR_SCOPE_MISMATCH": ("critical", "existing_flagship_website_owner"),
    "TERRITORY_SCOPE_UNVERIFIED": ("critical", "existing_flagship_website_owner"),
    "TERRITORY_SCOPE_MISMATCH": ("critical", "existing_flagship_website_owner"),
    "RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH": ("critical", "existing_flagship_website_owner"),
    "RESEARCH_RELEASE_OUTBOUND_POLICY_CHANGED": ("critical", "existing_flagship_website_owner"),
    "CONVERSION_OBJECTIVE_MISMATCH": ("critical", "existing_flagship_website_owner"),
    "RESEARCH_FORM_IS_NOT_PRODUCT_CHECKOUT": ("critical", "existing_flagship_website_owner"),
    "PRODUCT_CODE_MISMATCH": ("critical", "existing_commercial_catalog_and_fulfilment_owner"),
    "CATALOG_TERMS_NOT_CURRENT": ("critical", "existing_commercial_catalog_and_fulfilment_owner"),
    "PRODUCT_TERMS_UNVERIFIED": ("critical", "existing_commercial_catalog_and_fulfilment_owner"),
    "PROOF_CONTENT_NOT_SOURCE_BOUND": ("critical", "existing_flagship_website_owner"),
    "STALE_OR_MISSING_EXACT_CONTENT_SIGNOFF": ("critical", "existing_flagship_website_owner"),
    "UNVERIFIED_PROOF_CLAIMS_APPROVAL": ("critical", "existing_flagship_website_owner"),
    "UNVERIFIED_WEBSITE_APPROVAL": ("critical", "existing_flagship_website_owner"),
    "UNVERIFIED_PRIVACY_REVIEW": ("critical", "existing_flagship_website_owner"),
    "UNVERIFIED_FULFILMENT_APPROVAL": ("critical", "existing_commercial_catalog_and_fulfilment_owner"),
    "UNVERIFIED_SALES_CHANNEL_BASIS": ("critical", "existing_tenant_crm_and_sales_owner"),
    "PAID_MEDIA_OR_AUTOMATED_OUTBOUND_NOT_AUTHORIZED": ("critical", "existing_flagship_website_owner"),
}
_PROOF_PLACEMENT_OWNER_FIELDS = {
    "source_proof_claims_approval": "UNVERIFIED_PROOF_CLAIMS_APPROVAL",
    "website_publication_approval": "UNVERIFIED_WEBSITE_APPROVAL",
    "privacy_form_approval": "UNVERIFIED_PRIVACY_REVIEW",
    "fulfilment_and_delivery_approval": "UNVERIFIED_FULFILMENT_APPROVAL",
}


def review_proposed_proof_placement(
    *,
    root: Path,
    requested_campaign_id: str,
    proposed_market_scope: str,
    proposed_offer_arm: str,
    intended_conversion_objective: str,
    catalog_source: Mapping[str, Any] | None,
    catalog_readiness: Mapping[str, Any],
    proof_preview: Mapping[str, Any] | None = None,
    source_value_case: Any | None = None,
    source_signals: tuple[Any, ...] | None = None,
    now: datetime | None = None,
    proposed_product_code: str | None = None,
    proposed_target_geography: str | None = None,
    target_geography_source_verified: bool = False,
    approvals: Mapping[str, bool] | None = None,
    approval_content_sha256_by_owner: Mapping[str, str] | None = None,
    marketing_or_auto_followup_requested: bool = False,
    paid_media_requested: bool = False,
) -> dict[str, Any]:
    """Fail-closed review before proposing a proof experience for a released page.

    This gate is an existing campaign-owner API for website-owner integration,
    NOT installed into the existing website release writer. The caller must
    authenticate source/approval attestations in the owner's trust boundary.
    The result never authorizes publication, outreach, spending or billing.
    """
    from empire_os.owned_campaign_release import load_release
    from empire_os.owned_campaign_preflight import _landing
    from empire_os.owned_campaign_content import PRIVACY
    from empire_os.commercial_offer_book import product_ready
    from empire_os.campaign_intelligence import _SCOPES, _CAMPAIGN
    if (not isinstance(root, Path)
            or type(requested_campaign_id) is not str
            or not _CAMPAIGN.fullmatch(requested_campaign_id)
            or type(proposed_market_scope) is not str
            or proposed_market_scope not in _SCOPES
            or type(proposed_offer_arm) is not str
            or proposed_offer_arm not in _PROOF_OFFER_ARMS
            or type(intended_conversion_objective) is not str
            or intended_conversion_objective not in (
                "research_enquiry", "product_enquiry"
            )
            or (proposed_product_code is not None
                and (type(proposed_product_code) is not str
                     or len(proposed_product_code) > 90))
            or (proposed_target_geography is not None
                and (type(proposed_target_geography) is not str
                     or len(proposed_target_geography) > 120))
            or type(target_geography_source_verified) is not bool
            or type(marketing_or_auto_followup_requested) is not bool
            or type(paid_media_requested) is not bool):
        raise ValueError("UNTRUSTED_OR_UNSUPPORTED_PROOF_PLACEMENT_INTENT")
    if (approvals is not None
            and (not isinstance(approvals, Mapping)
                 or set(approvals) != set(_PROOF_PLACEMENT_OWNER_FIELDS)
                 or any(type(val) is not bool for val in approvals.values()))):
        raise ValueError("EXACT_TYPED_OWNER_APPROVAL_PROJECTION_REQUIRED")
    if (approval_content_sha256_by_owner is not None
            and (not isinstance(approval_content_sha256_by_owner, Mapping)
                 or set(approval_content_sha256_by_owner)
                 != set(_PROOF_PLACEMENT_OWNER_FIELDS)
                 or any(type(value) is not str or len(value) != 64
                        or any(char not in "0123456789abcdef" for char in value)
                        for value in approval_content_sha256_by_owner.values()))):
        raise ValueError("EXACT_SHA256_OWNER_APPROVAL_PROJECTION_REQUIRED")

    problems: set[str] = set()
    signed = load_release(root=root)
    campaign = None
    if signed is None:
        problems.add("NO_SIGNED_DESTINATION_RELEASE")
    else:
        matches = [
            row for row in signed["campaigns"]
            if row.get("campaign_id") == requested_campaign_id
        ]
        if len(matches) != 1:
            problems.add("CAMPAIGN_NOT_IN_SIGNED_RELEASE")
        else:
            campaign = matches[0]
    if campaign is not None:
        source_country = _RELEASE_MARKET_GEO.get(
            str(campaign.get("geography", "")).lower().strip()
        )
        source_niche = _RELEASE_NICHE_ALIASES.get(
            str(campaign.get("niche", "")).lower().strip(),
            str(campaign.get("niche", "")).lower().strip(),
        )
        if source_country is None or source_niche not in _RELEASE_NICHE:
            problems.add("UNKNOWN_SOURCE_MARKET")
        else:
            country, niche, _ = proposed_market_scope.split(":")
            if source_country != country:
                problems.add("COUNTRY_SCOPE_MISMATCH")
            if source_niche != niche:
                problems.add("SECTOR_SCOPE_MISMATCH")
        # A country+sector match does not establish city/metro fit.
        # Campaign source owner must independently verify the geography
        # associated with the actual proof; never infer it from a headline.
        if not target_geography_source_verified or not proposed_target_geography:
            problems.add("TERRITORY_SCOPE_UNVERIFIED")
        elif proposed_target_geography.strip().casefold() != str(
                campaign.get("geography") or ""
        ).strip().casefold():
            problems.add("TERRITORY_SCOPE_MISMATCH")
        if (campaign.get("campaign_objective") != intended_conversion_objective
                or (campaign.get("conversion_plan") or {}).get("landing_path")
                   != "/research/" + requested_campaign_id):
            problems.add("CONVERSION_OBJECTIVE_MISMATCH")
        # A previously signed page may have been changed to point at a
        # different asset or privacy statement while retaining the same URL.
        # Reuse the canonical existing first-party enquiry contract.
        try:
            landing = _landing(campaign)
            if (landing.get("asset_id") != requested_campaign_id + ":landing"
                    or landing.get("privacy_notice") != PRIVACY):
                problems.add("RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH")
        except (AttributeError, TypeError, ValueError, KeyError):
            problems.add("RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH")
        if (campaign.get("outbound_authorized", False) is not False
                or campaign.get("automatic_followup", False) is not False):
            problems.add("RESEARCH_RELEASE_OUTBOUND_POLICY_CHANGED")
        if (intended_conversion_objective == "research_enquiry"
                and proposed_product_code is not None):
            problems.add("RESEARCH_FORM_IS_NOT_PRODUCT_CHECKOUT")
        elif (intended_conversion_objective == "product_enquiry"
              and (proposed_product_code is None
                   or proposed_product_code != campaign.get("product_code"))):
            problems.add("PRODUCT_CODE_MISMATCH")
    if marketing_or_auto_followup_requested or paid_media_requested:
        problems.add("PAID_MEDIA_OR_AUTOMATED_OUTBOUND_NOT_AUTHORIZED")

    verified_catalog_review = (
        review_commercial_catalog_for_conversion(catalog_source, now=now)
        if type(now) is datetime and now.tzinfo is not None else None
    )
    if (catalog_readiness.get("source_status")
            != "CURRENT_CATALOG_PRODUCT_TERMS_REVIEWED"
            or not isinstance(catalog_source, Mapping)
            or not isinstance(catalog_source.get("products"), list)
            or catalog_source.get("product_count") != len(catalog_source["products"])
            or catalog_readiness.get("products_catalogued") != len(catalog_source["products"])
            or verified_catalog_review is None
            or verified_catalog_review.get("source_status")
            != "CURRENT_CATALOG_PRODUCT_TERMS_REVIEWED"
            or catalog_readiness.get("verified_commercial_terms_products")
            != verified_catalog_review.get("verified_commercial_terms_products")):
        problems.add("CATALOG_TERMS_NOT_CURRENT")
    elif proposed_product_code is not None:
        exact_matches = [
            p for p in catalog_source["products"]
            if isinstance(p, Mapping)
            and p.get("product_code") == proposed_product_code
        ]
        if len(exact_matches) != 1 or not product_ready(exact_matches[0]):
            problems.add("PRODUCT_TERMS_UNVERIFIED")

    # A caller-supplied HTML packet or self-asserted hash is not source
    # evidence. Regenerate from a typed, account-bound case and source-owned
    # verified signals. No case means critical HOLD, not trusted marketing.
    canonical_preview = None
    if source_value_case is not None or source_signals is not None:
        from empire_os.campaign_intelligence import (
            TrustedBuyerValueCase, TrustedCampaignSignal,
            build_private_buyer_offer_experience,
        )
        if (type(source_value_case) is TrustedBuyerValueCase
                and source_value_case.context.campaign_id == requested_campaign_id
                and source_value_case.context.market_scope == proposed_market_scope
                and type(source_signals) is tuple
                and len(source_signals) <= 250
                and all(type(x) is TrustedCampaignSignal for x in source_signals)
                and type(now) is datetime and now.tzinfo is not None):
            try:
                canonical_preview = build_private_buyer_offer_experience(
                    source_value_case, verified_signals=source_signals,
                    now=now,
                )
            except ValueError:
                canonical_preview = None
    if (canonical_preview is None
            or not isinstance(proof_preview, Mapping)
            or canonical_preview.get("private_html") != proof_preview.get("private_html")
            or canonical_preview.get("offer_arm") != proposed_offer_arm
            or proof_preview.get("status") != "PRIVATE_OPERATOR_PREVIEW_READY"
            or proof_preview.get("market_scope") != proposed_market_scope
            or proof_preview.get("offer_arm") != proposed_offer_arm
            or proof_preview.get("publication_authorized") is not False
            or proof_preview.get("working_first_party_cta_present") is not False
            or proof_preview.get("customer_or_account_identity_exposed") is not False
            or proof_preview.get("financial_results_or_inventory_quantity_claimed") is not False
            or not isinstance(proof_preview.get("private_html"), str)
            or not proof_preview.get("private_html")):
        problems.add("PROOF_CONTENT_NOT_SOURCE_BOUND")
    else:
        questions = proof_preview.get("prospect_question_coverage")
        if (not isinstance(questions, Mapping)
                or questions.get("questions_reviewed") != 8
                or questions.get("conversion_ready_for_live_site") is not False):
            problems.add("PROOF_CONTENT_NOT_SOURCE_BOUND")

    for key, risk in _PROOF_PLACEMENT_OWNER_FIELDS.items():
        if approvals is None or approvals.get(key) is not True:
            problems.add(risk)
    # Approval is version-specific: the slightest changed page copy must
    # invalidate EVERY old Claims/Website/Privacy/Fulfilment signature.
    from hashlib import sha256
    canonical_html = (
        canonical_preview.get("private_html")
        if isinstance(canonical_preview, Mapping) else None
    )
    expected_digest = (
        sha256(canonical_html.encode("utf-8")).hexdigest()
        if isinstance(canonical_html, str) and canonical_html else None
    )
    if (expected_digest is None or approval_content_sha256_by_owner is None
            or any(
                approval_content_sha256_by_owner.get(k) != expected_digest
                for k in _PROOF_PLACEMENT_OWNER_FIELDS
            )):
        problems.add("STALE_OR_MISSING_EXACT_CONTENT_SIGNOFF")
    # A positive owner approval flag alone is never authority for dispatch
    # or web publishing; the website owner's release writer must verify
    # actual approvals, exact content digests and privacy at its own boundary.
    if marketing_or_auto_followup_requested or paid_media_requested:
        problems.add("UNVERIFIED_SALES_CHANNEL_BASIS")

    risks = [
        {"risk_code": key, "severity": _PROOF_PLACEMENT_RISKS[key][0],
         "existing_owner": _PROOF_PLACEMENT_RISKS[key][1]}
        for key in sorted(problems)
    ]
    return {
        "schema_version": "empire.gtm.proof_placement_prepublication_risk.v1",
        "status": (
            "CRITICAL_PREPUBLICATION_HOLD" if problems
            else "READY_FOR_INDEPENDENT_WEBSITE_OWNER_PREFLIGHT"
        ),
        "blocking_issue_count": len(problems),
        "risk_codes": [r["risk_code"] for r in risks],
        "risks": risks,
        "requested_market_scope": proposed_market_scope,
        "destination_territory_match_verified": (
            campaign is not None
            and "TERRITORY_SCOPE_UNVERIFIED" not in problems
            and "TERRITORY_SCOPE_MISMATCH" not in problems
            and "UNKNOWN_SOURCE_MARKET" not in problems
        ),
        "destination_first_party_landing_privacy_verified": (
            campaign is not None
            and "RESEARCH_LANDING_ASSET_OR_PRIVACY_MISMATCH" not in problems
            and "RESEARCH_RELEASE_OUTBOUND_POLICY_CHANGED" not in problems
        ),
        "destination_country_and_sector_match_verified":
            not any(x in problems for x in (
                "NO_SIGNED_DESTINATION_RELEASE", "CAMPAIGN_NOT_IN_SIGNED_RELEASE",
                "UNKNOWN_SOURCE_MARKET", "COUNTRY_SCOPE_MISMATCH",
                "SECTOR_SCOPE_MISMATCH")),
        "actual_queued_publication_detected": False,
        "proposed_preview_already_published": False,
        "website_release_writer_enforcement_installed": False,
        "existing_owner_independent_evidence_recheck_required": True,
        "public_contact_or_raw_content_exported": False,
        "publication_authorized": False,
        "outbound_authorized": False,
        "paid_media_authorized": False,
        "execution_authority": "NONE",
    }


class ProofPrepublicationHeld(ValueError):
    """Explicit stop signal for the existing website owner's release writer."""

    def __init__(self, reason_codes: Iterable[str]) -> None:
        codes = tuple(sorted(set(reason_codes)))
        self.reason_codes = codes
        super().__init__(
            "PROOF_PREPUBLICATION_HELD:"
            + ",".join(codes or ("NO_VERIFIED_GATE_RESULT",))
        )


def require_proof_placement_at_owner_release_boundary(
    *,
    candidate_html_bytes: bytes,
    placement_arguments: Mapping[str, Any],
    final_artifact_signoff_sha256_by_owner: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Owner-controlled release *precondition*, not a publication command.

    The site owner calls this immediately before its own atomic publisher
    write, after authenticating owner signoffs, proof sources and artifacts.
    It raises on all unsafe conditions and checks owner-approved SHA-256
    values against the exact bytes proposed for publication. The private
    source preview and the public rendered page may (and generally must)
    differ: publishing owners must separately approve the final real form,
    privacy disclosures, CTA, routes and claims. This function does not
    authenticate owner signatures and cannot authorize a publication.
    It never writes files, signals services, or issues deployment tokens.

    This is supplied as an integration hook, not installed in production.
    """
    from hashlib import sha256

    if type(candidate_html_bytes) is not bytes:
        raise ProofPrepublicationHeld(("FINAL_RENDERED_ASSET_NOT_BYTES",))
    if not 100 <= len(candidate_html_bytes) <= 1_000_000:
        raise ProofPrepublicationHeld(("FINAL_RENDERED_ASSET_SIZE_INVALID",))
    if not isinstance(placement_arguments, Mapping):
        raise ProofPrepublicationHeld(("SOURCE_PLACEMENT_CONTRACT_REQUIRED",))
    allowed = {
        "root", "requested_campaign_id", "proposed_market_scope",
        "proposed_offer_arm", "intended_conversion_objective",
        "catalog_source", "catalog_readiness", "proof_preview",
        "source_value_case", "source_signals", "now",
        "proposed_product_code", "proposed_target_geography",
        "target_geography_source_verified", "approvals",
        "approval_content_sha256_by_owner",
        "marketing_or_auto_followup_requested", "paid_media_requested",
    }
    required = {
        "root", "requested_campaign_id", "proposed_market_scope",
        "proposed_offer_arm", "intended_conversion_objective",
        "catalog_source", "catalog_readiness", "proof_preview",
        "source_value_case", "source_signals", "now",
        "proposed_target_geography", "target_geography_source_verified",
        "approvals", "approval_content_sha256_by_owner",
    }
    if (set(placement_arguments) - allowed
            or required - set(placement_arguments)):
        raise ProofPrepublicationHeld(("EXACT_RELEASE_PLACEMENT_ARGUMENTS_REQUIRED",))
    try:
        result = review_proposed_proof_placement(**dict(placement_arguments))
    except (ValueError, TypeError, AttributeError, KeyError, OSError):
        raise ProofPrepublicationHeld(("UNTRUSTED_OR_UNAVAILABLE_RELEASE_EVIDENCE",)) from None
    if (result.get("status") != "READY_FOR_INDEPENDENT_WEBSITE_OWNER_PREFLIGHT"
            or result.get("blocking_issue_count") != 0
            or result.get("risk_codes")):
        raise ProofPrepublicationHeld(
            tuple(result.get("risk_codes") or ("GATE_NOT_READY",))
        )
    # The public artifact is not the PRIVATE preview; it may include the
    # publisher's separately approved first-party enquiry form and site
    # accessibility features. Require all source-owner and final-artifact
    # approvals for the exact candidate bytes, independently.
    if (not isinstance(final_artifact_signoff_sha256_by_owner, Mapping)
            or set(final_artifact_signoff_sha256_by_owner)
            != set(_PROOF_PLACEMENT_OWNER_FIELDS)
            or any(type(v) is not str or len(v) != 64
                   or any(ch not in "0123456789abcdef" for ch in v)
                   for v in final_artifact_signoff_sha256_by_owner.values())):
        raise ProofPrepublicationHeld(("FINAL_ARTIFACT_OWNER_SIGNOFFS_REQUIRED",))
    expected = sha256(candidate_html_bytes).hexdigest()
    if any(final_artifact_signoff_sha256_by_owner[k] != expected
           for k in _PROOF_PLACEMENT_OWNER_FIELDS):
        raise ProofPrepublicationHeld(("FINAL_ASSET_CHANGED_AFTER_OWNER_SIGNOFF",))
    # Matching owner-provided digests is NOT signature authentication.
    # The real publisher must verify approvals were issued by the
    # authorized owners for THIS release and remain in force.
    return {
        "schema_version": "empire.gtm.owner_final_artifact_proof_preflight.v1",
        "status": "READY_FOR_INDEPENDENT_WEBSITE_OWNER_RELEASE_CHECKS",
        "candidate_html_sha256": expected,
        "final_artifact_digest_matches_all_owner_claims": True,
        "exact_publication_route_authenticated_here": False,
        "first_party_form_or_privacy_deployment_verified_here": False,
        "risk_issue_count": 0,
        "source_owner_attestations_independently_authenticated_here": False,
        "publication_authorized": False,
        "published": False,
        "release_writer_hook_installed": False,
        "execution_authority": "NONE",
    }


def review_hypothetical_market_placement_risks(
    root: Path, *, market_scope: str,
    catalog_source: Mapping[str, Any] | None,
    catalog_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Demonstrate scope conflicts against signed routes only; not a queue."""
    from empire_os.owned_campaign_release import load_release
    from empire_os.campaign_intelligence import _SCOPES

    if market_scope not in _SCOPES:
        raise ValueError("UNSUPPORTED_HYPOTHETICAL_MARKET_SCOPE")
    signed = load_release(root=root)
    if signed is None:
        return {
            "schema_version": "empire.gtm.hypothetical_proof_market_audit.v1",
            "status": "HOLD_NO_SIGNED_CAMPAIGNS",
            "routes_compared": None,
            "geography_mismatch_routes": None,
            "sector_mismatch_routes": None,
            "actual_proposed_placements_checked": 0,
            "publication_authorized": False,
            "execution_authority": "NONE",
        }
    destination = []
    for c in signed["campaigns"]:
        route = review_proposed_proof_placement(
            root=root,
            requested_campaign_id=c["campaign_id"],
            proposed_market_scope=market_scope,
            proposed_offer_arm="buyer_inventory_fit_offer",
            intended_conversion_objective=c["campaign_objective"],
            catalog_source=catalog_source,
            catalog_readiness=catalog_readiness,
            proposed_product_code=c.get("product_code"),
            # No actual user/owner proposal, preview, permissions, or approvals
            # exist for this hypothetical simulation.
        )
        destination.append(route)
    counts = {
        key: sum(key in row["risk_codes"] for row in destination)
        for key in ("COUNTRY_SCOPE_MISMATCH", "SECTOR_SCOPE_MISMATCH",
                    "UNKNOWN_SOURCE_MARKET")
    }
    return {
        "schema_version": "empire.gtm.hypothetical_proof_market_audit.v1",
        "status": "HYPOTHETICAL_MARKET_SCOPE_CONFLICTS_REVIEWED",
        "compared_market_scope": market_scope,
        "routes_compared": len(destination),
        "geography_mismatch_routes": counts["COUNTRY_SCOPE_MISMATCH"],
        "sector_mismatch_routes": counts["SECTOR_SCOPE_MISMATCH"],
        "unknown_source_market_routes": counts["UNKNOWN_SOURCE_MARKET"],
        "actual_proposed_placements_checked": 0,
        "actual_queued_publications_detected": False,
        "website_release_writer_enforcement_installed": False,
        "publication_authorized": False,
        "execution_authority": "NONE",
    }


def export_conversion_owner_handoff(
    output: Mapping[str, Any], *, now: datetime,
) -> dict[str, Any]:
    """Compact, zero-PII handoff for already-assigned implementation owners."""
    board = output["conversion_release_owner_board"]
    catalog = output["existing_catalog_conversion_readiness"]
    research = output["research_enquiry_aggregate_conversion_readiness"]
    release = output["existing_first_party_research_release"]
    decision = output["decision_intelligence"]
    money = decision["real_first_party_conversion_journey"]
    return {
        "schema_version": "empire.gtm.source_bound_conversion_owner_handoff.v1",
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "feature_branch_review_only": True,
        "website": {
            "signed_research_route_count": release.get("verified_research_pages"),
            "product_enquiry_pages_with_verified_catalog_terms": (
                output["existing_research_product_alignment"].get(
                    "product_enquiry_pages_with_exact_catalog_terms"
                ) if "existing_research_product_alignment" in output else None
            ),
            "research_only_pages_not_product_offers": (
                output["existing_research_product_alignment"].get(
                    "research_question_pages_not_commercial_offers"
                ) if "existing_research_product_alignment" in output else None
            ),
            "private_proof_experience_publication_proven": False,
            "prepublication_proof_risk_api_implemented_in_feature_branch": True,
            "prepublication_proof_risk_enforced_in_live_release_writer": False,
            "actual_new_publication_queue_authenticated_here": False,
            "canonical_first_party_enquiry_route": (
                release.get("existing_enquiry_route")
            ),
        },
        "catalog": {
            "source_status": catalog["source_status"],
            "products_catalogued": catalog["products_catalogued"],
            "binding_terms_ready_count": catalog["verified_commercial_terms_products"],
            "buyer_specific_delivery_timing_verified": False,
        },
        "first_party_interest": {
            "source_status": research["source_status"],
            "authentic_research_enquiries_observed": research["accepted_research_enquiries"],
            "visitor_to_buyer_rate_verified": False,
            "marketing_consent_inferred": False,
        },
        "crm": {
            "authenticated_enquiry_prospect_link_count": (
                money.get("authenticated_crm_enquiries_linked")
                if isinstance(money, Mapping) else None
            ),
        },
        "finance": {
            "recognized_campaign_revenue_cents": (
                money.get("recognized_campaign_revenue_cents")
                if isinstance(money, Mapping) else None
            ),
            "realized_campaign_profit_cents": (
                money.get("realized_campaign_gp_cents")
                if isinstance(money, Mapping) else None
            ),
        },
        "existing_owner_actions": board["tasks"],
        "execution_authority": "NONE",
        "messages_sent": False,
        "database_writes": False,
        "automatic_tasks_reassigned": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument(
        "--owner-board", action="store_true",
        help="print only the privacy-safe implementation-owner conversion handoff",
    )
    parser.add_argument(
        "--hypothetical-placement-market",
        choices=("GB:solar:buyers", "US:roofing:buyers"),
        help="compare a hypothetical offer market to existing signed routes; "
             "not an actual publication queue",
    )
    options = parser.parse_args(argv)
    if not options.read_only:
        raise ValueError("read-only required")
    root = Path("/srv/empire_os")
    current = datetime.now(timezone.utc)
    output = review_full_funnel_strategy(
        read_existing_snapshots(root), now=current,
    )
    output["real_buyer_contactability"] = review_current_buyer_contactability(
        read_existing_buyer_sources(root), now=current,
    )
    output["first_pilot_offer_creatives"] = review_three_offer_creatives(
        market_scope="GB:solar:buyers",
    )
    output["decision_intelligence"] = review_authenticated_campaign_intelligence(
        now=current,
        observer_snapshots=read_real_commercial_observers(root),
    )
    output["existing_first_party_research_release"] = (
        review_existing_research_release_entrypoints(root)
    )
    output["existing_catalog_conversion_readiness"] = (
        review_commercial_catalog_for_conversion(
            read_existing_commercial_catalog_readonly(root), now=current,
        )
    )
    # The SEO enquiry operator has a held privileged read. Its result
    # remains UNKNOWN until an independently authorised owner supplies it.
    output["existing_research_product_alignment"] = (
        review_released_product_page_alignment(
            root,
            catalog_source=read_existing_commercial_catalog_readonly(root),
            catalog_readiness=output["existing_catalog_conversion_readiness"],
        )
    )
    output["research_enquiry_aggregate_conversion_readiness"] = (
        review_existing_enquiry_aggregate_for_conversion(
            None, owner_operator_attestation_verified=False,
        )
    )
    output["conversion_release_owner_board"] = review_conversion_owner_release_board(
        release=output["existing_first_party_research_release"],
        catalog=output["existing_catalog_conversion_readiness"],
        research_aggregate=output["research_enquiry_aggregate_conversion_readiness"],
        customer_money_join=output["decision_intelligence"]["real_first_party_conversion_journey"],
    )
    output["next_real_execution_focus"] = recommend_next_real_execution_focus(output)
    if options.hypothetical_placement_market:
        print(json.dumps(review_hypothetical_market_placement_risks(
            root, market_scope=options.hypothetical_placement_market,
            catalog_source=read_existing_commercial_catalog_readonly(root),
            catalog_readiness=output["existing_catalog_conversion_readiness"],
        ), sort_keys=True))
    elif options.owner_board:
        print(json.dumps(export_conversion_owner_handoff(output, now=current), sort_keys=True))
    else:
        print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
