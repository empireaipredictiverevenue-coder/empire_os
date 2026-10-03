"""Explicit activation-readiness gate for the Empire outbound control plane.

This module separates OBSERVE deployment readiness from live-send readiness. It does not
activate services, apply migrations, mutate DNS, or authorize outbound sends.
"""
from __future__ import annotations

from typing import Any, Mapping


def evaluate_activation_readiness(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    row = dict(evidence or {})
    observe_blockers: list[str] = []
    live_blockers: list[str] = []
    warnings: list[str] = []

    if row.get("targeted_ci_green") is not True:
        observe_blockers.append("targeted_ci_not_green")

    if row.get("observer_preflight_ready") is not True:
        observe_blockers.append("observer_preflight_not_ready")

    if row.get("observer_mode") != "OBSERVE":
        observe_blockers.append("observer_not_in_observe_mode")

    if row.get("telemetry_available") is not True:
        observe_blockers.append("telemetry_unavailable")

    if row.get("provider_policy_verified") is not True:
        observe_blockers.append("provider_policy_unverified")

    if row.get("domain_sovereignty_ready") is not True:
        observe_blockers.append("domain_sovereignty_unverified")

    if row.get("authentication_ready") is not True:
        observe_blockers.append("authentication_unverified")

    persistence_required = row.get("persistence_required") is True
    if persistence_required:
        if row.get("empiredb_migrations_applied") is not True:
            observe_blockers.append("empiredb_deliverability_migrations_not_applied")
        if row.get("empiredb_roles_bound") is not True:
            observe_blockers.append("empiredb_deliverability_roles_not_bound")
    elif row.get("empiredb_migrations_applied") is not True:
        warnings.append("observe_can_run_without_persistence_but_history_will_not_be_canonical")

    if row.get("signed_evidence_required") is True:
        if row.get("signed_evidence_verified") is not True:
            observe_blockers.append("signed_evidence_not_verified")
    elif row.get("signed_evidence_verified") is not True:
        warnings.append("local_evidence_bundle_not_signature_enforced")

    # Live sending has strictly more requirements than OBSERVE.
    live_blockers.extend(observe_blockers)

    for key, reason in (
        ("outbound_governor_live_ready", "outbound_governor_not_live_ready"),
        ("recipient_verification_ready", "recipient_verification_not_ready"),
        ("suppression_ready", "suppression_state_not_ready"),
        ("seed_placement_measured", "seed_placement_not_measured"),
        ("sender_pool_ready", "sender_pool_not_ready"),
        ("transport_policy_compatible", "transport_policy_not_compatible"),
        ("founder_live_send_approved", "founder_live_send_approval_missing"),
    ):
        if row.get(key) is not True:
            live_blockers.append(reason)

    observe_status = "READY" if not observe_blockers else "BLOCKED"
    live_status = "READY_FOR_EXPLICIT_APPROVAL" if not live_blockers else "BLOCKED"

    return {
        "observe": {
            "status": observe_status,
            "blockers": observe_blockers,
        },
        "live_send": {
            "status": live_status,
            "blockers": live_blockers,
            "send_authorized": False,
        },
        "warnings": warnings,
        "database_activation_authorized": False,
        "service_activation_authorized": False,
        "dns_mutation_authorized": False,
        "send_authorized": False,
    }
