from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.lead_smart_zip_activation import build_zip_targeting_gate

NOW = datetime(2026, 10, 9, 15, 55, tzinfo=timezone.utc)


def snapshot(count=8):
    rows = [
        {"zip": f"{v:05d}", "offer_key": "roofing"}
        for v in range(501, 501 + count)
    ]
    return {
        "schema_version": "empire.lead_smart.coverage_snapshot.v1",
        "mode": "OBSERVE",
        "observed_at": NOW.isoformat(),
        "source_hash": "a" * 64,
        "source": {
            "semantics": "TARGETING_GUIDANCE_ONLY",
            "payout_guaranteed": False,
        },
        "coverage": {
            "row_count": count,
            "unique_zip_count": count,
            "source_newest_last_updated": NOW.isoformat(),
        },
        "rows": rows,
        "authority": {
            "zip_coverage_observed": True,
            "execution_authority": "NONE",
        },
    }


def intelligence(data):
    return {
        "schema_version": "empire.lead_smart.coverage_intelligence.v1",
        "mode": "OBSERVE",
        "freshness": {"fresh_for_targeting_analysis": True},
        "coverage": {
            "source_hash": data["source_hash"],
            "row_count": data["coverage"]["row_count"],
            "unique_zip_count": data["coverage"]["unique_zip_count"],
        },
    }


def verify(data, intel=None, *, now=NOW):
    return build_zip_targeting_gate(
        snapshot=data,
        intelligence=intel if intel is not None else intelligence(data),
        now=now,
    )


@pytest.mark.parametrize("count", [8, 27906, 28040])
def test_coverage_cardinality_is_dynamic_and_fail_closed(count):
    data = snapshot(count=count)
    result = verify(data)
    assert result["zip_count"] == count
    assert result["zips"][0] == "00501"
    assert result["zip_targeting_gate_verified"] is True
    assert result["zip_coverage_activation_verified"] is True
    assert result["provider_payout_guaranteed"] is False
    assert result["provider_runtime_route_verified"] is False
    assert result["routing_enabled"] is False
    assert result["traffic_enabled"] is False


def test_intelligence_stale_claim_fails_closed():
    data = snapshot()
    intel = intelligence(data)
    intel["freshness"]["fresh_for_targeting_analysis"] = False
    with pytest.raises(ValueError, match="stale"):
        verify(data, intel)


def test_realtime_staleness_prevents_old_cached_true_value():
    data = snapshot()
    # The cached intelligence still says fresh but the observation expired.
    with pytest.raises(ValueError, match="stale"):
        verify(data, now=NOW + timedelta(hours=7))


def test_future_dated_snapshot_fails_closed():
    data = snapshot()
    data["observed_at"] = (NOW + timedelta(hours=2)).isoformat()
    with pytest.raises(ValueError, match="future-dated"):
        verify(data)


def test_missing_source_timestamp_fails_closed():
    data = snapshot()
    del data["coverage"]["source_newest_last_updated"]
    with pytest.raises(ValueError, match="missing coverage freshness evidence"):
        verify(data)


def test_intelligence_source_mismatch_fails_closed():
    data = snapshot()
    intel = intelligence(data)
    intel["coverage"]["source_hash"] = "b" * 64
    with pytest.raises(ValueError, match="source mismatch"):
        verify(data, intel)


def test_snapshot_counts_must_match_rows():
    data = snapshot()
    data["coverage"]["row_count"] += 1
    intel = intelligence(data)
    with pytest.raises(ValueError, match="cardinality mismatch"):
        verify(data, intel)


def test_duplicate_zip_fails_closed():
    data = snapshot()
    data["rows"][-1]["zip"] = data["rows"][0]["zip"]
    with pytest.raises(ValueError, match="duplicate"):
        verify(data)


def test_invalid_zip_fails_closed():
    data = snapshot()
    data["rows"][0]["zip"] = "1234"
    with pytest.raises(ValueError, match="invalid ZIP"):
        verify(data)


def test_source_policy_is_not_mutated():
    data = snapshot()
    before = deepcopy(data)
    verify(data)
    assert data == before


def test_missing_source_hash_fails_closed():
    data = snapshot()
    data["source_hash"] = ""
    with pytest.raises(ValueError, match="source hash"):
        verify(data)


def test_future_dated_source_update_fails_closed():
    data = snapshot()
    data["coverage"]["source_newest_last_updated"] = (
        NOW + timedelta(hours=1)
    ).isoformat()
    with pytest.raises(ValueError, match="future-dated coverage source"):
        verify(data)
