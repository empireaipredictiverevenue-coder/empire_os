import json
from datetime import datetime, timezone

from empire_os.lead_sources import LeadCandidate
from empire_os.source_health_observer import (
    atomic_write_observation,
    observe_source_health,
)


NOW = datetime(2026, 9, 19, 22, 50, tzinfo=timezone.utc)


def business(name="Observed Roofing LLC"):
    return LeadCandidate(
        name=name,
        phone="512-555-0101",
        niche="roofing",
        metro="Austin, TX",
        state="TX",
        source="overpass_osm",
        url="https://www.openstreetmap.org/node/123",
        raw={"osm_id": 123},
    )


def test_source_can_be_healthy_while_canonical_ingest_stays_disabled():
    result = observe_source_health(
        source="overpass",
        metro="Austin, TX",
        runner=lambda _metro: iter([business()]),
        canonical_ingest_authorized=False,
        canonical_ingest_scheduled=False,
        now=NOW,
    )
    assert result.endpoint_healthy is True
    assert result.candidates_seen == 1
    assert result.quality_accepted == 1
    assert result.end_to_end_healthy is False
    assert "canonical_ingest_not_authorized" in result.blockers
    assert "canonical_ingest_not_scheduled" in result.blockers
    assert result.canonical_writes is False
    assert result.side_effects == "none"


def test_end_to_end_requires_explicit_authority_and_scheduler():
    result = observe_source_health(
        source="overpass",
        metro="Austin, TX",
        runner=lambda _metro: iter([business()]),
        canonical_ingest_authorized=True,
        canonical_ingest_scheduled=True,
        now=NOW,
    )
    assert result.endpoint_healthy is True
    assert result.end_to_end_healthy is True
    assert result.blockers == ()


def test_empty_source_fails_closed():
    result = observe_source_health(
        source="overpass",
        metro="Austin, TX",
        runner=lambda _metro: iter(()),
        now=NOW,
    )
    assert result.endpoint_healthy is False
    assert result.end_to_end_healthy is False
    assert "no_source_candidates_observed" in result.blockers


def test_probe_error_is_observed_without_writes():
    def fail(_metro):
        raise RuntimeError("source unavailable")
        yield

    result = observe_source_health(
        source="overpass",
        metro="Austin, TX",
        runner=fail,
        now=NOW,
    )
    assert result.endpoint_healthy is False
    assert result.errors
    assert "source_probe_error" in result.blockers
    assert result.canonical_writes is False


def test_observation_write_is_atomic_json(tmp_path):
    result = observe_source_health(
        source="overpass",
        metro="Austin, TX",
        runner=lambda _metro: iter([business()]),
        now=NOW,
    )
    path = tmp_path / "latest.json"
    atomic_write_observation(path, result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source"] == "overpass"
    assert payload["mode"] == "OBSERVE"
    assert payload["canonical_writes"] is False
    assert not path.with_name("latest.json.tmp").exists()
