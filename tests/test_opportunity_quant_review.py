from empire_os.opportunity_quant_review import build_quant_review


def test_quant_review_keeps_missing_probability_unknown():
    intake = {
        "items": [{
            "opportunity_key": "market:roofing:denver",
            "opportunity_class": "market_research",
            "factory_ready": False,
            "normalization": {
                "quant_inputs": {
                    "conditional_revenue_cents": 150000,
                    "fixed_cost_cents": 30000,
                    "success_cost_cents": 30000,
                    "revenue_low_cents": 150000,
                    "revenue_high_cents": 150000,
                    "success_cost_low_cents": 30000,
                    "success_cost_high_cents": 30000,
                    "probability_success": None,
                    "uncertainty": None,
                    "time_to_revenue_days": None,
                    "confidence": None,
                },
                "quant_input_evidence": {
                    "basis": "verified_commercial_product_policy_scenario",
                    "actual_revenue": False,
                },
            },
        }]
    }
    result = build_quant_review(intake)
    packet = result["items"][0]["decision_packet"]
    assert packet["status"] == "UNAVAILABLE"
    assert "probability_success" in packet["missing_fields"]
    assert result["available_decision_packet_count"] == 0
    assert result["capital_execution"] is False


def test_quant_review_builds_packet_when_all_inputs_exist():
    intake = {
        "items": [{
            "opportunity_key": "market:roofing:denver",
            "opportunity_class": "market_research",
            "factory_ready": True,
            "normalization": {
                "quant_inputs": {
                    "probability_success": 0.5,
                    "conditional_revenue_cents": 150000,
                    "fixed_cost_cents": 30000,
                    "success_cost_cents": 30000,
                    "revenue_low_cents": 130000,
                    "revenue_high_cents": 160000,
                    "success_cost_low_cents": 25000,
                    "success_cost_high_cents": 35000,
                    "uncertainty": 0.3,
                    "time_to_revenue_days": 21,
                    "confidence": 0.7,
                },
            },
        }]
    }
    result = build_quant_review(intake, trials=500, seed=3)
    packet = result["items"][0]["decision_packet"]
    assert packet["status"] == "AVAILABLE"
    assert result["available_decision_packet_count"] == 1
    assert packet["actual_revenue"] is False
    assert result["execution_authority"] == "none"
