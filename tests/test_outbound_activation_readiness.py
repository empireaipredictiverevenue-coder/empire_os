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
    }
    value.update(overrides)
    return value


def test_observe_can_be_ready_without_live_send_or_db_activation():
    result = evaluate_activation_readiness(observe_ready())
    assert result["observe"]["status"] == "READY"
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
    )
    evidence.update({
        "outbound_governor_live_ready": True,
        "recipient_verification_ready": True,
        "suppression_ready": True,
        "seed_placement_measured": True,
        "sender_pool_ready": True,
        "transport_policy_compatible": True,
        "founder_live_send_approved": False,
    })
    result = evaluate_activation_readiness(evidence)
    assert result["observe"]["status"] == "READY"
    assert result["live_send"]["status"] == "BLOCKED"
    assert "founder_live_send_approval_missing" in result["live_send"]["blockers"]
    assert result["live_send"]["send_authorized"] is False


def test_even_ready_for_explicit_approval_never_self_authorizes_send():
    evidence = observe_ready(
        empiredb_migrations_applied=True,
        empiredb_roles_bound=True,
        signed_evidence_required=True,
        signed_evidence_verified=True,
    )
    evidence.update({
        "outbound_governor_live_ready": True,
        "recipient_verification_ready": True,
        "suppression_ready": True,
        "seed_placement_measured": True,
        "sender_pool_ready": True,
        "transport_policy_compatible": True,
        "founder_live_send_approved": True,
    })
    result = evaluate_activation_readiness(evidence)
    assert result["live_send"]["status"] == "READY_FOR_EXPLICIT_APPROVAL"
    assert result["send_authorized"] is False
