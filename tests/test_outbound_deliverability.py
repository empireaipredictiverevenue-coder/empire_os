from empire_os.outbound_deliverability import (
    DeliverabilityPolicy,
    evaluate_sender_health,
    lint_first_touch,
)


def healthy(**overrides):
    value = {
        "provider_policy_permits_use_case": True,
        "spf_aligned": True,
        "dkim_aligned": True,
        "dmarc_valid": True,
        "tls_ready": True,
        "recipient_verified": True,
        "bounce_rate": 0.01,
        "complaint_rate": 0.0,
        "daily_cap": 30,
        "volume_spike_ratio": 1.0,
    }
    value.update(overrides)
    return value


def test_healthy_sender_is_ready():
    result = evaluate_sender_health(healthy())
    assert result["decision"] == "READY"


def test_provider_policy_mismatch_is_hard_hold():
    result = evaluate_sender_health(
        healthy(provider_policy_permits_use_case=False)
    )
    assert result["decision"] == "HOLD"
    assert "provider_policy_prohibits_use_case" in result["hard_holds"]


def test_internal_bounce_ceiling_is_stricter_than_provider_shutdown_limit():
    result = evaluate_sender_health(healthy(bounce_rate=0.0385))
    assert result["decision"] == "HOLD"
    assert "bounce_rate_above_internal_limit" in result["hard_holds"]


def test_percentage_rates_are_normalized():
    result = evaluate_sender_health(healthy(bounce_rate=1.5))
    assert result["decision"] == "READY"
    assert result["observed"]["bounce_rate"] == 0.015


def test_cap_above_40_is_blocked():
    result = evaluate_sender_health(healthy(daily_cap=41))
    assert result["decision"] == "HOLD"
    assert "daily_cap_above_internal_limit" in result["hard_holds"]


def test_sudden_volume_spike_is_blocked():
    result = evaluate_sender_health(healthy(volume_spike_ratio=2.0))
    assert result["decision"] == "HOLD"
    assert "sudden_volume_spike" in result["hard_holds"]


def test_unverified_authentication_escalates():
    result = evaluate_sender_health(healthy(dkim_aligned=None))
    assert result["decision"] == "ESCALATE"
    assert "dkim_alignment_unverified" in result["evidence_holds"]


def test_fake_reply_prefix_is_blocked():
    result = lint_first_touch(
        {
            "subject": "Re: quick question",
            "body_text": "Hello",
            "from": "phil@example.com",
            "is_reply": False,
        }
    )
    assert "deceptive_reply_or_forward_prefix" in result["hard_holds"]


def test_link_heavy_first_touch_is_flagged():
    result = lint_first_touch(
        {
            "subject": "Question",
            "body_text": "See https://one.example and https://two.example",
            "from": "phil@example.com",
        }
    )
    assert "reduce_first_touch_links" in result["recommendations"]


def test_policy_is_configurable_but_defaults_fail_closed():
    result = evaluate_sender_health(
        healthy(bounce_rate=0.03),
        policy=DeliverabilityPolicy(max_bounce_rate=0.04),
    )
    assert result["decision"] == "READY"
