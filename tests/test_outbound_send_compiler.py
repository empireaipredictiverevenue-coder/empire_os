from empire_os.outbound_send_compiler import compile_send_plan


def opportunity(opportunity_id, value, mx="gmail"):
    return {
        "opportunity_id": opportunity_id,
        "approved": True,
        "recipient_verified": True,
        "suppressed": False,
        "predicted_value": value,
        "contact_confidence": 0.9,
        "deliverability_risk": 0.1,
        "conversation_probability": 0.5,
        "recipient_mx": mx,
    }


def test_compiler_requires_canary_and_respects_mx_cap():
    result = compile_send_plan(
        [
            opportunity("high", 1000),
            opportunity("low", 100),
        ],
        [
            {
                "sender_id": "s1",
                "domain": "outbound.example",
                "health": "GREEN",
                "enabled": True,
                "remaining_capacity": 10,
            }
        ],
        {"gmail": 1},
        total_capacity=2,
        canary_size=1,
    )
    assert result["posture"] == "CANARY_REQUIRED"
    assert result["canary"][0]["opportunity_id"] == "high"
    assert result["remainder"] == []
    assert any(
        row["opportunity_id"] == "low"
        and row["reason"] == "recipient_mx_capacity_exhausted"
        for row in result["unallocated"]
    )
    assert result["mutation_authorized"] is False


def test_compiler_cannot_use_unhealthy_sender():
    result = compile_send_plan(
        [opportunity("a", 1000)],
        [{
            "sender_id": "s1",
            "domain": "outbound.example",
            "health": "HOLD",
            "enabled": True,
            "remaining_capacity": 10,
        }],
        {"gmail": 10},
        total_capacity=1,
        canary_size=1,
    )
    assert result["posture"] == "HOLD"
