"""EmpireOS control fabric: shared event and component contracts.

This module is orchestration glue, not a replacement for specialist workflows.
It describes which components consume/produce events, their dependencies,
authority, SLA and commercial priority. It is side-effect free.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


AUTHORITY_LEVELS = ("observe", "internal_write", "governed_external", "founder_gate")


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    source: str
    subject_id: str | None = None
    payload: Mapping[str, Any] | None = None
    evidence_refs: tuple[str, ...] = ()
    commercial_priority: int = 50
    occurred_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        now = self.occurred_at or datetime.now(timezone.utc).isoformat()
        return {
            "schema_version": "empire.control_event.v1",
            "event_type": self.event_type,
            "source": self.source,
            "subject_id": self.subject_id,
            "payload": dict(self.payload or {}),
            "evidence_refs": list(dict.fromkeys(self.evidence_refs)),
            "commercial_priority": max(0, min(100, int(self.commercial_priority))),
            "occurred_at": now,
        }


@dataclass(frozen=True)
class ComponentSpec:
    name: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    authority: str = "observe"
    sla_seconds: int = 300
    repair_policy: str = "retry_then_escalate"
    owner: str = "astra"

    def __post_init__(self) -> None:
        if self.authority not in AUTHORITY_LEVELS:
            raise ValueError(f"invalid authority: {self.authority}")
        if self.sla_seconds < 1:
            raise ValueError("sla_seconds must be positive")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_registry() -> tuple[ComponentSpec, ...]:
    """Current canonical component map. Expand without coupling modules."""
    return (
        ComponentSpec(
            "founder_directive_intake",
            ("founder_directive_received",),
            ("founder_directive_captured",),
            (),
            "internal_write",
            60,
        ),
        ComponentSpec(
            "founder_directive_planner",
            ("founder_directive_captured", "founder_directive_plan_retry"),
            ("implementation_plan_ready", "founder_gate_required"),
            ("empire_coder",),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "predictive_cloud_opportunity_loop",
            (
                "opportunity_cycle_tick",
                "signal_discovered",
                "market_snapshot_refreshed",
                "community_pain_observed",
                "competitive_evidence_refreshed",
            ),
            (
                "opportunity_radar_refreshed",
                "opportunity_research_refreshed",
                "opportunity_factory_intake_refreshed",
                "opportunity_ai_plan_queued",
            ),
            ("search_fabric", "empire_coder"),
            "internal_write",
            1800,
        ),
        ComponentSpec(
            "astra_executive",
            (
                "executive_tick",
                "revenue_pulse_refreshed",
                "opportunity_factory_intake_refreshed",
                "buyer_state_refreshed",
                "predictive_cloud_status_refreshed",
            ),
            (
                "executive_plan_ready",
                "founder_gate_required",
            ),
            (
                "predictive_cloud_opportunity_loop",
                "revenue_pulse",
                "empire_coder",
            ),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "commercial_product_catalog",
            (
                "product_catalog_refresh_requested",
                "margin_evidence_required",
                "offer_match_required",
            ),
            (
                "commercial_product_catalog_refreshed",
                "product_economics_resolved",
                "offer_match_resolved",
            ),
            (),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "buyer_capacity_readiness",
            (
                "buyer_capacity_refresh_requested",
                "distribution_evidence_required",
            ),
            (
                "buyer_capacity_readiness_refreshed",
                "distribution_path_resolved",
            ),
            ("canonical_supabase",),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "fulfilment_readiness",
            (
                "fulfilment_readiness_requested",
                "fulfilment_evidence_required",
            ),
            (
                "fulfilment_readiness_resolved",
                "fulfilment_review_required",
            ),
            ("commercial_product_catalog",),
            "internal_write",
            600,
        ),
        ComponentSpec(
            "intelligence_fabric",
            (
                "data_advantage_evidence_required",
                "evidence_freshness_requested",
            ),
            (
                "data_advantage_measured",
                "evidence_freshness_refreshed",
            ),
            (),
            "internal_write",
            600,
        ),
        ComponentSpec(
            "empire_coder",
            (
                "implementation_plan_ready",
                "build_complexity_evidence_required",
                "reversible_build_requested",
            ),
            (
                "coder_plan_ready",
                "build_complexity_measured",
                "reversible_build_completed",
                "verification_ready",
            ),
            (),
            "internal_write",
            1800,
        ),
        ComponentSpec(
            "astra",
            ("coordination_tick", "executive_plan_ready"),
            ("workstream_ranked", "coordination_snapshot_ready"),
            ("astra_executive",),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "control_fabric",
            ("route_requested", "authority_check_requested"),
            ("route_resolved", "authority_resolved"),
            (),
            "observe",
            60,
        ),
        ComponentSpec(
            "runtime_self_heal",
            (
                "runtime_health_tick",
                "component_degraded",
                "snapshot_stale",
                "service_unhealthy",
            ),
            (
                "runtime_health_refreshed",
                "runtime_repair_attempted",
                "runtime_repair_verified",
                "founder_gate_required",
            ),
            ("control_fabric",),
            "internal_write",
            120,
            "allowlisted_reversible_only",
        ),
        ComponentSpec(
            "marketing",
            (
                "marketing_objective_ready",
                "positioning_refresh_requested",
                "campaign_plan_requested",
            ),
            (
                "marketing_plan_ready",
                "campaign_brief_ready",
                "positioning_ready",
            ),
            (
                "search_intelligence",
                "conversion_intelligence",
                "demand_genesis",
            ),
            "internal_write",
            1800,
        ),
        ComponentSpec(
            "media_os",
            (
                "media_opportunity_scan_requested",
                "search_opportunity_ready",
                "community_pain_observed",
                "revenue_pulse_refreshed",
                "media_analytics_refreshed",
                "youtube_observation_ingested",
                "media_trend_fusion_requested",
                "build_journal_event_recorded",
                "media_comment_observed",
                "media_refresh_requested",
                "media_workflow_execution_observed",
                "media_distribution_observed",
                "media_algorithm_review_requested",
                "media_runtime_refresh_requested",
                "media_claim_verification_requested",
                "media_content_pipeline_requested",
            ),
            (
                "media_runtime_refreshed",
                "youtube_intelligence_refreshed",
                "media_algorithm_intelligence_ready",
                "media_recommendation_chain_ready",
                "media_algorithm_hypothesis_ready",
                "media_trend_fusion_ready",
                "media_opportunity_features_ready",
                "media_research_pack_requested",
                "media_claim_verification_ready",
                "media_canonical_content_ready",
                "media_script_brief_ready",
                "media_draft_ready",
                "media_calendar_ready",
                "media_retention_analysis_ready",
                "media_attention_graph_packet_ready",
                "media_attribution_packet_ready",
                "media_channel_candidate_ready",
                "media_skill_candidate_ready",
                "media_release_candidate_ready",
                "quant_review_requested",
                "experiment_review_requested",
                "founder_gate_required",
            ),
            (
                "marketing",
                "search_intelligence",
                "intelligence_fabric",
                "quant_brain",
                "experiment_intelligence",
                "revenue_pulse",
                "conversion_intelligence",
                "revenue_crm",
            ),
            "internal_write",
            1800,
        ),
        ComponentSpec(
            "search_intelligence",
            (
                "search_intelligence_refresh_requested",
                "organic_gap_observed",
                "ai_visibility_gap_observed",
            ),
            (
                "search_opportunity_ready",
                "search_evidence_refreshed",
            ),
            ("search_fabric",),
            "internal_write",
            1800,
        ),
        ComponentSpec(
            "demand_genesis",
            (
                "demand_experiment_requested",
                "campaign_brief_ready",
            ),
            (
                "demand_plan_ready",
                "campaign_draft_ready",
            ),
            ("marketing",),
            "internal_write",
            1800,
        ),
        ComponentSpec(
            "conversion_intelligence",
            (
                "conversion_refresh_requested",
                "funnel_change_observed",
            ),
            (
                "conversion_analysis_ready",
                "bottleneck_detected",
            ),
            ("revenue_pulse",),
            "observe",
            900,
        ),
        ComponentSpec(
            "intelligence_router",
            (
                "intelligence_route_requested",
                "model_capability_requested",
            ),
            (
                "intelligence_route_ready",
                "model_capability_route_ready",
            ),
            (),
            "observe",
            60,
        ),
        ComponentSpec(
            "predictive_intelligence",
            (
                "probability_estimate_requested",
                "uncertainty_estimate_requested",
                "time_to_revenue_estimate_requested",
                "confidence_review_requested",
            ),
            (
                "probability_estimate_ready",
                "uncertainty_estimate_ready",
                "time_to_revenue_estimate_ready",
                "confidence_review_ready",
            ),
            (
                "intelligence_fabric",
                "quant_brain",
            ),
            "observe",
            900,
        ),
        ComponentSpec(
            "quant_brain",
            (
                "quant_review_requested",
                "economics_review_requested",
                "risk_review_requested",
                "calibration_review_requested",
                "value_of_information_requested",
            ),
            (
                "quant_decision_packet_ready",
                "economics_review_ready",
                "risk_review_ready",
                "calibration_review_ready",
            ),
            (),
            "observe",
            300,
        ),
        ComponentSpec(
            "experiment_intelligence",
            (
                "experiment_review_requested",
                "causal_review_requested",
            ),
            (
                "experiment_analysis_ready",
                "causal_evidence_ready",
            ),
            ("quant_brain",),
            "observe",
            1800,
        ),
        ComponentSpec(
            "digital_twin",
            (
                "scenario_review_requested",
                "twin_refresh_requested",
            ),
            (
                "scenario_analysis_ready",
                "digital_twin_refreshed",
            ),
            ("quant_brain",),
            "observe",
            1800,
        ),
        ComponentSpec(
            "predictive_cloud_status",
            (
                "predictive_cloud_status_requested",
                "component_health_changed",
            ),
            ("predictive_cloud_status_ready",),
            ("ops_sentinel",),
            "observe",
            300,
        ),
        ComponentSpec(
            "revenue_crm",
            (
                "customer_state_refresh_requested",
                "retention_review_requested",
                "expansion_review_requested",
            ),
            (
                "customer_state_refreshed",
                "retention_signal_ready",
                "expansion_opportunity_ready",
            ),
            ("conversation_os",),
            "internal_write",
            900,
        ),
        ComponentSpec(
            "capital_allocator",
            (
                "capital_review_requested",
                "portfolio_review_requested",
            ),
            (
                "capital_recommendation_ready",
                "portfolio_analysis_ready",
                "founder_gate_required",
            ),
            ("quant_brain", "revenue_pulse"),
            "founder_gate",
            1800,
        ),
        ComponentSpec(
            "strategic_partnerships",
            (
                "partner_research_requested",
                "distribution_gap_observed",
            ),
            (
                "partner_candidate_ready",
                "distribution_option_ready",
            ),
            ("buyer_capacity_readiness",),
            "internal_write",
            3600,
        ),
        ComponentSpec(
            "market_opportunity_agent",
            (
                "signal_discovered",
                "search_gap_detected",
                "storm_opportunity_detected",
                "community_pain_observed",
                "search_growth_gap_observed",
            ),
            ("opportunity_candidate_created",),
            ("search_fabric",),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "opportunity_factory",
            ("opportunity_candidate_created",),
            ("opportunity_research_requested", "mvp_build_requested", "opportunity_parked"),
            ("market_opportunity_agent",),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "acquisition",
            ("market_sweep_requested", "storm_opportunity_detected", "source_refresh_requested"),
            ("prospect_ingested", "signal_discovered", "acquisition_failed"),
            ("source_health",),
            "internal_write",
            900,
        ),
        ComponentSpec(
            "qualification",
            ("prospect_ingested", "qualification_requested"),
            ("prospect_qualified", "qualification_failed"),
            ("canonical_supabase",),
            "internal_write",
            900,
        ),
        ComponentSpec(
            "omega_readiness",
            ("prospect_qualified",),
            ("buyer_readiness_scored",),
            ("qualification",),
            "internal_write",
            600,
        ),
        ComponentSpec(
            "identity_enrichment",
            ("buyer_readiness_scored", "identity_recovery_requested"),
            ("decision_maker_resolved", "identity_deferred"),
            ("search_fabric",),
            "internal_write",
            900,
        ),
        ComponentSpec(
            "buyer_review",
            ("decision_maker_resolved", "buyer_review_requested"),
            ("buyer_review_proposed", "buyer_review_deferred"),
            ("canonical_supabase",),
            "internal_write",
            900,
        ),
        ComponentSpec(
            "gtm",
            ("buyer_review_approved",),
            ("outbound_intent_proposed",),
            ("outbound_governor",),
            "governed_external",
            900,
        ),
        ComponentSpec(
            "outbound_governor",
            ("outbound_intent_proposed",),
            ("outbound_authorized", "outbound_blocked"),
            ("provider_health",),
            "governed_external",
            300,
        ),
        ComponentSpec(
            "conversation_os",
            ("buyer_reply_received",),
            ("buyer_conversation_observed", "terms_candidate_created"),
            (),
            "internal_write",
            300,
        ),
        ComponentSpec(
            "commercial_terms",
            ("terms_candidate_created",),
            ("commercial_terms_proposed",),
            (),
            "founder_gate",
            1800,
        ),
        ComponentSpec(
            "revenue_pulse",
            (
                "prospect_ingested", "buyer_conversation_observed",
                "commercial_terms_proposed", "payment_verified",
                "fulfilment_completed", "revenue_recognized",
            ),
            ("revenue_pulse_refreshed",),
            (),
            "observe",
            300,
        ),
        ComponentSpec(
            "search_fabric",
            ("search_gap_detected", "identity_recovery_requested"),
            ("search_intelligence_ready", "identity_evidence_found"),
            (),
            "internal_write",
            600,
        ),
        ComponentSpec(
            "ops_sentinel",
            ("health_tick", "job_failed", "service_degraded", "workflow_stalled"),
            ("repair_requested", "incident_opened", "health_ok"),
            (),
            "observe",
            120,
        ),
        ComponentSpec(
            "ops_incident_manager",
            ("incident_opened", "repair_failed", "service_degraded", "workflow_stalled"),
            ("incident_diagnosed", "incident_escalated"),
            ("ops_sentinel", "ops_healer"),
            "observe",
            180,
        ),
        ComponentSpec(
            "ops_healer",
            ("repair_requested",),
            ("repair_succeeded", "repair_failed"),
            ("ops_sentinel",),
            "internal_write",
            300,
        ),
    )


def route_event(
    event: EventEnvelope | Mapping[str, Any],
    registry: Iterable[ComponentSpec] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic candidate routes ordered by commercial priority/SLA."""
    event_type = (
        event.event_type if isinstance(event, EventEnvelope)
        else str(event.get("event_type") or "").strip()
    )
    priority = (
        event.commercial_priority if isinstance(event, EventEnvelope)
        else int(event.get("commercial_priority") or 50)
    )
    if not event_type:
        raise ValueError("event_type required")

    routes = []
    for spec in registry or default_registry():
        if event_type not in spec.consumes:
            continue
        routes.append({
            "component": spec.name,
            "authority": spec.authority,
            "sla_seconds": spec.sla_seconds,
            "repair_policy": spec.repair_policy,
            "dependencies": list(spec.dependencies),
            "commercial_priority": max(0, min(100, priority)),
        })
    routes.sort(key=lambda row: (-row["commercial_priority"], row["sla_seconds"], row["component"]))
    return routes
