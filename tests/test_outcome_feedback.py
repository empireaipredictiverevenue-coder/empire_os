from empire_os.outcome_feedback import (
    feedback_to_revenue_features,
    summarize_outcomes,
)


def test_feedback_maps_real_outcomes_to_learning_features():
    row = {
        "fulfilment_order_id": "o1",
        "prospect_id": "p1",
        "buyer_id": "b1",
        "opportunity_id": "g1",
        "conversion_outcome": "won",
        "buyer_satisfaction": 4.5,
        "actual_revenue": True,
        "actual_revenue_cents": 10000,
        "actual_cost_cents": 3000,
        "gross_profit_cents": 7000,
    }
    value = feedback_to_revenue_features(row)
    assert value["replied"] is True
    assert value["engaged"] is True
    assert value["previous_purchase"] is True
    assert value["conversion_probability_target"] == 1.0
    assert value["gross_profit_cents"] == 7000


def test_summary_reports_conversion_revenue_profit_and_satisfaction():
    result = summarize_outcomes([
        {
            "conversion_outcome": "won",
            "buyer_satisfaction": 5,
            "actual_revenue_cents": 10000,
            "actual_cost_cents": 3000,
            "gross_profit_cents": 7000,
        },
        {
            "conversion_outcome": "lost",
            "buyer_satisfaction": 3,
            "actual_revenue_cents": 0,
            "actual_cost_cents": 500,
            "gross_profit_cents": -500,
        },
    ])
    assert result["orders"] == 2
    assert result["converted"] == 1
    assert result["conversion_rate"] == 0.5
    assert result["actual_revenue_cents"] == 10000
    assert result["gross_profit_cents"] == 6500
    assert result["gross_margin_rate"] == 0.65
    assert result["average_buyer_satisfaction"] == 4.0
