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
