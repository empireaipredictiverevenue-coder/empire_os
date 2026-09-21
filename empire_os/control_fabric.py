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
