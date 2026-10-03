"""Compose canonical outbound production-readiness evidence into one snapshot."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.outbound_activation_readiness import (
    evaluate_activation_readiness,
)


def build_production_readiness_snapshot(
    *,
    release_evidence: Mapping[str, Any],
    observer_preflight: Mapping[str, Any],
    empiredb_activation: Mapping[str, Any] | None,
    service_state: Mapping[str, Any],
    observer_heartbeat: Mapping[str, Any],
    provider_event_heartbeat: Mapping[str, Any],
    fleet_readiness: Mapping[str, Any] | None,
    governance_state: Mapping[str, Any],
    approval_state: Mapping[str, Any],
) -> dict[str, Any]:
    release = dict(release_evidence or {})
    preflight = dict(observer_preflight or {})
    db = dict(empiredb_activation or {})
    services = dict(service_state or {})
    heartbeat = dict(observer_heartbeat or {})
    provider_event = dict(provider_event_heartbeat or {})
    fleet = dict(fleet_readiness or {})
    governance = dict(governance_state or {})
    approval = dict(approval_state or {})

    persistence_required = bool(
        preflight.get("persistence_required")
        or release.get("persistence_required")
    )

    db_ready = db.get("status") == "READY"
    provider_event_ready = (
        provider_event.get("success") is True
        and provider_event.get("coverage") is True
    )

    evidence = {
        "targeted_ci_green": release.get("targeted_ci_green") is True,
        "observer_preflight_ready": preflight.get("status") == "READY",
        "observer_mode": preflight.get("mode"),
        "telemetry_available": release.get("telemetry_available") is True,
        "provider_policy_verified": (
            release.get("provider_policy_verified") is True
        ),
        "domain_sovereignty_ready": (
            release.get("domain_sovereignty_ready") is True
        ),
        "authentication_ready": release.get("authentication_ready") is True,
        "persistence_required": persistence_required,
        "empiredb_migrations_applied": db_ready,
        "empiredb_roles_bound": (
            db.get("roles_ready") is True
            and db.get("privileges_ready") is True
        ),
        "signed_evidence_required": (
            preflight.get("signed_evidence_required") is True
        ),
        "signed_evidence_verified": (
            preflight.get("evidence_signature_status") == "VERIFIED"
        ),
        "observer_service_active": (
            services.get("observer_service_active") is True
        ),
        "observer_timer_active": (
            services.get("observer_timer_active") is True
        ),
        "observer_watchdog_active": (
            services.get("observer_watchdog_active") is True
        ),
        "observer_watchdog_timer_active": (
            services.get("observer_watchdog_timer_active") is True
        ),
        "observer_heartbeat_status": heartbeat.get("status"),
        "telemetry_sla_posture": heartbeat.get("telemetry_posture"),
        "provider_event_ingest_ready": provider_event_ready,
        "fleet_readiness_status": fleet.get("status"),
        "outbound_governor_live_ready": (
            governance.get("outbound_governor_live_ready") is True
        ),
        "recipient_verification_ready": (
            governance.get("recipient_verification_ready") is True
        ),
        "suppression_ready": governance.get("suppression_ready") is True,
        "seed_placement_measured": (
            governance.get("seed_placement_measured") is True
        ),
        "sender_pool_ready": governance.get("sender_pool_ready") is True,
        "transport_policy_compatible": (
            governance.get("transport_policy_compatible") is True
        ),
        "capacity_reservation_ready": (
            governance.get("capacity_reservation_ready") is True
        ),
        "claim_evidence_ready": (
            governance.get("claim_evidence_ready") is True
        ),
        "account_saturation_ready": (
            governance.get("account_saturation_ready") is True
        ),
        "source_reputation_ready": (
            governance.get("source_reputation_ready") is True
        ),
        "content_family_reputation_ready": (
            governance.get("content_family_reputation_ready") is True
        ),
        "founder_live_send_approved": (
            approval.get("founder_live_send_approved") is True
        ),
        "exact_batch_approval_bound": (
            approval.get("exact_batch_approval_bound") is True
        ),
    }

    activation = evaluate_activation_readiness(evidence)

    if activation["live_send"]["status"] == "READY_FOR_SEND_GATE":
        status = "SEND_GATE_READY"
    elif activation["operational_observe"]["status"] == "READY":
        status = "OBSERVE_OPERATIONAL"
    elif activation["observe"]["status"] == "READY":
        status = "OBSERVE_DEPLOY_READY"
    else:
        status = "BLOCKED"

    return {
        "status": status,
        "activation": activation,
        "evidence": evidence,
        "components": {
            "release": release,
            "observer_preflight": preflight,
            "empiredb_activation": db or None,
            "service_state": services,
            "observer_heartbeat": heartbeat,
            "provider_event_heartbeat": provider_event,
            "fleet_readiness": fleet or None,
            "governance_state": governance,
            "approval_state": approval,
        },
        "database_activation_authorized": False,
        "service_activation_authorized": False,
        "dns_mutation_authorized": False,
        "provisioning_authorized": False,
        "send_authorized": False,
    }
