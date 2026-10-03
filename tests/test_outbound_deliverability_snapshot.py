from empire_os.outbound_deliverability_snapshot import build_deliverability_snapshot


def test_snapshot_marks_current_like_bounce_rate_as_hold():
    result = build_deliverability_snapshot(
        [
            {
                "domain": "mail.example.com",
                "sent": 104,
                "delivered": 100,
                "bounced": 4,
                "bounced_permanent": 2,
                "bounced_transient": 2,
                "complained": 0,
                "suppressed": 1,
                "failed": 0,
                "delivery_delayed": 1,
            },
            {
                "domain": "example.com",
                "sent": 8,
                "delivered": 8,
                "bounced": 0,
                "bounced_permanent": 0,
                "bounced_transient": 0,
                "complained": 0,
                "suppressed": 0,
                "failed": 0,
                "delivery_delayed": 0,
            },
        ]
    )
    assert result["health"] == "HOLD"
    assert round(result["bounce_rate"], 4) == 0.0357
    assert result["complaint_rate"] == 0
    assert result["inbox_placement_rate"] is None


def test_clean_snapshot_is_green():
    result = build_deliverability_snapshot(
        [{"domain": "example.com", "sent": 100, "delivered": 100}]
    )
    assert result["health"] == "GREEN"


def test_two_percent_bounce_is_amber():
    result = build_deliverability_snapshot(
        [{"domain": "example.com", "sent": 100, "delivered": 98, "bounced": 2}]
    )
    assert result["health"] == "AMBER"
