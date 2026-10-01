from datetime import datetime, timezone

import pytest

from empire_os.commercial_opportunity_decay import (
    assess_opportunity_decay,
)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def test_recent_revalidation_keeps_old_opportunity_active():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:1",
        "observed_at": "2026-08-01T00:00:00+00:00",
        "revalidated_at": "2026-10-01T11:30:00+00:00",
        "freshness_window_seconds": 86400,
        "buyer_need_until": "2026-10-10T00:00:00+00:00",
        "evidence_refs": ["permit:1", "revalidation:1"],
    }, as_of=NOW)

    assert result.state == "ACTIVE"
    assert result.recency_factor_candidate == 1.0
    assert result.actual_revenue is False


def test_explicit_hard_expiry_has_precedence():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:2",
        "revalidated_at": "2026-10-01T11:30:00+00:00",
        "freshness_window_seconds": 86400,
        "buyer_need_until": "2026-09-30T23:59:00+00:00",
        "evidence_refs": ["buyer-need:expired"],
    }, as_of=NOW)

    assert result.state == "EXPIRED"
    assert result.expired_fields == ("buyer_need_until",)
    assert result.recency_factor_candidate == 0.0


def test_stale_freshness_does_not_invent_numeric_decay():
    result = assess_opportunity_decay({
        "opportunity_key": "market:3",
        "revalidated_at": "2026-09-29T12:00:00+00:00",
        "freshness_window_seconds": 86400,
        "evidence_refs": ["market-snapshot:3"],
    }, as_of=NOW)

    assert result.state == "STALE"
    assert result.stale_by_seconds == 86400
    assert result.recency_factor_candidate is None


def test_created_age_without_temporal_contract_is_unknown():
    result = assess_opportunity_decay({
        "opportunity_key": "legacy:4",
        "observed_at": "2025-01-01T00:00:00+00:00",
        "evidence_refs": ["legacy:4"],
    }, as_of=NOW)

    assert result.state == "UNKNOWN"
    assert "temporal_validity_contract_missing" in result.blockers


def test_missing_evidence_refs_fails_closed():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:5",
        "revalidated_at": "2026-10-01T11:00:00+00:00",
        "freshness_window_seconds": 86400,
    }, as_of=NOW)

    assert result.state == "UNKNOWN"
    assert result.recency_factor_candidate is None
    assert "evidence_refs_missing" in result.blockers


def test_missing_validation_for_freshness_policy_is_unknown():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:6",
        "freshness_window_seconds": 86400,
        "evidence_refs": ["source-policy:permit"],
    }, as_of=NOW)

    assert result.state == "UNKNOWN"
    assert "validation_timestamp_missing" in result.blockers


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        assess_opportunity_decay({
            "opportunity_key": "permit:7",
            "observed_at": "2026-10-01T10:00:00",
            "freshness_window_seconds": 86400,
            "evidence_refs": ["permit:7"],
        }, as_of=NOW)


def test_candidate_never_grants_execution_authority():
    result = assess_opportunity_decay({
        "opportunity_key": "permit:8",
        "source_expires_at": "2026-10-05T00:00:00+00:00",
        "evidence_refs": ["source:8"],
    }, as_of=NOW)

    assert result.state == "ACTIVE"
    assert result.recommendation_only is True
    assert result.allocation_authorized is False
    assert result.outreach_authorized is False
    assert result.payment_authorized is False
    assert result.execution_authority == "none"
