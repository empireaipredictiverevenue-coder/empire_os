"""Cross-department hook review using EXISTING EmpireOS event/department contracts.

This is a side-effect-free mapping of marketing, editorial, growth, sales,
finance, operations and AI-review triggers. It does NOT register a new event
bus, start workers, invoke models, send messages, mutate CRM, change a
published page, or infer revenue. Existing Control Fabric retains routing
authority; a trigger not already consumed by Control Fabric remains UNWIRED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from empire_os.control_fabric import default_registry, route_event
from empire_os.departments import default_departments


@dataclass(frozen=True)
class ReviewHook:
    """Recommendation-only event or editorial hook attachment."""

    key: str
    department: str
    kind: str
    event_type: str
    consumer: str
    review_action: str
    priority: int
    risk: str = "internal"
    evidence_required: bool = True

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{3,80}", self.key):
            raise ValueError("invalid_hook_key")
        if not re.fullmatch(r"[a-z][a-z0-9_]{3,100}", self.event_type):
            raise ValueError("invalid_event_type")
        if not 1 <= self.priority <= 100:
            raise ValueError("invalid_priority")
        if self.kind not in {"operational", "editorial", "conversion", "measurement", "protection", "intelligence"}:
            raise ValueError("unknown_hook_kind")
        if self.risk not in {"internal", "governed_external", "founder_gate"}:
            raise ValueError("unknown_hook_risk")


# Every consumer already exists in default Control Fabric's component map.
# A matching route is verified at review time, not assumed from an event name.
# An event name not presently routed remains visible as a gap, not an action.
_HOOKS: tuple[ReviewHook, ...] = (
    ReviewHook("seo_gap_detection", "marketing_growth", "intelligence",
               "organic_gap_observed", "search_intelligence",
               "Draft an evidence-linked SEO gap brief", 92),
    ReviewHook("seo_source_integrity_review", "marketing_growth", "measurement",
               "search_intelligence_refresh_requested", "search_intelligence",
               "Reconcile live SEO measurement before claiming keyword or indexation results", 94),
    ReviewHook("search_keyword_competitor", "market_intelligence", "intelligence",
               "search_gap_detected", "search_fabric",
               "Investigate observed keyword or competitor gap", 89),
    ReviewHook("search_media_repurposing", "marketing_growth", "editorial",
               "search_opportunity_ready", "media_os",
               "Prepare channel-specific editorial angles for review", 75),
    ReviewHook("marketing_campaign_brief", "marketing_growth", "editorial",
               "campaign_brief_ready", "demand_genesis",
               "Compare content hooks, target intent and conversion paths", 82),
    ReviewHook("media_comments_questions", "marketing_growth", "editorial",
               "media_comment_observed", "media_os",
               "Propose helpful real-audience response topics", 66),
    ReviewHook("youtube_observation", "marketing_growth", "measurement",
               "youtube_observation_ingested", "media_os",
               "Review retention, subject clarity and content opening", 73),
    ReviewHook("community_pain_signal", "market_intelligence", "intelligence",
               "community_pain_observed", "market_opportunity_agent",
               "Review observed problems and evidence before making claims", 83),
    ReviewHook("conversion_bottleneck", "marketing_growth", "conversion",
               "funnel_change_observed", "conversion_intelligence",
               "Draft CTA, trust, page and form improvement hypotheses", 93),
    ReviewHook("conversion_snapshot_review", "marketing_growth", "conversion",
               "conversion_refresh_requested", "conversion_intelligence",
               "Review observed conversion sample and next buyer conversation bottleneck", 96),
    ReviewHook("prospect_lifecycle", "sales_revenue", "conversion",
               "prospect_ingested", "revenue_pulse",
               "Review first-party prospect evidence; do not infer opt-in", 91),
    ReviewHook("buyer_reply_priority", "sales_revenue", "conversion",
               "buyer_reply_received", "buyer_reply_operations_agent",
               "Review buying signal, question, objection or explicit STOP", 97,
               "governed_external"),
    ReviewHook("buyer_reply_evidence_review", "sales_revenue", "protection",
               "reply_analysis_requested", "buyer_reply_operations_agent",
               "Reconcile mailbox and canonical reply proof before asserting a buyer response", 98),
    ReviewHook("sender_deliverability", "risk_compliance", "protection",
               "provider_delivery_event_observed", "deliverability_sender_reputation_agent",
               "Review bounce/complaint/suppression before any sending", 99,
               "governed_external"),
    ReviewHook("crm_segment_review", "customer_success", "intelligence",
               "customer_state_refresh_requested", "revenue_crm",
               "Preview evidence-backed lifecycle and editorial interests", 78),
    ReviewHook("partnership_opportunities", "partnerships_distribution", "conversion",
               "partner_research_requested", "strategic_partnerships",
               "Draft relevant commercial collaboration brief", 79,
               "governed_external"),
    ReviewHook("buyer_capacity_constraints", "partnerships_distribution", "protection",
               "buyer_capacity_refresh_requested", "buyer_capacity_readiness",
               "Review genuine routing and buyer capacity evidence", 95,
               "governed_external"),
    ReviewHook("offer_margin_change", "product", "intelligence",
               "margin_evidence_required", "commercial_product_catalog",
               "Check real unit economics before offer changes", 88),
    ReviewHook("payment_confirmed", "finance_capital", "measurement",
               "payment_verified", "revenue_pulse",
               "Read canonical payment evidence; do not invent revenue", 99,
               "founder_gate"),
    ReviewHook("fulfilment_completed", "operations_fulfilment", "measurement",
               "fulfilment_completed", "revenue_pulse",
               "Review accepted delivery evidence and satisfaction", 92,
               "governed_external"),
    ReviewHook("recognized_revenue_feedback", "finance_capital", "measurement",
               "revenue_recognized", "revenue_pulse",
               "Connect proven outcomes back to organic and campaign learning", 100,
               "founder_gate"),
    ReviewHook("revenue_snapshot_closure_review", "strategy", "measurement",
               "revenue_pulse_refreshed", "astra_executive",
               "Review verified closure state without treating forecasts as receipts", 95),
    ReviewHook("service_health_incident", "engineering", "protection",
               "service_degraded", "ops_sentinel",
               "Surface production issue and reversible remediation review", 99),
    ReviewHook("component_recovery", "engineering", "operational",
               "component_degraded", "empire_reliability_agent",
               "Reconcile observation and bounded existing recovery", 90),
    ReviewHook("data_cloud_safety", "risk_compliance", "protection",
               "data_cloud_readiness_requested", "empire_data_cloud",
               "Verify canonical EmpireDB truth and authorization", 98,
               "founder_gate"),
    ReviewHook("experiment_result_review", "rd_innovation", "intelligence",
               "experiment_review_requested", "experiment_intelligence",
               "Compare outcome to test criteria with evidence", 72),
    ReviewHook("founder_request", "strategy", "operational",
               "founder_directive_received", "founder_directive_intake",
               "Prioritize an existing gap, not another infrastructure project", 90),
    ReviewHook("capital_allocation", "finance_capital", "protection",
               "capital_review_requested", "capital_allocator",
               "Review spend and financial authority without moving funds", 94,
               "founder_gate"),
    ReviewHook("model_calibration", "data_quant", "measurement",
               "calibration_review_requested", "quant_brain",
               "Compare observed error with calibration claims, never invent uplift", 82),
    ReviewHook("outbound_intent_gate", "outbound", "protection",
               "outbound_intent_proposed", "outbound_governor",
               "Check exact consent, suppression, buyer terms, sender and founder authorization", 100,
               "governed_external"),
    # Real future trigger gaps. These events have no Control Fabric consumers:
    # they remain UNWIRED, and cannot silently execute via this catalogue.
    ReviewHook("confirmed_newsletter_opt_in", "marketing_growth", "protection",
               "newsletter_subscription_confirmed", "revenue_crm",
               "Require person/purpose/topic proof and suppression before enrolment", 95,
               "governed_external"),
    ReviewHook("website_article_live", "marketing_growth", "measurement",
               "owned_article_live_verified", "search_intelligence",
               "Track indexability and actual GSC observations, not promised ranking", 79),
    ReviewHook("media_draft_content_hook", "marketing_growth", "editorial",
               "media_draft_ready", "media_os",
               "Review opening 3 seconds, narrative, voice, CTA and sourcing", 72),
    ReviewHook("verified_opt_out", "risk_compliance", "protection",
               "email_opt_out_verified", "revenue_crm",
               "Reconcile explicit opt-out with canonical suppression before messaging", 100,
               "governed_external"),
)

# Content hooks are writing angles, NOT automated publishing triggers.
# The same lenses can guide SEO titles, article intros, newsletters, YouTube
# narration, social posts, sales collateral and landing pages.
_CONTENT_LENSES: tuple[tuple[str, str, str], ...] = (
    ("pain", "Identify an actual, specific problem", "Never exaggerate cost or consequences"),
    ("proof", "Lead with a documented result or demonstration", "No fabricated case studies, rankings, revenue or testimonials"),
    ("outcome", "Explain the useful business improvement", "Predictions and illustrative ROI must be labelled"),
    ("question", "Ask the real question a buyer is already considering", "Do not imply an unverified answer"),
    ("contrast", "Compare alternatives and their trade-offs", "No invented competitor claims or false comparisons"),
    ("mistake", "Explain a common, supportable failure mode", "Do not imply every customer experiences it"),
    ("timely", "Interpret a verified change in search, policy or buyer demand", "Require dated source and applicable territory"),
    ("reassurance", "Reduce legitimate objections with process and clarity", "Don't misrepresent legal, commercial or financial guarantees"),
    ("curiosity", "Create a reason to read the next line", "Never conceal a material qualifier or promise unsupported results"),
    ("call_to_action", "Describe one accurate next step", "Use actual working contact, download or sign-up destination"),
)


def hook_catalogue() -> tuple[ReviewHook, ...]:
    """Immutable coverage map; existing event bus remains sole dispatcher."""
    return _HOOKS


def content_hook_lenses() -> tuple[dict[str, str], ...]:
    return tuple(
        {"lens": key, "objective": description, "safety": guardrail}
        for key, description, guardrail in _CONTENT_LENSES
    )


def review_hook_coverage() -> dict[str, Any]:
    """Bounded, introspective current-code audit with no external calls."""
    components = {spec.name for spec in default_registry()}
    departments = {dept.key for dept in default_departments()}
    if len({hook.key for hook in _HOOKS}) != len(_HOOKS):
        raise ValueError("duplicate_hook_keys")
    if len({hook.event_type for hook in _HOOKS}) != len(_HOOKS):
        raise ValueError("duplicate_hook_events")
    results = []
    for hook in _HOOKS:
        if hook.consumer not in components or hook.department not in departments:
            raise ValueError("invalid_existing_component_or_department:" + hook.key)
        existing = route_event({"event_type": hook.event_type, "commercial_priority": hook.priority})
        route = next((row for row in existing if row["component"] == hook.consumer), None)
        results.append({
            **asdict(hook),
            "existing_route_wired_in_control_fabric": route is not None,
            "current_control_fabric_authority": route["authority"] if route else None,
            "status": "REVIEW_CANDIDATE_EXISTING_ROUTE" if route else "UNWIRED_NO_EXECUTION",
            "hook_execution_authority": "none",
            "model_invocation": False,
            "automatic_publish": False,
            "automatic_outbound": False,
            "funds_moved": False,
        })
    return {
        "schema_version": "empire.cross_department_hook_review.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "hooks": results,
        "total": len(results),
        "existing_route_count": sum(h["existing_route_wired_in_control_fabric"] for h in results),
        "unwired_count": sum(not h["existing_route_wired_in_control_fabric"] for h in results),
        "content_hook_lenses": list(content_hook_lenses()),
        "model_candidate": "ling-3.1-flash",
        "model_registered_or_activated_by_this_review": False,
        "new_scheduler": False,
        "new_database": False,
        "external_requests": False,
    }


def preview_event_hook(
    event: Mapping[str, Any],
    *,
    evidence_refs: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Recommend matching hook(s); never forward the original payload.

    Payloads may contain personal identifiers, private emails or provider
    secrets, so responses expose only pre-approved static recommendations
    and a one-way digest, not raw subject IDs, addresses, contents or values.
    Passing a reference is not itself verification of its source or consent.
    """
    event_type = event.get("event_type")
    if not isinstance(event_type, str) or not re.fullmatch(r"[a-z][a-z0-9_]{3,100}", event_type):
        raise ValueError("invalid_event_type")
    refs = tuple(ref.strip() for ref in evidence_refs if isinstance(ref, str) and ref.strip())
    if len(refs) > 10:
        raise ValueError("too_many_evidence_refs")
    snapshot = review_hook_coverage()
    matches = []
    for hook in snapshot["hooks"]:
        if hook["event_type"] != event_type:
            continue
        wired = hook["existing_route_wired_in_control_fabric"]
        evidence_present = bool(refs)
        matches.append({
            "hook_key": hook["key"],
            "department": hook["department"],
            "kind": hook["kind"],
            "review_action": hook["review_action"],
            "risk": hook["risk"],
            "priority": hook["priority"],
            "status": (
                "UNWIRED_NO_EXECUTION" if not wired else
                "EVIDENCE_MISSING" if not evidence_present else
                "EVIDENCE_REVIEW_PENDING"
            ),
            "evidence_reference_count": len(refs),
            "evidence_verified": False,  # no independent lookup is performed
            "existing_control_fabric_route": wired,
            "execution_allowed": False,
            "publication_authorized": False,
            "outbound_authorized": False,
            "payment_authorized": False,
        })
    digest = hashlib.sha256(
        json.dumps({"type": event_type, "refs": sorted(set(refs))}, sort_keys=True).encode("utf8")
    ).hexdigest()[:16]
    return {
        "schema_version": "empire.cross_department_hook_event_preview.v1",
        "mode": "OBSERVE",
        "event_type": event_type,
        "evidence_fingerprint": digest,
        "matches": matches,
        "execution_authority": "none",
        "canonical_record_lookup_performed": False,
        "model_invocation": False,
        "database_writes": False,
        "messages_sent": False,
        "payment_executed": False,
    }


def content_hook_brief(
    *,
    channel: str,
    audience: str,
    problem: str,
    evidence_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Draft-scoping notes for an editor or model, not generated factual claims."""
    supported = {
        "seo_article", "seo_title", "landing_page", "email_newsletter",
        "video_script", "social_post", "sales_deck", "partner_outreach",
    }
    if channel not in supported:
        raise ValueError("unsupported_content_channel")
    if not all(isinstance(x, str) and 3 <= len(x.strip()) <= 180 for x in (audience, problem)):
        raise ValueError("bounded_audience_and_problem_required")
    if len(evidence_refs) > 10:
        raise ValueError("too_many_evidence_refs")
    return {
        "schema_version": "empire.content_hook_brief.v1",
        "mode": "DRAFT_ONLY",
        "channel": channel,
        "audience": audience.strip(),
        "problem": problem.strip(),
        "candidate_lenses": list(content_hook_lenses()),
        "evidence_reference_count": len(evidence_refs),
        "claimed_evidence_requires_review": True,
        "ranking_or_revenue_claims_generated": False,
        "copy_generated": False,
        "quality_and_editorial_review_required": True,
        "publication_allowed": False,
        "outbound_allowed": False,
    }
