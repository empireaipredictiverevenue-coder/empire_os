"""One-shot storm source observation must fail closed and never write production."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.observe_nsh_storm_source_20261021 import (
    canonical_rows_from_payload, observe, stage_snapshot, STAGING_ROOT,
    MAX_SOURCE_ITEMS, MAX_QUALIFIED_EVENTS,
)

NOW = datetime(2026, 10, 21, 15, 10, tzinfo=timezone.utc)


def sample(event="Severe Thunderstorm Warning"):
    return {"type": "FeatureCollection", "updated": NOW.isoformat(), "features": [{
        "type": "Feature",
        "id": "https://api.weather.gov/alerts/urn:oid:test-storm",
        "geometry": None,
        "properties": {
            "event": event, "sent": (NOW - timedelta(minutes=5)).isoformat(),
            "expires": (NOW + timedelta(minutes=45)).isoformat(),
            "areaDesc": "Test County", "status": "Actual",
            "messageType": "Alert", "category": "Met",
            "severity": "Severe", "certainty": "Likely",
            "urgency": "Immediate", "headline": "Test-only NWS warning",
        }
    }]}


def test_genuine_allowlisted_source_event_reuses_canonical_adapters():
    events, rejected, eligible = canonical_rows_from_payload(sample(), checked_at=NOW)
    assert eligible == 1
    assert len(events) == 1 and rejected == []
    assert events[0]["tenant_id"] == "empire-internal"
    assert events[0]["event_type"] == "Severe Thunderstorm Warning"
    assert events[0]["truth_scope"] == "SOURCE_RECORD_ONLY"
    assert events[0]["geographic_footprint"]["location"]["precision"] == "TEXT_AREA_ONLY"


def test_non_warning_source_is_not_converted_to_commercial_evidence():
    status, snapshot = observe(sample("Special Weather Statement"), now=NOW)
    assert status["tracked_warning_types_eligible"] == 0
    assert snapshot["candidate_count"] == 0
    assert status["damage_verified"] is False
    assert status["buyer_intent_verified"] is False
    assert status["outbound_sent"] is False


def test_real_warning_still_does_not_prove_damage_or_buyer_intent():
    status, snapshot = observe(sample(), now=NOW)
    assert status["source_events_valid"] == 1
    assert status["candidate_count"] == 0
    assert snapshot["automatic_external_execution_allowed"] is False
    assert snapshot["payment_authority"] == "none"
    assert snapshot["commercial_authority"] == "none"


def test_bounded_source_collection():
    with pytest.raises(ValueError, match="nws_features_unbounded_or_missing"):
        canonical_rows_from_payload({
            "type": "FeatureCollection", "features": [None] * (MAX_SOURCE_ITEMS + 1)
        }, checked_at=NOW)
    with pytest.raises(ValueError, match="eligible_event_batch_limit"):
        entry = sample()["features"][0]
        canonical_rows_from_payload({
            "type": "FeatureCollection", "features": [entry] * (MAX_QUALIFIED_EVENTS + 1)
        }, checked_at=NOW)


def test_staging_cannot_be_redirected_to_production(tmp_path):
    with pytest.raises(ValueError, match="only_dedicated_observation_staging_allowed"):
        stage_snapshot(tmp_path, {"mode": "OBSERVE"})
    with pytest.raises(ValueError, match="only_dedicated_observation_staging_allowed"):
        stage_snapshot(Path("/srv/empire_os"), {"mode": "OBSERVE"})
