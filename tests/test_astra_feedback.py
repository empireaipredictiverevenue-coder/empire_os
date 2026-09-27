from empire_os.astra_feedback import (
    build_outcome_calibration,
    buyer_history_features,
)


def test_empty_feedback_is_not_ready():
    calibration = build_outcome_calibration([])

    assert calibration.sample_size == 0
    assert calibration.converted == 0
    assert calibration.actual_revenue_cents == 0
    assert calibration.gross_profit_cents == 0
    assert calibration.calibration_ready is False
    assert calibration.calibration_reason == "insufficient_real_outcome_samples"


def test_real_threshold_becomes_ready():
    rows = []
    for index in range(20):
        won = index < 5
        rows.append({
            "conversion_outcome": "won" if won else "lost",
            "actual_revenue_cents": 1000 if won else 0,
            "actual_cost_cents": 400 if won else 0,
            "gross_profit_cents": 600 if won else 0,
            "buyer_satisfaction": 4.5 if won else None,
            "previous_purchase": won,
        })

    calibration = build_outcome_calibration(rows)

    assert calibration.sample_size == 20
    assert calibration.converted == 5
    assert calibration.actual_revenue_cents == 5000
    assert calibration.actual_cost_cents == 2000
    assert calibration.gross_profit_cents == 3000
    assert calibration.conversion_rate == 0.25
    assert calibration.gross_margin_rate == 0.6
    assert calibration.average_buyer_satisfaction == 4.5
    assert calibration.repeat_purchase_orders == 5
    assert calibration.calibration_ready is True
    assert calibration.calibration_reason == "real_outcome_threshold_met"


def test_negative_margin_uses_verified_gross_profit():
    rows = [
        {"conversion_outcome": "won", "gross_profit_cents": -125},
        {"conversion_outcome": "won", "gross_profit_cents": 300},
        {"conversion_outcome": "lost", "gross_profit_cents": -1},
    ]

    calibration = build_outcome_calibration(
        rows,
        min_samples=1,
        min_conversions=1,
    )

    assert calibration.negative_margin_orders == 2


def test_buyer_history_uses_observed_fields_only():
    features = buyer_history_features({
        "conversion_outcome": "booked",
        "previous_purchase": False,
        "buyer_satisfaction": 4.25,
        "gross_profit_cents": "875",
        "fulfilment_order_id": "order-1",
        "prospect_id": "prospect-1",
        "buyer_id": "buyer-1",
        "opportunity_id": "opportunity-1",
    })

    assert features["replied"] is True
    assert features["engaged"] is True
    assert features["previous_purchase"] is False
    assert features["historical_buyer_satisfaction"] == 4.25
    assert features["historical_gross_profit_cents"] == 875
    assert features["buyer_id"] == "buyer-1"


def test_missing_history_remains_unknown():
    features = buyer_history_features({})

    assert features["replied"] is None
    assert features["engaged"] is None
    assert features["previous_purchase"] is None
    assert features["historical_buyer_satisfaction"] is None
    assert features["historical_gross_profit_cents"] is None
