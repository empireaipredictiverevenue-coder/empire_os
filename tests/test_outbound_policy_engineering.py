from empire_os.outbound_config_attestation import detect_configuration_drift
from empire_os.outbound_infrastructure_concentration import evaluate_concentration
from empire_os.outbound_policy_shadow import compare_policies


def test_critical_configuration_drift_holds():
    previous = {
        "domain": "mail.example.com",
        "nameservers": ["ns1.example"],
        "spf_record": "v=spf1 include:a -all",
        "dkim_selectors": ["s1"],
        "dmarc_record": "v=DMARC1; p=none",
        "mx_records": ["mx.example"],
        "transport_key": "a",
        "return_path_domain": "rp.example.com",
    }
    current = {**previous, "dkim_selectors": ["s2"]}
    result = detect_configuration_drift(previous, current)
    assert result["posture"] == "HOLD"
    assert "dkim_selectors" in result["critical_changes"]


def test_concentration_flags_single_transport_dependency():
    result = evaluate_concentration([
        {"enabled": True, "domain": "a", "transport_key": "t1", "ip_pool_key": "p1"},
        {"enabled": True, "domain": "b", "transport_key": "t1", "ip_pool_key": "p1"},
        {"enabled": True, "domain": "c", "transport_key": "t1", "ip_pool_key": "p1"},
    ])
    assert result["posture"] == "HIGH_CONCENTRATION"
    assert result["transport_hhi"] == 1.0


def test_shadow_policy_never_authorizes_promotion():
    def current(_):
        return {"posture": "READY", "mutation_authorized": False}

    def candidate(_):
        return {"posture": "LIMITED", "mutation_authorized": False}

    result = compare_policies(
        [{"x": 1}, {"x": 2}],
        current=current,
        candidate=candidate,
    )
    assert result["disagreements"] == 2
    assert result["candidate_stricter"] == 2
    assert result["promotion_authorized"] is False
