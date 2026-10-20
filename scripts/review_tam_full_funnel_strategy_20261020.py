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
from typing import Any, Callable, Mapping

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
        metric="verified_paying_customers_per_eligible_delivery",
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
        metric="verified_paying_customers_per_eligible_delivery",
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
    for key in lookup_keys:
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
                prior = by_company.setdefault(row.company_lookup_key, arm)
                if arm != prior:
                    # Should be impossible with deterministic assignment.
                    raise ValueError("company experiment arm collision")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
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
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
