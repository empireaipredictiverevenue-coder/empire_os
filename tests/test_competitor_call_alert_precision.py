"""County UGC and forecast-zone NWS review never become ZIP or buyer intent."""
import hashlib
from datetime import datetime, timezone, timedelta
from copy import deepcopy
from pathlib import Path

import pytest

from empire_os.competitor_call_alert_precision import (
    SCHEMA, review_once, parse_official_alert, _official_alert_url,
)

NOW = datetime(2026, 10, 27, 10, 35, tzinfo=timezone.utc)
URL = "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.test.001.1"


def snapshot():
    return {
        "schema_version": "empire.search_fabric.geo_opportunity_observation.v68",
        "source": "NOAA_NWS_PUBLIC_ALERTS",
        "source_url": "https://api.weather.gov/alerts/active",
        "source_rights_readonly_public_alerts": True,
        "outbound_sent": False, "database_writes": False,
        "retrieved_at_utc": (NOW-timedelta(minutes=4)).isoformat(),
        "geo_events": [{
            "source_event_sha256": hashlib.sha256(URL.encode()).hexdigest(),
            "source_record_url": URL,
            "state": "TX", "event": "Severe Thunderstorm Warning",
            "issued_at_utc": (NOW-timedelta(minutes=20)).isoformat(),
            "expires_at_utc": (NOW+timedelta(hours=2)).isoformat(),
            "geographic_precision": "NWS_UGC_STATE_ONLY_NOT_ADDRESS_OR_ZIP",
            "potential_supply_research_verticals": ["roofing", "restoration"],
        }],
    }


def official(ugc=("TXC113", "TXZ125")):
    return {
        "type": "Feature", "id": URL,
        "properties": {
            "@id": URL, "event": "Severe Thunderstorm Warning",
            "status": "Actual", "messageType": "Alert",
            "sent": (NOW-timedelta(minutes=20)).isoformat(),
            "ends": (NOW+timedelta(hours=2)).isoformat(),
            "geocode": {"UGC": list(ugc)},
            "affectedZones": ["https://api.weather.gov/zones/county/TXC113",
                              "https://api.weather.gov/zones/forecast/TXZ125"],
        },
    }


def test_county_codes_are_not_converted_to_zip_fips_or_buyers():
    r = review_once(snapshot(), now=NOW, fetch=lambda _: official())
    assert r["schema_version"] == SCHEMA
    assert r["detail_checked_this_cycle"] == 1
    assert r["official_detail_observation_count"] == 1
    obs = r["observations"][0]
    assert obs["official_county_ugc_ids"] == ["TXC113"]
    assert obs["official_forecast_zone_ugc_ids"] == ["TXZ125"]
    assert obs["geographic_precision"] == "NWS_COUNTY_UGC_IDENTIFIERS_AND_FORECAST_ZONES"
    assert not obs["county_fips_crosswalk_verified"]
    assert not obs["affected_property_zip_codes_verified"]
    assert not r["accepted_buyer_territory_verified"]
    assert not r["call_activation_authorized"]
    assert r["execution_authority"] == "none"


def test_forecast_zones_are_never_labelled_counties():
    v = review_once(snapshot(), now=NOW,
                    fetch=lambda _: official(("TXZ125", "TXZ126")))
    obs = v["observations"][0]
    assert obs["official_county_ugc_ids"] == []
    assert obs["forecast_zone_ugc_count"] == 2
    assert obs["county_ugc_count"] == 0
    assert obs["geographic_precision"] == "NWS_FORECAST_ZONE_IDENTIFIERS_ONLY"


@pytest.mark.parametrize("change", [
    lambda d: d["properties"].update({"@id": "https://evil.example/alerts/1"}),
    lambda d: d["properties"].update({"event": "Different Hazard"}),
    lambda d: d["properties"].update({"status": "Test"}),
    lambda d: d["properties"]["geocode"].update({"UGC": ["TXC113", "ABC123"]}),
    lambda d: d["properties"].update({"ends": (NOW-timedelta(minutes=1)).isoformat()}),
    lambda d: d["properties"].update({"sent": (NOW-timedelta(days=2)).isoformat()}),
])
def test_untrusted_official_alert_never_promoted(change):
    bad = official()
    change(bad)
    out = review_once(snapshot(), now=NOW, fetch=lambda _: bad)
    assert out["official_detail_observation_count"] == 0
    assert out["last_fetch_status"] == "DETAIL_FETCH_UNAVAILABLE_OR_UNVERIFIED"


def test_expired_source_skips_network():
    s = snapshot()
    s["geo_events"][0]["expires_at_utc"] = (NOW-timedelta(minutes=1)).isoformat()
    r = review_once(s, now=NOW, fetch=lambda _: pytest.fail("unexpected network"))
    assert r["detail_checked_this_cycle"] == 0
    assert not r["observations"]


def test_missing_snapshot_freshness_skips_network():
    s = snapshot()
    s["retrieved_at_utc"] = (NOW-timedelta(hours=4)).isoformat()
    r = review_once(s, now=NOW, fetch=lambda _: pytest.fail("unexpected network"))
    assert r["eligible_roofing_event_count"] == 0


def test_real_alert_url_is_allowlisted_not_arbitrary_host():
    assert _official_alert_url(URL)
    assert not _official_alert_url("https://api.weather.gov.evil.test/alerts/urn:oid:abcd")
    assert not _official_alert_url("http://api.weather.gov/alerts/urn:oid:abc")
    assert not _official_alert_url("https://api.weather.gov@evil.test/alerts/urn:oid:abc")
    assert not _official_alert_url("https://api.weather.gov/alerts/active?point=1,2")


def test_round_robin_one_detail_max_with_two_events():
    x = snapshot()
    another = deepcopy(x["geo_events"][0])
    another["source_record_url"] = URL.replace("001.1", "002.1")
    another["source_event_sha256"] = hashlib.sha256(another["source_record_url"].encode()).hexdigest()
    x["geo_events"].append(another)
    calls = []
    def fetch(url):
        calls.append(url)
        q = official()
        q["id"] = url
        q["properties"]["@id"] = url
        return q
    first = review_once(x, now=NOW, fetch=fetch)
    second = review_once(x, previous=first, now=NOW, fetch=fetch)
    assert len(calls) == 2
    assert len(set(calls)) == 2
    assert first["detail_checked_this_cycle"] == second["detail_checked_this_cycle"] == 1
    assert second["official_detail_observation_count"] == 2

def test_existing_timer_stage_never_creates_new_monitor_or_outbound(tmp_path):
    from scripts.refresh_opportunity_brief_chain import refresh_bounded_alert_precision
    missing = refresh_bounded_alert_precision(
        tmp_path, precision_fn=lambda _: pytest.fail("unexpected fetch"))
    assert missing["status"] == "ORIGINAL_GEO_OBSERVATION_UNAVAILABLE"
    assert missing["checked"] == 0
    p = tmp_path / "runtime/search_fabric_evidence/geo_opportunity_latest_v68.json"
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    success = refresh_bounded_alert_precision(tmp_path, precision_fn=lambda _: {
        "last_fetch_status": "VERIFIED_OFFICIAL_ALERT_DETAIL",
        "detail_checked_this_cycle": 1,
        "official_detail_observation_count": 2,
        "county_ugc_area_count": 1,
        "forecast_zone_area_count": 3,
    })
    assert success["checked"] == 1
    assert success["county_ugc_area_count"] == 1
    assert not success["buyer_territory_or_homeowner_lead_verified"]
    assert success["execution_authority"] == "none"
    held = refresh_bounded_alert_precision(
        tmp_path, precision_fn=lambda _: (_ for _ in ()).throw(ValueError("bad")))
    assert held["status"] == "COUNTY_ZONE_RESEARCH_HELD"
    assert held["execution_authority"] == "none"


def test_original_founder_feed_exposes_only_validated_zone_evidence(tmp_path):
    import json
    from empire_os.competitor_call_channel_atlas import build_atlas, SOURCE
    from empire_os.competitor_intelligence_feed import _call_acquisition_overlay
    root = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    atlas = build_atlas(json.loads((root / SOURCE).read_text()), now=NOW)
    (runtime / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    r = review_once(snapshot(), now=NOW, fetch=lambda _: official(("TXZ125",)))
    (runtime / "call_alert_precision_latest.json").write_text(json.dumps(r))
    overlay = _call_acquisition_overlay(tmp_path)
    detail = overlay["official_alert_precision"]
    assert detail["available"] is True
    assert detail["county_ugc_area_count"] == 0
    assert detail["forecast_zone_area_count"] == 1
    assert detail["observations"][0]["official_forecast_zone_ugc_ids"] == ["TXZ125"]
    assert detail["accepted_buyer_territory_verified"] is False
    r["outreach_enabled"] = True
    (runtime / "call_alert_precision_latest.json").write_text(json.dumps(r))
    assert _call_acquisition_overlay(tmp_path)["official_alert_precision"]["available"] is False


def test_repeat_refresh_is_throttled_before_second_nws_request(tmp_path, monkeypatch):
    import json
    from empire_os import competitor_call_alert_precision as module
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    inp = tmp_path / module.GEO
    inp.parent.mkdir(parents=True)
    inp.write_text(json.dumps(snapshot()))
    # Seed the *prior receipt* directly: this test exercises the cooldown,
    # not the historical fixture's alert state at the current wall clock.
    prior = {
        "schema_version": module.SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "detail_checked_this_cycle": 1,
        "observations": [],
        "execution_authority": "none",
    }
    (runtime / "call_alert_precision_latest.json").write_text(json.dumps(prior))
    monkeypatch.setattr(module, "fetch_official_alert",
                        lambda _: pytest.fail("second request during cooldown"))
    assert module.refresh(tmp_path) == prior
