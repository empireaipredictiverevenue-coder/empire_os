from empire_os.opportunity_value_scoring import (
    build_opportunity_value_snapshot,
)


def _available(key, score):
    return {
        "opportunity_key": key,
        "opportunity_class": "market_research",
        "quant_input_evidence": {
            "predictive_intelligence": {
                "candidate_probability_is_product_cohort_baseline": True,
            }
        },
        "decision_packet": {
            "status": "AVAILABLE",
            "missing_fields": [],
            "expected_economics": {
                "expected_revenue_cents": 120000,
                "expected_cost_cents": 50000,
                "expected_gross_profit_cents": 70000,
            },
            "risk_adjusted": {
                "risk_adjusted_score": score,
                "risk_penalty_cents": 20000,
                "time_discount": 0.8,
                "confidence": 0.7,
            },
            "downside_simulation": {
                "p05_gross_profit_cents": -10000,
                "p50_gross_profit_cents": 65000,
                "p95_gross_profit_cents": 130000,
                "probability_negative_gross_profit": 0.1,
            },
            "prediction_only": True,
            "actual_revenue": False,
        },
    }


def test_value_projection_reuses_quant_economics_and_ranks():
    result = build_opportunity_value_snapshot({
        "items": [
            _available("opp-low", 10000),
            _available("opp-high", 30000),
        ]
    })

    assert result["value_available_count"] == 2
    assert result["items"][0]["opportunity_key"] == "opp-high"
    assert result["items"][0]["rank"] == 1
    assert result["items"][1]["rank"] == 2
    assert result["items"][0]["expected_gross_profit_cents"] == 70000
    assert result["new_scoring_model_introduced"] is False
    assert result["prediction_only"] is True
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_missing_quant_packet_stays_unavailable():
    result = build_opportunity_value_snapshot({
        "items": [{
            "opportunity_key": "opp-unknown",
            "decision_packet": {
                "status": "UNAVAILABLE",
                "missing_fields": [
                    "probability_success",
                    "time_to_revenue_days",
                ],
            },
        }]
    })

    row = result["items"][0]
    assert result["value_available_count"] == 0
    assert result["value_unavailable_count"] == 1
    assert row["status"] == "UNAVAILABLE"
    assert row["risk_adjusted_score"] is None
    assert row["rank"] is None
    assert row["missing_fields"] == [
        "probability_success",
        "time_to_revenue_days",
    ]


def test_incomplete_available_packet_fails_closed():
    result = build_opportunity_value_snapshot({
        "items": [{
            "opportunity_key": "opp-bad",
            "decision_packet": {
                "status": "AVAILABLE",
                "expected_economics": {
                    "expected_revenue_cents": 100000,
                },
                "risk_adjusted": {},
            },
        }]
    })

    row = result["items"][0]
    assert row["status"] == "UNAVAILABLE"
    assert "expected_cost_cents" in row["missing_fields"]
    assert "risk_adjusted_score" in row["missing_fields"]
    assert result["actual_revenue"] is False
