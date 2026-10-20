"""Read-only operational assessment of Taylor Haren-style TAM-to-revenue campaigns.

Reuses Empire's TAM, outreach optimiser, owned campaign, analytics and measured
outcome snapshots. Plans one 30-60-day market touch, offer/creative experiments,
same-day signal review and paying-customer feedback. NEVER dispatches outreach,
enrols contacts, exports audiences, or changes any production source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping

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
        blockers.append("COMPLETE_VERIFIED_QUALIFIED_TAM_NOT_AVAILABLE")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    options = parser.parse_args(argv)
    if not options.read_only:
        raise ValueError("read-only required")
    output = review_full_funnel_strategy(
        read_existing_snapshots(Path("/srv/empire_os")),
        now=datetime.now(timezone.utc),
    )
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
