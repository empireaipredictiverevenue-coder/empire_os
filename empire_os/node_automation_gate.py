"""Production automation promotion gate for Empire Node Fabric."""

from __future__ import annotations

from dataclasses import dataclass

from empire_os.hybrid_compute import (
    TaskKind,
)
from empire_os.node_economic_scheduler import (
    ScheduleDecision,
)


GATE_VERSION = "empire-node-automation-gate-v1"


FOUNDER_GATED_TASKS = frozenset({
    TaskKind.OUTBOUND_SEND,
    TaskKind.COMMERCIAL_BINDING,
    TaskKind.PAYMENT,
    TaskKind.INFRASTRUCTURE_CHANGE,
})


SAFE_INTERNAL_TASKS = frozenset({
    TaskKind.CLASSIFY,
    TaskKind.EXTRACT,
    TaskKind.SUMMARISE,
    TaskKind.REASON,
    TaskKind.RESEARCH,
    TaskKind.PREDICTIVE_REVENUE,
    TaskKind.QUANT,
    TaskKind.OPTIMIZE,
    TaskKind.OUTBOUND_DRAFT,
})


@dataclass(frozen=True)
class AutomationGate:
    task_kind: TaskKind
    node_id: str | None

    shadow_ready: bool
    bounded_production_ready: bool

    founder_gate_required: bool

    can_execute: bool
    production_authority: bool

    blockers: tuple[str, ...]


def evaluate_automation_gate(
    *,
    task_kind: TaskKind,
    schedule: ScheduleDecision,
    bounded_activation_enabled: bool = False,
) -> AutomationGate:
    blockers: list[str] = []

    founder_gate = (
        task_kind in FOUNDER_GATED_TASKS
    )

    if schedule.selected_node_id is None:
        blockers.append(
            "no_verified_scheduled_node"
        )

    if not schedule.production_selection_available:
        blockers.append(
            "scheduler_production_gate_closed"
        )

    if task_kind not in SAFE_INTERNAL_TASKS:
        blockers.append(
            "task_not_safe_internal"
        )

    if founder_gate:
        blockers.append(
            "founder_gate_required"
        )

    if not bounded_activation_enabled:
        blockers.append(
            "bounded_activation_disabled"
        )

    bounded_ready = (
        schedule.production_selection_available
        and task_kind in SAFE_INTERNAL_TASKS
        and not founder_gate
    )

    # Critical invariant:
    # readiness is not execution authority.
    #
    # A later explicit production activation changes this
    # boundary through a separate execution-plane contract.
    return AutomationGate(
        task_kind=task_kind,
        node_id=schedule.selected_node_id,
        shadow_ready=(
            schedule.shadow_selection_available
        ),
        bounded_production_ready=bounded_ready,
        founder_gate_required=founder_gate,
        can_execute=False,
        production_authority=False,
        blockers=tuple(blockers),
    )
