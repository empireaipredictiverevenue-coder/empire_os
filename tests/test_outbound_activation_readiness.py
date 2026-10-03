from empire_os.outbound_activation_readiness import evaluate_activation_readiness


def observe_ready(**overrides):
    value = {
        "targeted_ci_green": True,
        "observer_preflight_ready": True,
        "observer_mode": "OBSERVE",
        "telemetry_available": True,
        "provider_policy_verified": True,
        "domain_sovereignty_ready": True,
        "authentication_ready": True,
        "persistence_required": False,
        "empiredb_migrations_applied": False,
        "empiredb_roles_bound": False,
        "signed_evidence_required": False,
        "signed_evidence_verified": False,
        "observer_service_active": False,
        "observer_timer_active": False,
        "observer_watchdog_active": False,
        "observer_watchdog_timer_active": False,
        "observer_heartbeat_status": "MISSING",
        "telemetry_sla_posture": "BLIND",
        "provider_event_ingest_ready": False,
        "fleet_readiness_status": "HOLD",
    }
    value.update(overrides)
    return value


def test_observe_can_be_ready_without_live_send_or_db_activation():
    result = evaluate_activation_readiness(observe_ready())
    assert result["observe"]["status"] == "READY"
    assert result["operational_observe"]["status"] == "BLOCKED"
    assert result["live_send"]["status"] == "BLOCKED"
    assert result["send_authorized"] is False
    assert result["database_activation_authorized"] is False


def test_persistence_required_blocks_until_empiredb_is_activated():
    result = evaluate_activation_readiness(
        observe_ready(persistence_required=True)
    )
    assert result["observe"]["status"] == "BLOCKED"
    assert "empiredb_deliverability_migrations_not_applied" in result["observe"]["blockers"]
    assert "empiredb_deliverability_roles_not_bound" in result["observe"]["blockers"]


def test_live_send_requires_founder_approval_even_when_everything_else_ready():
    evidence = observe_ready(
        empiredb_migrations_applied=True,
        empiredb_roles_bound=True,
        signed_evidence_required=True,
        signed_evidence_verified=True,
        observer_service_active=True,
        observer_timer_active=True,
        observer_watchdog_active=True,
        observer_watchdog_timer_active=True,
        observer_heartbeat_status="CURRENT",
        telemetry_sla_posture="CURRENT",
        provider_event_ingest_ready=True,
        fleet_readiness_status="READY",
    )
    evidence.update({
        "outbound_governor_live_ready": True,
        "recipient_verification_ready": True,
        "suppression_ready": True,
        "seed_placement_measured": True,
        "sender_pool_ready": True,
        "transport_policy_compatible": True,
        "capacity_reservation_ready": True,
        "claim_evidence_ready": True,
        "account_saturation_ready": True,
        "source_reputation_ready": True,
        "content_family_reputation_ready": True,
        "founder_live_send_approved": False,
        "exact_batch_approval_bound": False,
    })
    result = evaluate_activation_readiness(evidence)
    assert result["observe"]["status"] == "READY"
    assert result["live_send"]["status"] == "BLOCKED"
    assert "founder_live_send_approval_missing" in result["live_send"]["blockers"]
    assert "exact_batch_approval_binding_missing" in result["live_send"]["blockers"]
    assert result["live_send"]["send_authorized"] is False


def test_even_ready_for_exact_send_gate_never_self_authorizes_send():
    evidence = observe_ready(
        empiredb_migrations_applied=True,
        empiredb_roles_bound=True,
        signed_evidence_required=True,
        signed_evidence_verified=True,
        observer_service_active=True,
        observer_timer_active=True,
        observer_watchdog_active=True,
        observer_watchdog_timer_active=True,
        observer_heartbeat_status="CURRENT",
        telemetry_sla_posture="CURRENT",
        provider_event_ingest_ready=True,
        fleet_readiness_status="READY",
    )
    evidence.update({
        "outbound_governor_live_ready": True,
        "recipient_verification_ready": True,
        "suppression_ready": True,
        "seed_placement_measured": True,
        "sender_pool_ready": True,
        "transport_policy_compatible": True,
        "capacity_reservation_ready": True,
        "claim_evidence_ready": True,
        "account_saturation_ready": True,
        "source_reputation_ready": True,
        "content_family_reputation_ready": True,
        "founder_live_send_approved": True,
        "exact_batch_approval_bound": True,
    })
    result = evaluate_activation_readiness(evidence)
    assert result["operational_observe"]["status"] == "READY"
    assert result["live_send"]["status"] == "READY_FOR_SEND_GATE"
    assert result["send_authorized"] is False



def test_operational_observe_requires_watchdog_heartbeat_and_current_telemetry():
    result = evaluate_activation_readiness(observe_ready())
    blockers = result["operational_observe"]["blockers"]
    assert result["observe"]["status"] == "READY"
    assert result["operational_observe"]["status"] == "BLOCKED"
    assert "observer_service_not_active" in blockers
    assert "observer_watchdog_not_active" in blockers
    assert "observer_heartbeat_not_current" in blockers
    assert "telemetry_sla_not_current" in blockers
    assert "provider_event_ingest_not_ready" in blockers


def test_live_send_requires_fleet_and_new_governance_layers():
    evidence = observe_ready(
        empiredb_migrations_applied=True,
        empiredb_roles_bound=True,
        observer_service_active=True,
        observer_timer_active=True,
        observer_watchdog_active=True,
        observer_watchdog_timer_active=True,
        observer_heartbeat_status="CURRENT",
        telemetry_sla_posture="CURRENT",
        provider_event_ingest_ready=True,
        fleet_readiness_status="LIMITED",
    )
    evidence.update({
        "outbound_governor_live_ready": True,
        "recipient_verification_ready": True,
        "suppression_ready": True,
        "seed_placement_measured": True,
        "sender_pool_ready": True,
        "transport_policy_compatible": True,
        "capacity_reservation_ready": False,
        "claim_evidence_ready": False,
        "account_saturation_ready": False,
        "source_reputation_ready": False,
        "content_family_reputation_ready": False,
        "founder_live_send_approved": True,
        "exact_batch_approval_bound": True,
    })
    result = evaluate_activation_readiness(evidence)
    blockers = result["live_send"]["blockers"]
    assert "fleet_readiness_not_ready" in blockers
    assert "capacity_reservation_not_ready" in blockers
    assert "claim_evidence_not_ready" in blockers
    assert "account_saturation_not_ready" in blockers
    assert "source_reputation_not_ready" in blockers
    assert "content_family_reputation_not_ready" in blockers
