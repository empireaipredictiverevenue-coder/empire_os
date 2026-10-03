from empire_os.outbound_deliverability_ringleader import evaluate_ringleader
from empire_os.outbound_domain_sovereignty import evaluate_domain_sovereignty


def sovereign_domain(**overrides):
    value = {
        "domain": "outbound.example.com",
        "purpose": "prospecting",
        "registrar_account_owned": True,
        "dns_authority_owned": True,
        "mfa_enabled": True,
        "domain_lock_enabled": True,
        "auto_renew_enabled": True,
        "dns_zone_exported": True,
        "dmarc_rua_empire_owned": True,
        "provider_portable_sender_identity": True,
        "recovery_path_verified": True,
        "uses_primary_brand_root": False,
        "provider_managed_dkim_only": False,
        "single_transport_dependency": False,
    }
    value.update(overrides)
    return value


def test_full_domain_control_is_sovereign():
    result = evaluate_domain_sovereignty(sovereign_domain())
    assert result["status"] == "SOVEREIGN"
    assert result["score"] == 100


def test_missing_registrar_control_is_hold():
    result = evaluate_domain_sovereignty(
        sovereign_domain(registrar_account_owned=False)
    )
    assert result["status"] == "HOLD"


def test_primary_brand_outreach_is_flagged_for_reputation_exposure():
    result = evaluate_domain_sovereignty(
        sovereign_domain(uses_primary_brand_root=True)
    )
    assert "primary_brand_reputation_exposure" in result["warnings"]


def test_ringleader_stops_on_deliverability_hold():
    result = evaluate_ringleader({
        "deliverability": {"health": "HOLD"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
    })
    assert result["posture"] == "HOLD"
    assert result["tasks"][0]["action"] == "STOP_SEND"
    assert result["mutation_authorized"] is False


def test_ringleader_requests_placement_measurement_before_scale():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": False},
        "domain_sovereignty": sovereign_domain(),
    })
    assert result["posture"] == "LIMITED"
    assert any(task["action"] == "MEASURE_PLACEMENT" for task in result["tasks"])


def test_ringleader_holds_provider_policy_mismatch():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": False,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
    })
    assert result["posture"] == "HOLD"
    assert any(task["action"] == "MIGRATE_TRANSPORT" for task in result["tasks"])


def test_ringleader_holds_when_reputation_credit_is_exhausted():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "reputation_escrow": {
            "state": {"credit": 20},
            "observation": {"complaints": 1},
        },
    })
    assert result["posture"] == "HOLD"
    assert "reputation_credit_exhausted" in result["hard_holds"]


def test_ringleader_escalates_deeper_verification_for_catch_all():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "verification_context": {
            "predicted_value": 10000,
            "contact_confidence": 0.8,
            "historical_domain_bounce_rate": 0.01,
            "catch_all": True,
        },
    })
    assert result["posture"] == "LIMITED"
    assert result["verification_depth"]["outcome"] == "ESCALATE"
    assert any(task["action"] == "VERIFY_RECIPIENTS" for task in result["tasks"])


def test_ringleader_explains_shift_and_plans_remediation():
    result = evaluate_ringleader({
        "deliverability": {"health": "AMBER"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "metric_shift": {
            "before": {"bounce_rate": 0.01},
            "after": {"bounce_rate": 0.04},
            "changes": [{
                "kind": "recipient_source_changed",
                "change_id": "source-change-1",
                "evidence_strength": 0.9,
                "temporal_proximity": 1.0,
                "affected_metrics": ["bounce_rate"],
            }],
        },
    })
    assert result["root_cause"]["metric_shift"]["shift_detected"] is True
    assert result["remediation"]["posture"] == "REMEDIATE"
    assert all(
        task["mutation_authorized"] is False
        for task in result["remediation"]["tasks"]
    )


def test_ringleader_blocks_cross_agent_contact_pressure():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "contact_pressure": {
            "candidate": {
                "person_key": "person:a",
                "company_key": "company:x",
            },
            "history": [{
                "person_key": "person:a",
                "company_key": "company:x",
                "occurred_at": "2026-10-02T12:00:00+00:00",
            }],
        },
    })
    assert result["posture"] == "HOLD"
    assert "contact_pressure_hold" in result["hard_holds"]


def test_ringleader_blocks_sender_thread_hopping():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "sender_affinity": {
            "is_existing_thread": True,
            "prior_sender_id": "s1",
            "prior_sender_health": "GREEN",
            "proposed_sender_id": "s2",
        },
    })
    assert result["posture"] == "HOLD"
    assert "sender_affinity_hold" in result["hard_holds"]


def test_ringleader_holds_exhausted_reputation_slo():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "reputation_slo": {
            "sent": 100,
            "bounces": 3,
            "complaints": 0,
            "seed_tests": 10,
            "spam_placements": 0,
        },
    })
    assert result["posture"] == "HOLD"
    assert "reputation_error_budget_exhausted" in result["hard_holds"]


def test_ringleader_holds_domain_continuity_failure():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "domain_continuity": {
            "domain": "outbound.example.com",
            "purpose": "prospecting",
            "days_to_expiry": 365,
            "registrar_owned": True,
            "dns_owned": True,
            "registrar_lock": True,
            "auto_renew": True,
            "nameserver_drift": True,
            "dnssec_valid": True,
            "dkim_selector_count": 1,
            "dmarc_rua_owned": True,
            "is_primary_brand_domain": False,
        },
    })
    assert result["posture"] == "HOLD"
    assert "domain_continuity_hold" in result["hard_holds"]


def test_ringleader_preemptively_throttles_worsening_reputation_forecast():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "health_history": [
            {"bounce_rate": 0.010, "inbox_placement_rate": 0.97},
            {"bounce_rate": 0.018, "inbox_placement_rate": 0.96},
            {"bounce_rate": 0.024, "inbox_placement_rate": 0.95},
        ],
    })
    assert result["posture"] == "LIMITED"
    assert result["health_forecast"]["posture"] == "PREEMPTIVE_THROTTLE"
    assert any(
        task["reason"] == "forecast_threshold_breach_risk"
        for task in result["tasks"]
    )


def test_ringleader_holds_unconsented_consumer_mailbox_prospecting():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "recipient_domain_policy": {
            "recipient_domain": "gmail.com",
            "traffic_class": "prospecting",
            "consented": False,
            "existing_relationship": False,
            "person_company_bound": True,
        },
    })
    assert result["posture"] == "HOLD"
    assert "recipient_domain_policy_hold" in result["hard_holds"]


def test_ringleader_limits_yahoo_destination_on_transient_deferral():
    result = evaluate_ringleader({
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "recipient_quality": {"verified": True},
        "placement": {"measured": True},
        "domain_sovereignty": sovereign_domain(),
        "destination_reputation": {
            "mx_family": "YAHOO",
            "yahoo_delivery": {
                "smtp_code": 421,
                "response": "421 temporary deferral",
            },
            "seed_placement": {"inbox_placement_rate": 0.97},
        },
    })
    assert result["posture"] == "LIMITED"
    assert result["destination_reputation"]["posture"] == "LIMIT_DESTINATION"


def test_ringleader_holds_critical_sender_configuration_drift():
    result = evaluate_ringleader({
        "evaluation_scope": "FLEET",
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "domain_sovereignty": sovereign_domain(),
        "configuration_attestation": {
            "previous": {
                "domain": "mail.example.com",
                "nameservers": ["ns1.example"],
                "spf_record": "v=spf1 include:a -all",
                "dkim_selectors": ["s1"],
                "dmarc_record": "v=DMARC1; p=none",
                "transport_key": "t1",
                "return_path_domain": "rp.example.com",
            },
            "current": {
                "domain": "mail.example.com",
                "nameservers": ["ns1.example"],
                "spf_record": "v=spf1 include:a -all",
                "dkim_selectors": ["unexpected"],
                "dmarc_record": "v=DMARC1; p=none",
                "transport_key": "t1",
                "return_path_domain": "rp.example.com",
            },
        },
    })
    assert result["posture"] == "HOLD"
    assert "critical_configuration_drift" in result["hard_holds"]


def test_ringleader_limits_high_infrastructure_concentration():
    result = evaluate_ringleader({
        "evaluation_scope": "FLEET",
        "deliverability": {"health": "GREEN"},
        "provider_policy_permits_use_case": True,
        "authentication": {
            "spf_aligned": True,
            "dkim_aligned": True,
            "dmarc_valid": True,
            "tls_ready": True,
        },
        "domain_sovereignty": sovereign_domain(),
        "infrastructure_concentration": [
            {"enabled": True, "domain": "a", "transport_key": "t1", "ip_pool_key": "p1"},
            {"enabled": True, "domain": "b", "transport_key": "t1", "ip_pool_key": "p1"},
            {"enabled": True, "domain": "c", "transport_key": "t1", "ip_pool_key": "p1"},
        ],
    })
    assert result["posture"] == "LIMITED"
    assert result["infrastructure_concentration"]["posture"] == "HIGH_CONCENTRATION"
    assert any(task["action"] == "REDUCE_CONCENTRATION" for task in result["tasks"])
