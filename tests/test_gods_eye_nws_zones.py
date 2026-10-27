"""Official NWS zone *coverage* must never imply mapped impact or leads."""
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.gods_eye_nws_zones import build_nws_advisory_zone_review

NOW = datetime.now(timezone.utc)
ZONE = "https://api.weather.gov/zones/forecast/TXZ015"
ALERT = "https://api.weather.gov/alerts/urn:oid:example"


def payload(*, sent=NOW, expires=NOW + timedelta(minutes=40), status="Actual"):
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "id": ALERT, "geometry": None,
            "properties": {
                "event": "Dense Fog Advisory", "severity": "Moderate",
                "status": status, "sent": sent.isoformat(),
                "expires": expires.isoformat(), "affectedZones": [ZONE],
            },
        }],
    }


def zone(*, geom=None):
    return {
        "type": "Feature", "id": ZONE,
        "properties": {"id": "TXZ015", "name": "Wheeler"},
        "geometry": geom or {"type": "Polygon", "coordinates": [[
            [-100.1, 35.5], [-100.0, 35.5], [-100.0, 35.6], [-100.1, 35.5],
        ]]},
    }


def make(a=None, z=None, **kwargs):
    return build_nws_advisory_zone_review(
        a or payload(), z if z is not None else {ZONE: zone()},
        now=NOW, alerts_transport_verified=True,
        zone_transports_verified=True, **kwargs,
    )


def test_real_forecast_zone_does_not_assert_hazard_damage_or_lead():
    data = make()
    assert data["type"] == "FeatureCollection"
    assert data["empire_review"]["status"] == "OFFICIAL_ZONE_COVERAGE_AVAILABLE"
    assert len(data["features"]) == 1
    props = data["features"][0]["properties"]
    assert props["alert_ref"] == ALERT and props["zone_ref"] == ZONE
    assert props["zone_id"] == "TXZ015"
    assert props["geometry_truth"] == "ADVISORY_FORECAST_ZONE_COVERAGE_NOT_EVENT_FOOTPRINT"
    assert props["weather_impact_footprint_verified"] is False
    assert props["property_damage_verified"] is False
    assert props["buyer_intent_verified"] is False
    assert data["empire_review"]["public_publish_authorized"] is False


def test_missing_official_zone_geometry_produces_no_map_feature():
    data = make(z={})
    assert data["features"] == []
    assert data["empire_review"]["audit"]["zones_unavailable_or_invalid"] == 1


def test_zone_url_match_is_mandatory():
    fake = zone()
    fake["id"] = "https://api.weather.gov/zones/forecast/TXZ123"
    assert make(z={ZONE: fake})["features"] == []


def test_expired_advisory_must_be_absent():
    d = payload(expires=NOW - timedelta(seconds=3))
    assert make(a=d)["features"] == []


def test_not_yet_sent_advisory_must_be_absent():
    d = payload(sent=NOW + timedelta(minutes=5))
    assert make(a=d)["features"] == []


def test_point_geometry_never_used_as_advisory_zone():
    fake = zone(geom={"type": "Point", "coordinates": [-100, 35]})
    assert make(z={ZONE: fake})["features"] == []


def test_no_claimed_transport_no_source():
    with pytest.raises(ValueError, match="separate_official_nws"):
        build_nws_advisory_zone_review(payload(), {ZONE: zone()}, now=NOW,
                                        alerts_transport_verified=False,
                                        zone_transports_verified=True)


def test_alert_that_has_precise_polygon_not_duplicated_as_zone():
    d=payload()
    d["features"][0]["geometry"] = zone()["geometry"]
    assert make(a=d)["features"] == []


def test_still_valid_advisory_issued_eight_hours_earlier_is_eligible():
    advisory = payload(sent=NOW-timedelta(hours=8),expires=NOW+timedelta(hours=3))
    result = make(a=advisory)
    assert len(result["features"]) == 1
