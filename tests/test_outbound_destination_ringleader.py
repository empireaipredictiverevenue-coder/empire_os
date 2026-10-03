from empire_os.outbound_deliverability_ringleader import evaluate_ringleader


def sovereign_domain():
    return {
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


def test_ringleader_limits_unhealthy_destination_without_global_hold():
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
            "mx_family": "MICROSOFT",
            "microsoft_delivery": {
                "smtp_code": 421,
                "response": "temporary destination deferral",
            },
            "seed_placement": {"inbox_placement_rate": 0.97},
        },
    })

    assert result["posture"] == "LIMITED"
    assert result["hard_holds"] == []
    assert result["destination_reputation"]["scope"] == "recipient_mx_family"
    assert any(task["action"] == "THROTTLE_MX" for task in result["tasks"])
