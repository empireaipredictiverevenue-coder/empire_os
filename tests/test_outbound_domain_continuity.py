from datetime import date

from empire_os.outbound_domain_continuity import evaluate_domain_continuity


TODAY = date(2026, 10, 3)


def base(**overrides):
    value = {
        "domain": "outbound.example.com",
        "purpose": "prospecting",
        "days_to_expiry": 365,
        "registrar_owned": True,
        "dns_owned": True,
        "registrar_lock": True,
        "auto_renew": True,
        "nameserver_drift": False,
        "dnssec_valid": True,
        "dkim_selector_count": 1,
        "dmarc_rua_owned": True,
        "is_primary_brand_domain": False,
    }
    value.update(overrides)
    return value


def test_healthy_domain_has_no_continuity_warning():
    result = evaluate_domain_continuity(base(), today=TODAY)
    assert result["posture"] == "HEALTHY"


def test_nameserver_drift_is_hold():
    result = evaluate_domain_continuity(
        base(nameserver_drift=True),
        today=TODAY,
    )
    assert result["posture"] == "HOLD"
    assert "unexpected_nameserver_drift" in result["hard_holds"]


def test_expiry_inside_two_weeks_is_hold():
    result = evaluate_domain_continuity(
        base(days_to_expiry=7),
        today=TODAY,
    )
    assert result["posture"] == "HOLD"


def test_primary_brand_prospecting_warns_blast_radius():
    result = evaluate_domain_continuity(
        base(is_primary_brand_domain=True),
        today=TODAY,
    )
    assert "primary_brand_reputation_blast_radius" in result["warnings"]
