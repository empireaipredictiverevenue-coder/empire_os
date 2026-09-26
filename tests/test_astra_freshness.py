from datetime import datetime, timezone

import pytest

from empire_os.astra_freshness import validate_astra_operational_freshness


def test_fresh_operational_evidence_is_accepted():
    result = validate_astra_operational_freshness(
        {"observed_at": "2026-09-19T17:00:00+00:00"},
        now=datetime(2026, 9, 19, 17, 10, tzinfo=timezone.utc),
        max_age_seconds=3600,
    )
    assert result.fresh is True
    assert result.reason == "operational_evidence_fresh"
    assert result.age_seconds == 600.0


def test_stale_operational_evidence_fails_closed():
    result = validate_astra_operational_freshness(
        {"observed_at": "2026-09-19T15:00:00+00:00"},
        now=datetime(2026, 9, 19, 17, 10, tzinfo=timezone.utc),
        max_age_seconds=3600,
    )
    assert result.fresh is False
    assert result.reason == "operational_evidence_stale"


def test_future_operational_evidence_fails_closed():
    result = validate_astra_operational_freshness(
        {"observed_at": "2026-09-19T17:20:00+00:00"},
        now=datetime(2026, 9, 19, 17, 10, tzinfo=timezone.utc),
        max_age_seconds=3600,
    )
    assert result.fresh is False
    assert result.reason == "operational_evidence_from_future"


def test_missing_observed_at_is_rejected():
    with pytest.raises(ValueError, match="observed_at is required"):
        validate_astra_operational_freshness(
            {},
            now=datetime(2026, 9, 19, 17, 10, tzinfo=timezone.utc),
        )


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_astra_operational_freshness(
            {"observed_at": "2026-09-19T17:00:00"},
            now=datetime(2026, 9, 19, 17, 10, tzinfo=timezone.utc),
        )
