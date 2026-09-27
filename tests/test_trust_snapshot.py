from empire_os.trust_snapshot import build_trust_snapshot


def test_security_findings_block_public_trust_readiness():
    result = build_trust_snapshot(
        ops_control={
            "healthy": True,
            "observed_at": "2026-09-21T10:00:00+00:00",
        },
        security_audit={
            "findings": {
                "rls_disabled_in_public": 2,
                "security_definer_view": 1,
            }
        },
        commercial_loop={"stages": []},
    )
    security = next(
        row for row in result["assessment"]["dimensions"]
        if row["key"] == "security_privacy"
    )
    assert security["state"] == "failed"
    assert result["assessment"]["public_trust_center_ready"] is False
    assert result["publishing_authority"] is False


def test_payment_verification_requires_observed_payment_stage():
    result = build_trust_snapshot(
        ops_control={},
        security_audit={},
        commercial_loop={
            "stages": [
                {"stage": "bsc_usdt_payment", "observed": True},
            ]
        },
    )
    payment = next(
        row for row in result["assessment"]["dimensions"]
        if row["key"] == "payment_verification"
    )
    assert payment["state"] == "verified"
    assert payment["evidence_refs"]


def test_unknown_customer_reference_stays_unknown():
    result = build_trust_snapshot(
        ops_control={},
        security_audit={},
        commercial_loop={"stages": []},
    )
    reference = next(
        row for row in result["assessment"]["dimensions"]
        if row["key"] == "customer_references"
    )
    assert reference["state"] == "unknown"
