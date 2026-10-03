from empire_os.outbound_production_readiness_snapshot import (
    build_production_readiness_snapshot,
)


def base_release(**overrides):
    row = {
        "targeted_ci_green": True,
        "telemetry_available": True,
        "provider_policy_verified": True,
        "domain_sovereignty_ready": True,
        "authentication_ready": True,
        "persistence_required": False,
    }
    row.update(overrides)
    return row


def preflight(**overrides):
    row = {
        "status": "READY",
        "mode": "OBSERVE",
        "persistence_required": False,
        "signed_evidence_required": False,
        "evidence_signature_status": "UNSIGNED",
    }
    row.update(overrides)
    return row


def services(active=True):
    return {
        "observer_service_active": active,
        "observer_timer_active": active,
        "observer_watchdog_active": active,
        "observer_watchdog_timer_active": active,
    }


def heartbeat(status="CURRENT", telemetry="CURRENT"):
    return {
        "status": status,
        "telemetry_posture": telemetry,
    }


def provider_event(success=True, coverage=True):
    return {
        "success": success,
        "coverage": coverage,
    }


def fleet(status="READY"):
    return {"status": status}


def governance(**overrides):
    row = {
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
    }
    row.update(overrides)
    return row


def approval(approved=False, exact=False):
    return {
        "founder_live_send_approved": approved,
        "exact_batch_approval_bound": exact,
    }


def build(**overrides):
    kwargs = {
        "release_evidence": base_release(),
        "observer_preflight": preflight(),
        "empiredb_activation": None,
        "service_state": services(),
        "observer_heartbeat": heartbeat(),
        "provider_event_heartbeat": provider_event(),
        "fleet_readiness": fleet(),
        "governance_state": governance(),
        "approval_state": approval(),
    }
    kwargs.update(overrides)
    return build_production_readiness_snapshot(**kwargs)


def test_operational_observe_ready_but_live_gate_blocked_without_approval():
    result = build()
    assert result["status"] == "OBSERVE_OPERATIONAL"
    assert result["activation"]["observe"]["status"] == "READY"
    assert result["activation"]["operational_observe"]["status"] == "READY"
    assert result["activation"]["live_send"]["status"] == "BLOCKED"
    assert "founder_live_send_approval_missing" in (
        result["activation"]["live_send"]["blockers"]
    )
    assert result["send_authorized"] is False


def test_deploy_ready_when_services_are_not_yet_active():
    result = build(
        service_state=services(active=False),
        observer_heartbeat=heartbeat(status="MISSING", telemetry=None),
        provider_event_heartbeat=provider_event(False, False),
    )
    assert result["status"] == "OBSERVE_DEPLOY_READY"
    assert result["activation"]["observe"]["status"] == "READY"
    assert result["activation"]["operational_observe"]["status"] == "BLOCKED"


def test_exact_batch_approval_can_reach_send_gate_but_never_self_authorizes():
    result = build(
        approval_state=approval(approved=True, exact=True),
    )
    assert result["status"] == "SEND_GATE_READY"
    assert result["activation"]["live_send"]["status"] == "READY_FOR_SEND_GATE"
    assert result["activation"]["live_send"]["send_authorized"] is False
    assert result["send_authorized"] is False


def test_provider_event_blindness_blocks_operational_observe():
    result = build(
        provider_event_heartbeat=provider_event(False, False),
    )
    assert result["status"] == "OBSERVE_DEPLOY_READY"
    assert "provider_event_ingest_not_ready" in (
        result["activation"]["operational_observe"]["blockers"]
    )


def test_persistence_required_needs_ready_empiredb_probe():
    result = build(
        release_evidence=base_release(persistence_required=True),
        observer_preflight=preflight(persistence_required=True),
        empiredb_activation={
            "status": "BLOCKED",
            "roles_ready": False,
            "privileges_ready": False,
        },
    )
    assert result["status"] == "BLOCKED"
    blockers = result["activation"]["observe"]["blockers"]
    assert "empiredb_deliverability_migrations_not_applied" in blockers
    assert "empiredb_deliverability_roles_not_bound" in blockers


def test_fleet_limited_keeps_operational_observe_but_blocks_live_gate():
    result = build(
        fleet_readiness=fleet("LIMITED"),
        approval_state=approval(approved=True, exact=True),
    )
    assert result["status"] == "OBSERVE_OPERATIONAL"
    assert "fleet_readiness_not_ready" in (
        result["activation"]["live_send"]["blockers"]
    )


def test_all_authority_outputs_remain_false():
    result = build(
        approval_state=approval(approved=True, exact=True),
    )
    for key in (
        "database_activation_authorized",
        "service_activation_authorized",
        "dns_mutation_authorized",
        "provisioning_authorized",
        "send_authorized",
    ):
        assert result[key] is False
