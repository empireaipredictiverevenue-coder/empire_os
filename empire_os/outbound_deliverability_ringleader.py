"""Ringleader: supervisory decision layer for Empire outbound deliverability."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.outbound_domain_sovereignty import evaluate_domain_sovereignty
from empire_os.outbound_canary import evaluate_canary
from empire_os.outbound_deliverability_twin import simulate_batch
from empire_os.outbound_mx_pacing import evaluate_mx_pool
from empire_os.outbound_reputation_budget import allocate_reputation_budget
from empire_os.outbound_reputation_escrow import update_reputation_credit
from empire_os.outbound_verification_depth import verification_plan
from empire_os.outbound_root_cause import detect_metric_shift, rank_candidate_causes
from empire_os.outbound_remediation_planner import plan_remediation
from empire_os.outbound_contact_pressure import evaluate_contact_pressure
from empire_os.outbound_sender_affinity import resolve_sender_affinity
from empire_os.outbound_reputation_slo import evaluate_reputation_slo
from empire_os.outbound_domain_continuity import evaluate_domain_continuity
from empire_os.outbound_health_forecast import forecast_reputation_health
from empire_os.outbound_destination_reputation import evaluate_destination_reputation
from empire_os.outbound_recipient_domain_policy import evaluate_recipient_domain_policy
from empire_os.outbound_config_attestation import detect_configuration_drift
from empire_os.outbound_infrastructure_concentration import evaluate_concentration
from empire_os.outbound_evidence_fusion import fuse_evidence
from empire_os.outbound_open_source_health import evaluate_open_source_evidence


@dataclass(frozen=True)
class RingleaderPolicy:
    require_inbox_placement_evidence_before_scale: bool = True


_PRIORITY = {
    "STOP_SEND": 100,
    "MIGRATE_TRANSPORT": 95,
    "REPAIR_AUTH": 90,
    "RECONCILE_EVIDENCE": 88,
    "REMEDIATE_DOMAIN_CONTROL": 85,
    "REFRESH_EVIDENCE": 82,
    "VERIFY_PROVIDER_POLICY": 82,
    "VERIFY_RECIPIENTS": 80,
    "RUN_CANARY": 75,
    "MEASURE_PLACEMENT": 70,
    "THROTTLE_MX": 65,
    "THROTTLE": 60,
    "REDUCE_CONCENTRATION": 55,
    "OBSERVE": 10,
}


def _task(action: str, reason: str, owner: str) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "owner": owner,
        "priority": _PRIORITY[action],
    }


def evaluate_ringleader(
    context: Mapping[str, Any] | None,
    *,
    policy: RingleaderPolicy | None = None,
) -> dict[str, Any]:
    """Fuse deliverability, policy, placement and sovereignty into one send posture."""

    policy = policy or RingleaderPolicy()
    context = dict(context or {})
    evaluation_scope = str(context.get("evaluation_scope") or "SEND").upper()
    if evaluation_scope not in {"FLEET", "BATCH", "SEND"}:
        raise ValueError("unsupported_ringleader_evaluation_scope")

    tasks: list[dict[str, Any]] = []
    hard_holds: list[str] = []

    deliverability = dict(context.get("deliverability") or {})
    health = str(deliverability.get("health") or deliverability.get("overall_health") or "UNKNOWN")
    if health == "HOLD":
        hard_holds.append("deliverability_hold")
        tasks.append(_task("STOP_SEND", "deliverability_hold", "outbound_governor"))
    elif health in {"AMBER", "RED"}:
        tasks.append(_task("THROTTLE", f"deliverability_{health.lower()}", "pacing_controller"))
    elif health != "GREEN":
        tasks.append(
            _task(
                "REFRESH_EVIDENCE",
                "deliverability_health_unverified",
                "deliverability_observer",
            )
        )

    provider_policy = context.get("provider_policy_permits_use_case")
    if provider_policy is False:
        hard_holds.append("provider_policy_mismatch")
        tasks.append(_task("MIGRATE_TRANSPORT", "provider_policy_mismatch", "transport_adapter"))
    elif provider_policy is not True:
        tasks.append(
            _task(
                "VERIFY_PROVIDER_POLICY",
                "provider_policy_unverified",
                "policy_observer",
            )
        )

    auth = dict(context.get("authentication") or {})
    missing_auth = [
        key for key in ("spf_aligned", "dkim_aligned", "dmarc_valid", "tls_ready")
        if auth.get(key) is not True
    ]
    if missing_auth:
        tasks.append(_task("REPAIR_AUTH", ",".join(missing_auth), "auth_observer"))

    recipient_quality = dict(context.get("recipient_quality") or {})
    if (
        evaluation_scope in {"BATCH", "SEND"}
        and recipient_quality.get("verified") is not True
    ):
        tasks.append(
            _task(
                "REFRESH_EVIDENCE",
            "VERIFY_RECIPIENTS",
                "recipient_quality_unverified",
                "recipient_verifier",
            )
        )

    placement = dict(context.get("placement") or {})
    if (
        evaluation_scope in {"BATCH", "SEND"}
        and policy.require_inbox_placement_evidence_before_scale
        and placement.get("measured") is not True
    ):
        tasks.append(
            _task(
                "MEASURE_PLACEMENT",
                "inbox_placement_unknown",
                "placement_lab",
            )
        )

    twin = None
    planned_batch = context.get("planned_batch")
    if (
        evaluation_scope in {"BATCH", "SEND"}
        and isinstance(planned_batch, Mapping)
    ):
        twin_current = dict(context.get("twin_current") or {})
        twin = simulate_batch(twin_current, planned_batch)
        if twin["posture"] == "HOLD":
            hard_holds.append("pre_send_twin_hold")
            tasks.append(_task("STOP_SEND", "pre_send_twin_hold", "deliverability_twin"))
        elif twin["posture"] == "CANARY_ONLY":
            tasks.append(_task("RUN_CANARY", "pre_send_twin_requires_canary", "canary_controller"))

    mx_pacing = None
    mx_pool = context.get("mx_pool")
    if isinstance(mx_pool, Mapping):
        mx_pacing = evaluate_mx_pool(mx_pool)
        if mx_pacing["state"] == "HOLD":
            tasks.append(_task("THROTTLE_MX", mx_pacing["reason"], "mx_pacing_controller"))
        elif mx_pacing["state"] == "BACKOFF":
            tasks.append(_task("THROTTLE_MX", mx_pacing["reason"], "mx_pacing_controller"))

    canary = None
    canary_result = context.get("canary_result")
    if isinstance(canary_result, Mapping):
        canary = evaluate_canary(canary_result)
        if canary["decision"] == "HOLD":
            hard_holds.append("canary_hold")
            tasks.append(_task("STOP_SEND", canary["reason"], "canary_controller"))
        elif canary["decision"] == "THROTTLE":
            tasks.append(_task("THROTTLE", canary["reason"], "pacing_controller"))

    reputation_budget = None
    budget = context.get("reputation_budget")
    if isinstance(budget, Mapping):
        opportunities = budget.get("opportunities")
        capacity = budget.get("capacity")
        if isinstance(opportunities, list) and isinstance(capacity, int):
            reputation_budget = allocate_reputation_budget(
                opportunities,
                capacity=capacity,
            )

    verification_depth = None
    verification_context = context.get("verification_context")
    if (
        evaluation_scope in {"BATCH", "SEND"}
        and isinstance(verification_context, Mapping)
    ):
        verification_depth = verification_plan(verification_context)
        if verification_depth["outcome"] == "HOLD":
            hard_holds.append("recipient_verification_risk_hold")
            tasks.append(_task("STOP_SEND", "recipient_verification_risk_hold", "recipient_verifier"))
        elif verification_depth["outcome"] == "ESCALATE":
            tasks.append(_task("VERIFY_RECIPIENTS", "deeper_verification_required", "recipient_verifier"))

    reputation_escrow = None
    escrow_context = context.get("reputation_escrow")
    if isinstance(escrow_context, Mapping):
        state = dict(escrow_context.get("state") or {})
        observation = dict(escrow_context.get("observation") or {})
        reputation_escrow = update_reputation_credit(state, observation)
        if reputation_escrow["state"] == "QUARANTINED":
            hard_holds.append("reputation_credit_exhausted")
            tasks.append(_task("STOP_SEND", "reputation_credit_exhausted", "reputation_escrow"))
        elif reputation_escrow["state"] == "LIMITED":
            tasks.append(_task("THROTTLE", "reputation_credit_low", "reputation_escrow"))

    root_cause = None
    remediation = None
    shift_context = context.get("metric_shift")
    if isinstance(shift_context, Mapping):
        before = dict(shift_context.get("before") or {})
        after = dict(shift_context.get("after") or {})
        change_events = shift_context.get("changes") or []
        metric_shift = detect_metric_shift(before, after)
        if metric_shift["shift_detected"]:
            ranked = rank_candidate_causes(change_events, metric_shift)
            root_cause = {
                "metric_shift": metric_shift,
                "candidate_causes": ranked["candidates"],
            }
            remediation = plan_remediation(ranked["candidates"])

    contact_pressure = None
    pressure_context = context.get("contact_pressure")
    if evaluation_scope == "SEND" and isinstance(pressure_context, Mapping):
        candidate = dict(pressure_context.get("candidate") or {})
        history = pressure_context.get("history") or []
        contact_pressure = evaluate_contact_pressure(candidate, history)
        if contact_pressure["decision"] == "HOLD":
            hard_holds.append("contact_pressure_hold")
            tasks.append(_task("STOP_SEND", contact_pressure["reason"], "contact_pressure_guard"))

    sender_affinity = None
    affinity_context = context.get("sender_affinity")
    if evaluation_scope == "SEND" and isinstance(affinity_context, Mapping):
        sender_affinity = resolve_sender_affinity(affinity_context)
        if sender_affinity["decision"] == "HOLD":
            hard_holds.append("sender_affinity_hold")
            tasks.append(_task("STOP_SEND", sender_affinity["reason"], "sender_affinity"))
        elif sender_affinity["decision"] == "ESCALATE":
            tasks.append(_task("OBSERVE", sender_affinity["reason"], "sender_affinity"))

    reputation_slo = None
    slo_context = context.get("reputation_slo")
    if isinstance(slo_context, Mapping):
        reputation_slo = evaluate_reputation_slo(slo_context)
        if reputation_slo["status"] == "EXHAUSTED":
            hard_holds.append("reputation_error_budget_exhausted")
            tasks.append(_task("STOP_SEND", "reputation_error_budget_exhausted", "reputation_slo"))

    domain_continuity = None
    continuity_context = context.get("domain_continuity")
    if isinstance(continuity_context, Mapping):
        from datetime import date
        domain_continuity = evaluate_domain_continuity(
            continuity_context,
            today=date.today(),
        )
        if domain_continuity["posture"] == "HOLD":
            hard_holds.append("domain_continuity_hold")
            tasks.append(_task("STOP_SEND", "domain_continuity_hold", "domain_sovereignty"))
        elif domain_continuity["posture"] == "REMEDIATE":
            tasks.append(
                _task(
                    "REMEDIATE_DOMAIN_CONTROL",
                    "domain_continuity_remediation_required",
                    "domain_sovereignty",
                )
            )

    health_forecast = None
    forecast_history = context.get("health_history")
    if isinstance(forecast_history, list):
        health_forecast = forecast_reputation_health(forecast_history)
        if health_forecast["posture"] == "PREEMPTIVE_THROTTLE":
            tasks.append(
                _task(
                    "THROTTLE",
                    "forecast_threshold_breach_risk",
                    "reputation_forecaster",
                )
            )

    destination_reputation = None
    destination_context = context.get("destination_reputation")
    if isinstance(destination_context, Mapping):
        destination_reputation = evaluate_destination_reputation(destination_context)
        if destination_reputation["posture"] == "HOLD_DESTINATION":
            tasks.append(
                _task(
                    "THROTTLE_MX",
                    "destination_reputation_hold",
                    "mx_pacing_controller",
                )
            )
        elif destination_reputation["posture"] == "LIMIT_DESTINATION":
            tasks.append(
                _task(
                    "THROTTLE_MX",
                    "destination_reputation_limited",
                    "mx_pacing_controller",
                )
            )

    recipient_domain_policy = None
    recipient_domain_context = context.get("recipient_domain_policy")
    if isinstance(recipient_domain_context, Mapping):
        recipient_domain_policy = evaluate_recipient_domain_policy(
            recipient_domain_context
        )
        if recipient_domain_policy["decision"] == "HOLD":
            hard_holds.append("recipient_domain_policy_hold")
            tasks.append(
                _task(
                    "STOP_SEND",
                    recipient_domain_policy["reason"],
                    "recipient_policy",
                )
            )
        elif recipient_domain_policy["decision"] == "ESCALATE":
            tasks.append(
                _task(
                    "VERIFY_RECIPIENTS",
                    recipient_domain_policy["reason"],
                    "recipient_verifier",
                )
            )

    configuration_drift = None
    attestation_context = context.get("configuration_attestation")
    if isinstance(attestation_context, Mapping):
        previous_configuration = dict(attestation_context.get("previous") or {})
        current_configuration = dict(attestation_context.get("current") or {})
        configuration_drift = detect_configuration_drift(
            previous_configuration,
            current_configuration,
        )
        if configuration_drift["posture"] == "HOLD":
            hard_holds.append("critical_configuration_drift")
            tasks.append(
                _task(
                    "STOP_SEND",
                    "critical_sender_infrastructure_drift",
                    "domain_sovereignty",
                )
            )
        elif configuration_drift["posture"] == "REMEDIATE":
            tasks.append(
                _task(
                    "REMEDIATE_DOMAIN_CONTROL",
                    "sender_infrastructure_drift",
                    "domain_sovereignty",
                )
            )

    infrastructure_concentration = None
    concentration_context = context.get("infrastructure_concentration")
    if isinstance(concentration_context, list):
        infrastructure_concentration = evaluate_concentration(
            concentration_context
        )
        if infrastructure_concentration["posture"] == "HIGH_CONCENTRATION":
            tasks.append(
                _task(
                    "REDUCE_CONCENTRATION",
                    "sender_infrastructure_concentration_high",
                    "pool_allocator",
                )
            )
        elif infrastructure_concentration["posture"] == "MODERATE_CONCENTRATION":
            tasks.append(
                _task(
                    "OBSERVE",
                    "sender_infrastructure_concentration_moderate",
                    "pool_allocator",
                )
            )

    evidence_fusion = None
    fusion_rows = context.get("evidence_fusion")
    if isinstance(fusion_rows, list):
        evidence_fusion = fuse_evidence(fusion_rows)
        if evidence_fusion["posture"] == "INVESTIGATE":
            hard_holds.append("critical_evidence_conflict")
            tasks.append(
                _task(
                    "STOP_SEND",
                    "critical_deliverability_evidence_conflict",
                    "evidence_fusion",
                )
            )
            tasks.append(
                _task(
                    "RECONCILE_EVIDENCE",
                    "critical_deliverability_evidence_conflict",
                    "evidence_fusion",
                )
            )
        elif evidence_fusion["conflicts"]:
            tasks.append(
                _task(
                    "RECONCILE_EVIDENCE",
                    "deliverability_evidence_conflict",
                    "evidence_fusion",
                )
            )

    open_source_health = None
    open_source_bundle = context.get("open_source_evidence")
    if isinstance(open_source_bundle, Mapping):
        open_source_health = evaluate_open_source_evidence(
            open_source_bundle
        )
        if open_source_health["posture"] == "HOLD":
            hard_holds.append("open_source_evidence_hold")
            tasks.append(
                _task(
                    "STOP_SEND",
                    "open_source_deliverability_hold",
                    "evidence_fusion",
                )
            )
            tasks.append(
                _task(
                    "REPAIR_AUTH",
                    "open_source_authentication_failure",
                    "auth_observer",
                )
            )
        elif open_source_health["posture"] == "REMEDIATE":
            warnings = set(open_source_health["warnings"])
            if any(item.startswith("dns_") for item in warnings):
                tasks.append(
                    _task(
                        "REMEDIATE_DOMAIN_CONTROL",
                        "open_source_dns_drift",
                        "domain_sovereignty",
                    )
                )
            if any("authentication" in item or "dmarc_" in item for item in warnings):
                tasks.append(
                    _task(
                        "REPAIR_AUTH",
                        "open_source_authentication_degraded",
                        "auth_observer",
                    )
                )

    sender_estate_reconciliation = None
    reconciliation_context = context.get("sender_estate_reconciliation")
    if isinstance(reconciliation_context, Mapping):
        sender_estate_reconciliation = dict(reconciliation_context)
        reconciliation_status = str(
            sender_estate_reconciliation.get("status") or "UNKNOWN"
        ).upper()
        if reconciliation_status == "HOLD":
            hard_holds.append("sender_estate_reconciliation_hold")
            tasks.append(
                _task(
                    "STOP_SEND",
                    "sender_estate_reconciliation_hold",
                    "sender_estate_reconciler",
                )
            )
        elif reconciliation_status == "DEGRADED":
            tasks.append(
                _task(
                    "RECONCILE_ESTATE",
                    "sender_estate_reconciliation_degraded",
                    "sender_estate_reconciler",
                )
            )

    sovereignty = evaluate_domain_sovereignty(context.get("domain_sovereignty"))
    if sovereignty["status"] in {"HOLD", "WEAK"}:
        tasks.append(
            _task(
                "REMEDIATE_DOMAIN_CONTROL",
                f"domain_sovereignty_{sovereignty['status'].lower()}",
                "domain_sovereignty",
            )
        )
        if sovereignty["status"] == "HOLD":
            hard_holds.append("domain_sovereignty_hold")

    # Deduplicate exact actions/reasons while keeping deterministic priority order.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for task in tasks:
        unique[(task["action"], task["reason"])] = task
    tasks = sorted(
        unique.values(),
        key=lambda item: (-int(item["priority"]), str(item["action"]), str(item["reason"])),
    )

    if hard_holds:
        posture = "HOLD"
    elif any(task["action"] in {"REPAIR_AUTH", "REMEDIATE_DOMAIN_CONTROL", "RECONCILE_EVIDENCE"} for task in tasks):
        posture = "REMEDIATE"
    elif any(
        task["action"] in {
            "REFRESH_EVIDENCE",
            "VERIFY_PROVIDER_POLICY",
            "VERIFY_RECIPIENTS",
            "RUN_CANARY",
            "MEASURE_PLACEMENT",
            "THROTTLE_MX",
            "THROTTLE",
            "REDUCE_CONCENTRATION",
        }
        for task in tasks
    ):
        posture = "LIMITED"
    else:
        posture = "READY"

    return {
        "posture": posture,
        "evaluation_scope": evaluation_scope,
        "hard_holds": hard_holds,
        "tasks": tasks,
        "domain_sovereignty": sovereignty,
        "deliverability_twin": twin,
        "mx_pacing": mx_pacing,
        "canary": canary,
        "reputation_budget": reputation_budget,
        "verification_depth": verification_depth,
        "reputation_escrow": reputation_escrow,
        "root_cause": root_cause,
        "remediation": remediation,
        "contact_pressure": contact_pressure,
        "sender_affinity": sender_affinity,
        "reputation_slo": reputation_slo,
        "domain_continuity": domain_continuity,
        "health_forecast": health_forecast,
        "destination_reputation": destination_reputation,
        "recipient_domain_policy": recipient_domain_policy,
        "sender_estate_reconciliation": sender_estate_reconciliation,
        "configuration_drift": configuration_drift,
        "infrastructure_concentration": infrastructure_concentration,
        "evidence_fusion": evidence_fusion,
        "open_source_health": open_source_health,
        "mutation_authorized": False,
    }
