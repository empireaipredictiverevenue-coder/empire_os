from empire_os.hybrid_compute import (
    Route,
    TaskKind,
)
from empire_os.node_automation_gate import (
    evaluate_automation_gate,
)
from empire_os.node_economic_scheduler import (
    ScheduleDecision,
)


def decision(
    *,
    selected="node-a",
    shadow=True,
    production=True,
):
    return ScheduleDecision(
        route=Route.LOCAL_SMALL,
        capability="compute.local.small",
        candidate_scores=(),
        selected_node_id=selected,
        shadow_selection_available=shadow,
        production_selection_available=production,
        production_authority=False,
        execution_performed=False,
        reason_codes=(),
    )


def test_safe_internal_can_be_ready_not_execute():
    gate = evaluate_automation_gate(
        task_kind=TaskKind.CLASSIFY,
        schedule=decision(),
        bounded_activation_enabled=True,
    )

    assert gate.bounded_production_ready is True
    assert gate.can_execute is False
    assert gate.production_authority is False


def test_activation_disabled_blocks():
    gate = evaluate_automation_gate(
        task_kind=TaskKind.CLASSIFY,
        schedule=decision(),
    )

    assert (
        "bounded_activation_disabled"
        in gate.blockers
    )

    assert gate.can_execute is False


def test_outbound_send_keeps_founder_gate():
    gate = evaluate_automation_gate(
        task_kind=TaskKind.OUTBOUND_SEND,
        schedule=decision(),
        bounded_activation_enabled=True,
    )

    assert gate.founder_gate_required is True
    assert gate.bounded_production_ready is False
    assert gate.can_execute is False


def test_payment_keeps_founder_gate():
    gate = evaluate_automation_gate(
        task_kind=TaskKind.PAYMENT,
        schedule=decision(),
        bounded_activation_enabled=True,
    )

    assert gate.founder_gate_required is True
    assert gate.can_execute is False


def test_scheduler_gate_must_be_open():
    gate = evaluate_automation_gate(
        task_kind=TaskKind.QUANT,
        schedule=decision(
            production=False
        ),
        bounded_activation_enabled=True,
    )

    assert gate.bounded_production_ready is False
    assert (
        "scheduler_production_gate_closed"
        in gate.blockers
    )
