"""No inferred homeowners, ZIP alert matches, payable calls or outreach."""
from datetime import datetime, timedelta, timezone
import copy

import pytest

from empire_os.competitor_call_geo_research import build_geo_research, SCHEMA


NOW = datetime(2026, 10, 26, 23, 45, tzinfo=timezone.utc)


def fixture():
    geo = {
        "schema_version": "empire.search_fabric.geo_opportunity_observation.v68",
        "source": "NOAA_NWS_PUBLIC_ALERTS",
        "source_url": "https://api.weather.gov/alerts/active",
        "source_rights_readonly_public_alerts": True,
        "database_writes": False,
        "outbound_sent": False,
        "market_gap_or_competitor_rank_measured": False,
        "retrieved_at_utc": (NOW-timedelta(minutes=10)).isoformat(),
        "research_only_geo_events": 2,
        "geo_events": [
            {
                "state": "TX",
                "geographic_precision": "NWS_UGC_STATE_ONLY_NOT_ADDRESS_OR_ZIP",
                "source_event_sha256": "a"*64,
                "source_record_url": "https://api.weather.gov/alerts/urn:oid:warning1",
                "event": "Severe Thunderstorm Warning",
                "issued_at_utc": (NOW-timedelta(hours=1)).isoformat(),
                "expires_at_utc": (NOW+timedelta(hours=2)).isoformat(),
                "potential_supply_research_verticals": ["roofing", "restoration"],
            },
            {
                "state": "CO",
                "geographic_precision": "NWS_UGC_STATE_ONLY_NOT_ADDRESS_OR_ZIP",
                "source_event_sha256": "b"*64,
                "source_record_url": "https://api.weather.gov/alerts/urn:oid:flood1",
                "event": "Flood Warning",
                "issued_at_utc": (NOW-timedelta(hours=1)).isoformat(),
                "expires_at_utc": (NOW+timedelta(hours=2)).isoformat(),
                "potential_supply_research_verticals": ["restoration"],
            },
        ],
    }
    cov = {
        "schema_version": "empire.lead_smart.coverage_snapshot.v1",
        "mode": "OBSERVE",
        "buyer": "Lead Smart",
        "source": {"semantics": "TARGETING_GUIDANCE_ONLY", "payout_guaranteed": False},
        "observed_at": (NOW-timedelta(minutes=20)).isoformat(),
        "source_hash": "c"*64,
        "coverage": {"row_count": 4},
        "rows": [
            {"state": "TX", "zip": "75001"},
            {"state": "TX", "zip": "75002"},
            {"state": "IL", "zip": "60601"},
            {"state": None, "zip": "99999"},
        ],
    }
    return geo, cov


def test_real_state_alert_research_not_accepted_buyer_or_zip():
    geo, coverage = fixture()
    result = build_geo_research(geo=geo, coverage=coverage, now=NOW)
    assert result["schema_version"] == SCHEMA
    assert result["fresh_for_research"]
    assert result["active_roofing_alert_count"] == 1
    assert result["state_count"] == 3  # TX plus pilot IL / legacy CO
    assert result["unmapped_coverage_zip_rows"] == 1
    assert [r["state"] for r in result["states"]] == ["TX", "IL", "CO"]
    assert result["states"][0]["public_coverage_zip_row_count"] == 2
    assert result["states"][0]["priority_class"] == "SOURCE_EVENT_AND_COVERAGE_REVIEW"
    assert result["states"][1]["priority_class"] == "EXISTING_MARKET_BASELINE_NO_MATCHING_ALERT_IN_SAMPLED_SOURCE"
    assert result["buyer_geo_verified"] is False
    assert result["human_lead_verified"] is False
    assert result["market_demand_estimated"] is False
    assert result["call_traffic_authorized"] is False
    assert result["execution_authority"] == "none"
    assert all(r["exact_alert_zip_match_verified"] is False for r in result["states"])
    assert "75001" not in repr(result)
    assert "60601" not in repr(result)


def test_expired_roofing_warning_does_not_survive_to_research_queue():
    geo, coverage = fixture()
    geo["geo_events"][0]["expires_at_utc"] = (NOW-timedelta(minutes=1)).isoformat()
    r = build_geo_research(geo=geo, coverage=coverage, now=NOW)
    assert r["active_roofing_alert_count"] == 0
    assert set(p["state"] for p in r["states"]) == {"IL", "CO"}


def test_stale_snapshot_discards_research_ranking_not_source_truth():
    geo, coverage = fixture()
    geo["retrieved_at_utc"] = (NOW-timedelta(hours=3)).isoformat()
    r = build_geo_research(geo=geo, coverage=coverage, now=NOW)
    assert r["fresh_for_research"] is False
    assert r["state_count"] == 0
    assert r["call_traffic_authorized"] is False


@pytest.mark.parametrize("key,value", [
    ("source_rights_readonly_public_alerts", False),
    ("source", "FAKE_STORM_INVENTORY"),
    ("market_gap_or_competitor_rank_measured", True),
])
def test_untrusted_geo_source_fails_closed(key, value):
    geo, coverage = fixture()
    geo[key] = value
    with pytest.raises(ValueError):
        build_geo_research(geo=geo, coverage=coverage, now=NOW)


def test_state_scope_cannot_be_upgrade_to_zip_or_property():
    geo, coverage = fixture()
    geo["geo_events"][0]["geographic_precision"] = "HOUSEHOLD_ZIP_EXACT"
    with pytest.raises(ValueError):
        build_geo_research(geo=geo, coverage=coverage, now=NOW)


def test_invalid_unknown_coverage_state_not_guessed():
    geo, coverage = fixture()
    coverage["rows"][0]["state"] = "FAKE"
    with pytest.raises(ValueError):
        build_geo_research(geo=geo, coverage=coverage, now=NOW)
