from empire_os.outbound_warmup import (
    WarmupState,
    classify_pool,
    next_warmup_state,
)


def base(**overrides):
    value = {
        "state": "VERIFYING",
        "dns_ready": True,
        "placement_measured": False,
        "provider_policy_permits_use_case": True,
        "real_traffic_only": True,
        "bounce_rate": 0,
        "complaint_rate": 0,
        "deferrals": 0,
        "hard_bounces": 0,
        "daily_cap": 5,
    }
    value.update(overrides)
    return value


def test_verified_sender_enters_ramp_at_low_volume():
    result = next_warmup_state(base())
    assert result["state"] == "RAMPING"
    assert result["daily_cap"] == 5


def test_deferral_causes_backoff():
    result = next_warmup_state(base(state="RAMPING", daily_cap=20, deferrals=1))
    assert result["state"] == "THROTTLED"
    assert result["daily_cap"] == 10


def test_synthetic_warmup_is_rejected():
    result = next_warmup_state(base(real_traffic_only=False))
    assert result["state"] == "QUARANTINED"
    assert result["daily_cap"] == 0
    assert "synthetic_warmup_not_allowed" in result["holds"]


def test_pool_classification_is_stable_by_purpose():
    result = classify_pool({"kind": "RECIPIENT_MX", "purpose": "gmail"})
    assert result["isolation"] == "destination_rate_control"
