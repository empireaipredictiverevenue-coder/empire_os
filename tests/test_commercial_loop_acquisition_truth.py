from datetime import datetime, timezone

from empire_os.commercial_loop_observer import (
    fetch_canonical_commercial_observations,
    observations_from_cycle,
)


NOW = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)


def test_canonical_acquisition_survives_later_zero_runtime_cycle():
    def reader(path, params):
        if path.endswith("/prospect_acquisitions"):
            return [{
                "prospect_id": "prospect-real-1",
                "source": "overpass_osm",
                "created_at": "2026-09-20T12:57:39Z",
            }]
        return []

    canonical = fetch_canonical_commercial_observations(reader, now=NOW)
    observations = observations_from_cycle(
        acquisition_accepted=0,
        qualification={"qualified": 0},
        omega={"candidates_seen": 5},
        buyer_readiness={
            "buyers_with_verified_terms": 0,
            "activated_buyers_with_capacity": 0,
        },
        canonical_observations=canonical,
    )

    assert canonical["real_acquisition"].observed is True
    assert observations["real_acquisition"].observed is True
    assert observations["real_acquisition"].evidence_ref == (
        "canonical:prospect_acquisitions"
    )


def test_no_canonical_acquisition_remains_false_after_zero_runtime_cycle():
    def reader(path, params):
        return []

    canonical = fetch_canonical_commercial_observations(reader, now=NOW)
    observations = observations_from_cycle(
        acquisition_accepted=0,
        qualification={"qualified": 0},
        omega={"candidates_seen": 0},
        buyer_readiness={
            "buyers_with_verified_terms": 0,
            "activated_buyers_with_capacity": 0,
        },
        canonical_observations=canonical,
    )

    assert canonical["real_acquisition"].observed is False
    assert observations["real_acquisition"].observed is False
