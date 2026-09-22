"""Astra Executive v1: business-wide goal/state/plan/delegate loop.

This module composes existing EmpireOS truth surfaces. It does not replace
specialist agents and it performs no external side effects.

Executive cycle:
WORLD STATE -> GOALS -> PRIORITY -> PLAN -> DELEGATE -> REVIEW CONTRACT

All facts remain evidence-typed. Unknown remains unknown. A plan is not an
execution, a forecast is not an actual, and a commercial recommendation does
not create commercial authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from empire_os.agi_memory import build_memory_query
from empire_os.control_fabric import default_registry
from empire_os.departments import (
    default_departments,
    departments_for_component,
)


PREDICTIVE_STATUS = Path("runtime/predictive_cloud/status_latest.json")
EVIDENCE_ROUTES = Path(
    "runtime/opportunity_factory/evidence_routes_latest.json"
)
NEXT_BEST_ACTION = Path(
    "runtime/next_best_action/next_best_action_latest.json"
)
REVENUE_PULSE = Path("runtime/revenue_pulse/latest.json")
QUANT_REVIEW = Path(
    "runtime/opportunity_factory/quant_review_latest.json"
)
CONTROL_FABRIC = Path("runtime/control_fabric/latest.json")
OUTPUT = Path("runtime/astra/executive_latest.json")


CAPABILITY_COMPONENT = {
    "conversation_os": "conversation_os",
    "market_gps_and_commercial_outcomes": "revenue_pulse",
    "sensor_mesh": "predictive_cloud_opportunity_loop",
    "commercial_product_catalog": "commercial_product_catalog",
    "buyer_capacity_readiness": "buyer_capacity_readiness",
    "intelligence_fabric": "intelligence_fabric",
    "commercial_product_catalog_and_fulfilment": "fulfilment_readiness",
    "empire_coder": "empire_coder",
    "search_fabric_and_sensor_mesh": "predictive_cloud_opportunity_loop",
    "entity_resolution": "identity_enrichment",
    "search_fabric": "search_fabric",
}


QUANT_FIELD_COMPONENT = {
    "probability_success": "predictive_intelligence",
    "uncertainty": "predictive_intelligence",
    "time_to_revenue_days": "predictive_intelligence",
    "confidence": "predictive_intelligence",
    "conditional_revenue_cents": "commercial_product_catalog",
    "fixed_cost_cents": "commercial_product_catalog",
    "success_cost_cents": "commercial_product_catalog",
    "revenue_low_cents": "commercial_product_catalog",
    "revenue_high_cents": "commercial_product_catalog",
    "success_cost_low_cents": "commercial_product_catalog",
    "success_cost_high_cents": "commercial_product_catalog",
}


NBA_COMPONENT = {
    "enrich_identity": "identity_enrichment",
    "verify_decision_maker": "identity_enrichment",
    "prepare_buyer_review": "buyer_review",
    "conversation_follow_up": "conversation_os",
    "terms_candidate": "commercial_terms",
    "payment_review": "commercial_terms",
    "fulfilment_review": "fulfilment_readiness",
    "research_more": "predictive_cloud_opportunity_loop",
}


@dataclass(frozen=True)
class ExecutiveGoal:
    key: str
    objective: str
    priority: int
    reason: str
    evidence_refs: tuple[str, ...]
    success_condition: str
    status: str = "active"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutivePlanStep:
    step_id: str
    goal_key: str
    action: str
    target_component: str
    department_keys: tuple[str, ...]
    authority: str
    auto_dispatch_eligible: bool
    founder_gate_required: bool
    evidence_refs: tuple[str, ...]
    memory_query: Mapping[str, Any]
    success_condition: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, 0)


def _component_registry() -> dict[str, Any]:
    return {row.name: row for row in default_registry()}


def build_world_state(
    *,
    predictive_status: Mapping[str, Any] | None,
    evidence_routes: Mapping[str, Any] | None,
    next_best_action: Mapping[str, Any] | None,
    revenue_pulse: Mapping[str, Any] | None,
    quant_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status = dict(predictive_status or {})
    routes = dict(evidence_routes or {})
    nba = dict(next_best_action or {})
    pulse = dict(revenue_pulse or {})
    quant = dict(quant_review or {})

    truth = pulse.get("recognized_revenue_truth")
    truth = truth if isinstance(truth, Mapping) else {}

    recognized = _nonnegative_int(truth.get("recognized_revenue_cents"))
    gp = truth.get("realized_gp_cents")
    try:
        realized_gp = int(gp) if gp is not None else None
    except (TypeError, ValueError):
        realized_gp = None

    unavailable = [
        _clean(x)
        for x in (status.get("unavailable_components") or [])
        if _clean(x)
    ]
    stale = [
        _clean(x)
        for x in (status.get("stale_components") or [])
        if _clean(x)
    ]

    route_items = [
        row for row in (routes.get("items") or [])
        if isinstance(row, Mapping)
    ]
    internal_routes = []
    commercial_routes = []
    for item in route_items:
        for route in item.get("routes") or []:
            if not isinstance(route, Mapping):
                continue
            enriched = {
                **dict(route),
                "opportunity_key": item.get("opportunity_key"),
                "opportunity_class": item.get("opportunity_class"),
                "lifecycle": item.get("lifecycle"),
            }
            if route.get("automatic_internal_work") is True:
                internal_routes.append(enriched)
            if route.get("mode") == "commercial_observation":
                commercial_routes.append(enriched)

    actions = [
        row for row in (nba.get("actions") or [])
        if isinstance(row, Mapping)
    ]

    return {
        "schema_version": "empire.astra.world_state.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "recognized_revenue_cents": recognized,
        "realized_gp_cents": realized_gp,
        "revenue_state_known": recognized is not None,
        "revenue_blocker": _clean(
            pulse.get("highest_priority_blocker")
        ) or None,
        "pulse_state": _clean(pulse.get("pulse_state")) or None,
        "unavailable_components": unavailable,
        "stale_components": stale,
        "predictive_cloud_available_component_count": (
            status.get("available_component_count")
        ),
        "opportunity_count": int(routes.get("opportunity_count") or 0),
        "opportunity_stage_counts": dict(routes.get("stage_counts") or {}),
        "automatic_internal_evidence_routes": internal_routes,
        "commercial_observation_routes": commercial_routes,
        "next_best_actions": actions,
        "next_best_action_count": len(actions),
        "founder_gate_count": int(nba.get("founder_gate_count") or 0),
        "waiting_external_count": int(
            nba.get("waiting_external_count") or 0
        ),
        "outreach_authorized": nba.get("outreach_authorized") is True,
        "payment_authorized": nba.get("payment_authorized") is True,
        "quant_decision_packet_available_count": int(
            quant.get("available_decision_packet_count") or 0
        ),
        "quant_decision_packet_unavailable_count": int(
            quant.get("unavailable_decision_packet_count") or 0
        ),
        "quant_missing_field_counts": dict(
            quant.get("missing_field_counts") or {}
        ),
        "quant_review_items": [
            row for row in (quant.get("items") or [])
            if isinstance(row, Mapping)
        ],
        "execution_authority": "none",
    }


def derive_goals(world: Mapping[str, Any]) -> tuple[ExecutiveGoal, ...]:
    goals: list[ExecutiveGoal] = []

    unavailable = tuple(world.get("unavailable_components") or ())
    stale = tuple(world.get("stale_components") or ())
    if unavailable or stale:
        refs = tuple(
            f"predictive_cloud:{name}"
            for name in (*unavailable, *stale)
        )
        goals.append(ExecutiveGoal(
            key="restore_operating_truth",
            objective=(
                "Restore fresh canonical business state before relying on "
                "degraded or missing intelligence."
            ),
            priority=100,
            reason=(
                f"unavailable={len(unavailable)} stale={len(stale)}"
            ),
            evidence_refs=refs,
            success_condition=(
                "critical Predictive Cloud components are available and fresh"
            ),
        ))

    revenue = world.get("recognized_revenue_cents")
    blocker = _clean(world.get("revenue_blocker"))
    if revenue == 0 and blocker:
        goals.append(ExecutiveGoal(
            key="advance_first_verified_revenue",
            objective=(
                "Advance the closest genuine commercial state toward verified "
                "payment, fulfilment and recognized revenue."
            ),
            priority=98,
            reason=f"recognized revenue is zero; blocker={blocker}",
            evidence_refs=("runtime:revenue_pulse",),
            success_condition=(
                "commercial loop advances one observed stage without inferred "
                "buyer intent, payment or revenue"
            ),
        ))

    actions = world.get("next_best_actions") or []
    if actions:
        internal = sum(
            row.get("founder_gate_required") is not True
            and row.get("waiting_external") is not True
            for row in actions
            if isinstance(row, Mapping)
        )
        if internal:
            goals.append(ExecutiveGoal(
                key="progress_observed_buyer_state",
                objective=(
                    "Execute or prepare the highest-value evidence-backed buyer "
                    "state transitions that remain within current authority."
                ),
                priority=94,
                reason=f"{internal} actionable buyer-state recommendations",
                evidence_refs=("runtime:next_best_action",),
                success_condition=(
                    "at least one buyer state gains new observed evidence or "
                    "reaches a governed external/founder gate"
                ),
            ))

    internal_routes = world.get("automatic_internal_evidence_routes") or []
    if internal_routes:
        goals.append(ExecutiveGoal(
            key="complete_opportunity_evidence",
            objective=(
                "Resolve missing Opportunity Factory evidence using existing "
                "Empire capabilities before proposing new systems."
            ),
            priority=90,
            reason=f"{len(internal_routes)} internal evidence routes available",
            evidence_refs=("runtime:opportunity_factory:evidence_routes",),
            success_condition=(
                "opportunity blockers decrease, lifecycle stage advances, "
                "or candidate is explicitly parked"
            ),
        ))

    quant_available = int(
        world.get("quant_decision_packet_available_count") or 0
    )
    if quant_available > 0:
        goals.append(ExecutiveGoal(
            key="evaluate_quantified_opportunities",
            objective=(
                "Use deterministic Quant decision packets to compare "
                "evidence-backed opportunity economics, downside and uncertainty."
            ),
            priority=92,
            reason=f"{quant_available} Quant decision packets are available",
            evidence_refs=("runtime:opportunity_factory:quant_review",),
            success_condition=(
                "Astra records a decision rationale grounded in Quant output "
                "without treating the recommendation as execution authority"
            ),
        ))

    quant_missing = world.get("quant_missing_field_counts") or {}
    if quant_missing:
        goals.append(ExecutiveGoal(
            key="complete_quantitative_evidence",
            objective=(
                "Resolve missing probability, uncertainty, timing or economics "
                "inputs required for deterministic Quant review."
            ),
            priority=89,
            reason=(
                f"{sum(int(v) for v in quant_missing.values())} missing "
                "Quant inputs remain across opportunities"
            ),
            evidence_refs=("runtime:opportunity_factory:quant_review",),
            success_condition=(
                "missing Quant fields decrease or remain explicitly UNKNOWN "
                "after bounded evidence review"
            ),
        ))

    commercial_routes = world.get("commercial_observation_routes") or []
    if commercial_routes:
        goals.append(ExecutiveGoal(
            key="seek_real_commercial_validation",
            objective=(
                "Move qualified opportunities toward genuine commercial "
                "observation where policy and standing authority permit."
            ),
            priority=86,
            reason=(
                f"{len(commercial_routes)} blockers require real commercial "
                "observation rather than more inference"
            ),
            evidence_refs=("runtime:opportunity_factory:evidence_routes",),
            success_condition=(
                "genuine reply, terms, payment or explicit negative outcome is "
                "observed; otherwise state remains unknown"
            ),
        ))

    if world.get("recognized_revenue_cents", 0) and (
        world.get("recognized_revenue_cents") or 0
    ) > 0:
        goals.append(ExecutiveGoal(
            key="learn_from_verified_economics",
            objective=(
                "Compare predictions and decisions with verified outcomes and "
                "feed calibration/Economic Memory."
            ),
            priority=80,
            reason="verified recognized revenue exists",
            evidence_refs=("runtime:revenue_pulse",),
            success_condition=(
                "verified outcome is captured in calibration and Economic Memory"
            ),
        ))

    if not goals:
        goals.append(ExecutiveGoal(
            key="maintain_discovery",
            objective=(
                "Continue bounded opportunity discovery and evidence collection."
            ),
            priority=70,
            reason="no higher-priority evidence-backed objective is active",
            evidence_refs=("runtime:predictive_cloud_status",),
            success_condition=(
                "new evidence is observed or all current opportunities remain "
                "unchanged after bounded review"
            ),
        ))

    goals.sort(key=lambda row: (-row.priority, row.key))
    return tuple(goals)


def _authority_for(component: str) -> str:
    registry = _component_registry()
    spec = registry.get(component)
    return spec.authority if spec is not None else "observe"


def _memory_query(
    *,
    task_id: str,
    component: str,
    task_type: str,
    entity_refs: Sequence[str] = (),
    topic_keys: Sequence[str] = (),
) -> Mapping[str, Any]:
    return build_memory_query(
        task_type=task_type,
        task_id=task_id,
        entity_refs=tuple(entity_refs),
        topic_keys=(component, *tuple(topic_keys)),
        max_items_per_type=12,
    )


def _step(
    *,
    goal: ExecutiveGoal,
    ordinal: int,
    action: str,
    component: str,
    rationale: str,
    success_condition: str,
    evidence_refs: Sequence[str],
    entity_refs: Sequence[str] = (),
    topic_keys: Sequence[str] = (),
    task_type: str = "planning",
) -> ExecutivePlanStep:
    authority = _authority_for(component)
    founder_gate = authority == "founder_gate"
    auto = authority in {"observe", "internal_write"} and not founder_gate
    material = "|".join((
        goal.key,
        str(ordinal),
        action,
        component,
        *sorted(str(x) for x in entity_refs),
    ))
    step_id = "exec_step_" + hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:16]
    return ExecutivePlanStep(
        step_id=step_id,
        goal_key=goal.key,
        action=action,
        target_component=component,
        department_keys=departments_for_component(component),
        authority=authority,
        auto_dispatch_eligible=auto,
        founder_gate_required=founder_gate,
        evidence_refs=tuple(dict.fromkeys(
            str(x) for x in evidence_refs if str(x).strip()
        )),
        memory_query=_memory_query(
            task_id=step_id,
            component=component,
            task_type=task_type,
            entity_refs=entity_refs,
            topic_keys=topic_keys,
        ),
        success_condition=success_condition,
        rationale=rationale,
    )


def build_plan(
    world: Mapping[str, Any],
    goals: Sequence[ExecutiveGoal],
    *,
    max_steps: int = 8,
) -> tuple[ExecutivePlanStep, ...]:
    if not goals:
        return ()
    primary = goals[0]
    steps: list[ExecutivePlanStep] = []

    if primary.key == "restore_operating_truth":
        steps.append(_step(
            goal=primary,
            ordinal=1,
            action="refresh_predictive_cloud_truth",
            component="ops_sentinel",
            rationale=primary.reason,
            success_condition=primary.success_condition,
            evidence_refs=primary.evidence_refs,
            topic_keys=("freshness", "source_health"),
            task_type="execution_review",
        ))

    # Buyer next-best actions are closer to revenue than generic opportunity
    # research, so include them whenever current authority permits.
    for row in world.get("next_best_actions") or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("waiting_external") is True:
            continue
        action = _clean(row.get("recommended_action"))
        component = NBA_COMPONENT.get(action)
        if not component:
            continue
        component_authority = _authority_for(component)
        if row.get("founder_gate_required") is True:
            component_authority = "founder_gate"
        entity = _clean(row.get("entity_id"))
        evidence = row.get("evidence")
        refs = [
            f"buyer_state:{entity}" if entity else "runtime:next_best_action"
        ]
        if isinstance(evidence, Mapping):
            refs.extend(
                f"nba:{key}={value}"
                for key, value in sorted(evidence.items())
                if value is not None
            )
        step = _step(
            goal=next(
                (
                    goal for goal in goals
                    if goal.key == "progress_observed_buyer_state"
                ),
                primary,
            ),
            ordinal=len(steps) + 1,
            action=action,
            component=component,
            rationale=_clean(row.get("reason"))
            or "evidence-backed next-best action",
            success_condition=(
                "buyer state gains a new observed transition or reaches an "
                "explicit external/founder gate"
            ),
            evidence_refs=refs,
            entity_refs=(entity,) if entity else (),
            topic_keys=(action, "buyer_state"),
            task_type="commercial_decision",
        )
        if component_authority == "founder_gate":
            step = ExecutivePlanStep(
                **{
                    **step.as_dict(),
                    "authority": "founder_gate",
                    "auto_dispatch_eligible": False,
                    "founder_gate_required": True,
                }
            )
        steps.append(step)
        if len(steps) >= max_steps:
            return tuple(steps)

    # Resolve missing Quant inputs before using economic ranking.
    quant_missing = world.get("quant_missing_field_counts") or {}
    for field_name, count in sorted(
        quant_missing.items(),
        key=lambda item: (-int(item[1]), str(item[0])),
    ):
        component = QUANT_FIELD_COMPONENT.get(str(field_name))
        if not component:
            continue
        steps.append(_step(
            goal=next(
                (
                    goal for goal in goals
                    if goal.key == "complete_quantitative_evidence"
                ),
                primary,
            ),
            ordinal=len(steps) + 1,
            action=f"resolve_quant_input:{field_name}",
            component=component,
            rationale=(
                f"{count} opportunities are missing Quant input "
                f"{field_name}"
            ),
            success_condition=(
                f"{field_name} is populated from typed evidence or remains "
                "explicitly UNKNOWN after bounded review"
            ),
            evidence_refs=(
                "runtime:opportunity_factory:quant_review",
                f"quant_missing:{field_name}",
            ),
            topic_keys=(str(field_name), "quant_decision_packet"),
            task_type="quantitative_research",
        ))
        if len(steps) >= max_steps:
            return tuple(steps)

    # Route missing evidence to the existing capability that owns it.
    seen: set[tuple[str, str, str]] = set()
    for route in world.get("automatic_internal_evidence_routes") or []:
        if not isinstance(route, Mapping):
            continue
        capability = _clean(route.get("capability"))
        component = CAPABILITY_COMPONENT.get(capability)
        if not component:
            continue
        blocker = _clean(route.get("blocker"))
        opportunity_key = _clean(route.get("opportunity_key"))
        action = _clean(route.get("action"))
        signature = (component, blocker, opportunity_key)
        if signature in seen:
            continue
        seen.add(signature)
        steps.append(_step(
            goal=next(
                (
                    goal for goal in goals
                    if goal.key == "complete_opportunity_evidence"
                ),
                primary,
            ),
            ordinal=len(steps) + 1,
            action=action or "resolve_opportunity_evidence",
            component=component,
            rationale=(
                f"Factory blocker {blocker} is routed to {capability}"
            ),
            success_condition=(
                f"{blocker} is resolved with provenance or remains explicitly "
                "unknown after bounded review"
            ),
            evidence_refs=(
                "runtime:opportunity_factory:evidence_routes",
                f"opportunity:{opportunity_key}",
            ),
            entity_refs=(opportunity_key,) if opportunity_key else (),
            topic_keys=(blocker, capability),
            task_type=(
                "coding" if component == "empire_coder" else "research"
            ),
        ))
        if len(steps) >= max_steps:
            return tuple(steps)

    if not steps:
        steps.append(_step(
            goal=primary,
            ordinal=1,
            action="run_bounded_opportunity_cycle",
            component="predictive_cloud_opportunity_loop",
            rationale=primary.reason,
            success_condition=primary.success_condition,
            evidence_refs=primary.evidence_refs,
            topic_keys=("opportunity_discovery",),
            task_type="research",
        ))

    return tuple(steps[:max_steps])


def build_executive_snapshot(
    *,
    predictive_status: Mapping[str, Any] | None,
    evidence_routes: Mapping[str, Any] | None,
    next_best_action: Mapping[str, Any] | None,
    revenue_pulse: Mapping[str, Any] | None,
    quant_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    world = build_world_state(
        predictive_status=predictive_status,
        evidence_routes=evidence_routes,
        next_best_action=next_best_action,
        revenue_pulse=revenue_pulse,
        quant_review=quant_review,
    )
    goals = derive_goals(world)
    plan = build_plan(world, goals)
    plan_material = json.dumps(
        {
            "goals": [goal.as_dict() for goal in goals],
            "steps": [step.as_dict() for step in plan],
        },
        sort_keys=True,
        default=str,
    )
    plan_id = "astra_plan_" + hashlib.sha256(
        plan_material.encode("utf-8")
    ).hexdigest()[:20]

    department_counts: dict[str, int] = {}
    for step in plan:
        for department_key in step.department_keys:
            department_counts[department_key] = (
                department_counts.get(department_key, 0) + 1
            )

    return {
        "schema_version": "empire.astra.executive.v2",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": plan_id,
        "world_state": world,
        "primary_goal": goals[0].as_dict(),
        "goals": [goal.as_dict() for goal in goals],
        "department_count": len(default_departments()),
        "departments_in_plan": tuple(sorted(department_counts)),
        "department_plan_counts": dict(sorted(department_counts.items())),
        "plan_step_count": len(plan),
        "auto_dispatch_eligible_count": sum(
            step.auto_dispatch_eligible for step in plan
        ),
        "founder_gate_step_count": sum(
            step.founder_gate_required for step in plan
        ),
        "plan": [step.as_dict() for step in plan],
        "evaluation_contract": {
            "compare_plan_with_next_cycle": True,
            "success_requires_observed_evidence": True,
            "verified_outcomes_required_for_learning": True,
            "forecast_is_not_actual": True,
            "plan_is_not_execution": True,
        },
        "external_execution_performed": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }


def refresh_astra_executive(repo_root: Path) -> dict[str, Any]:
    payload = build_executive_snapshot(
        predictive_status=_read(repo_root / PREDICTIVE_STATUS),
        evidence_routes=_read(repo_root / EVIDENCE_ROUTES),
        next_best_action=_read(repo_root / NEXT_BEST_ACTION),
        revenue_pulse=_read(repo_root / REVENUE_PULSE),
        quant_review=_read(repo_root / QUANT_REVIEW),
    )
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
