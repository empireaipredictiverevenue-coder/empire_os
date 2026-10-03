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


def test_fleet_scope_does_not_require_send_specific_recipient_evidence():
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
    })
    assert result["evaluation_scope"] == "FLEET"
    assert not any(
        task["action"] in {"VERIFY_RECIPIENTS", "MEASURE_PLACEMENT"}
        for task in result["tasks"]
    )


def test_invalid_scope_fails_closed():
    try:
        evaluate_ringleader({"evaluation_scope": "anything"})
    except ValueError as exc:
        assert str(exc) == "unsupported_ringleader_evaluation_scope"
    else:
        raise AssertionError("invalid scope should fail closed")
