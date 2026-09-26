from datetime import datetime, timezone

from empire_os.search_intelligence.content_decay import evaluate_content_decay


def test_unknown_history_stays_unknown():
    result = evaluate_content_decay([])
    assert result.refresh_required is None
    assert result.recommendation is None


def test_observed_decline_and_staleness_trigger_review():
    result = evaluate_content_decay(
        [
            {"impressions": 1000, "clicks": 100, "ctr": 0.10, "average_position": 4, "conversions": 20},
            {"impressions": 600, "clicks": 50, "ctr": 0.05, "average_position": 7, "conversions": 10},
        ],
        last_modified_at="2024-01-01T00:00:00+00:00",
        as_of=datetime(2026, 9, 18, tzinfo=timezone.utc),
    )
    assert result.refresh_required is True
    assert "falling_impressions" in result.reasons
    assert "ranking_deterioration" in result.reasons
    assert "stale_content" in result.reasons
    assert result.execution_allowed is False
