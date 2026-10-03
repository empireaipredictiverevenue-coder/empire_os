from datetime import datetime, timezone

from empire_os.outbound_deliverability_service import build_rolling_health


class FakeProvider:
    def metrics(self, *, start, end, granularity="daily"):
        days = (end - start).days
        if days >= 30:
            return {
                "data": [{
                    "domain_name": "mail.example.com",
                    "sent": 112,
                    "delivered": 108,
                    "bounced": 4,
                    "bounced_permanent": 2,
                    "bounced_transient": 2,
                    "complained": 0,
                    "suppressed": 1,
                }]
            }
        return {
            "data": [{
                "domain_name": "mail.example.com",
                "sent": 10,
                "delivered": 10,
                "bounced": 0,
                "complained": 0,
            }]
        }


def test_rolling_health_uses_worst_window():
    result = build_rolling_health(
        FakeProvider(),
        now=datetime(2026, 10, 3, tzinfo=timezone.utc),
    )
    assert result["overall_health"] == "HOLD"
    assert result["windows"]["1d"]["health"] == "GREEN"
    assert result["windows"]["30d"]["health"] == "HOLD"
    assert result["inbox_placement"]["status"] == "separate_measurement_required"
