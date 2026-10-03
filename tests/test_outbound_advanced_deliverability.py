from empire_os.outbound_deliverability_twin import simulate_batch
from empire_os.outbound_mx_pacing import evaluate_mx_pool
from empire_os.outbound_reputation_budget import allocate_reputation_budget
from empire_os.outbound_canary import evaluate_canary


def test_twin_requires_canary_for_moderate_risk():
    result = simulate_batch(
        {
            "sent_7d": 100,
            "bounce_rate": 0.01,
            "complaint_rate": 0,
            "deferral_rate": 0,
            "placement_rate": 0.95,
            "auth_ready": True,
        },
        {"count": 30, "recipient_verified_fraction": 1.0},
    )
    assert result["posture"] in {"ALLOW_BOUNDED", "CANARY_ONLY"}
    assert result["canary_size"] >= 3


def test_twin_holds_unverified_high_volume_batch():
    result = simulate_batch(
        {
            "sent_7d": 20,
            "bounce_rate": 0.03,
            "complaint_rate": 0,
            "deferral_rate": 0.08,
            "auth_ready": False,
        },
        {"count": 50, "recipient_verified_fraction": 0.50},
    )
    assert result["posture"] == "HOLD"


def test_mx_pool_backs_off_on_deferrals():
    result = evaluate_mx_pool({"daily_cap": 20, "deferral_rate": 0.10})
    assert result["state"] == "BACKOFF"
    assert result["daily_cap"] == 10


def test_reputation_budget_never_selects_unapproved():
    result = allocate_reputation_budget(
        [
            {
                "opportunity_id": "a",
                "approved": True,
                "recipient_verified": True,
                "suppressed": False,
                "predicted_value": 1000,
                "contact_confidence": 0.9,
                "deliverability_risk": 0.1,
                "conversation_probability": 0.5,
            },
            {
                "opportunity_id": "b",
                "approved": False,
                "recipient_verified": True,
                "suppressed": False,
                "predicted_value": 100000,
                "contact_confidence": 1,
                "deliverability_risk": 0,
                "conversation_probability": 1,
            },
        ],
        capacity=1,
    )
    assert result["selected"][0]["opportunity_id"] == "a"
    assert result["held"][0]["opportunity_id"] == "b"


def test_canary_stops_on_complaint():
    result = evaluate_canary({"sent": 5, "complaints": 1})
    assert result["decision"] == "HOLD"
