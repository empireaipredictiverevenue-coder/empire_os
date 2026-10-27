"""Evidence-only God's Eye NWS GeoJSON compatibility tests."""
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.gods_eye_nws_geojson import build_official_nws_review_layer

NOW = datetime.now(timezone.utc)
SQUARE = {"type": "Polygon", "coordinates": [[
    [-97.3, 32.7], [-97.2, 32.7], [-97.2, 32.8], [-97.3, 32.7],
]]}


def example(*, geometry=SQUARE, sent=NOW, expires=NOW+timedelta(hours=2), status="Actual"):
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "id": "https://api.weather.gov/alerts/urn:oid:example",
        "geometry": geometry,
        "properties": {
            "event": "Severe Thunderstorm Warning",
            "severity": "Severe",
            "sent": sent.isoformat(), "expires": expires.isoformat(),
            "status": status,
        },
    }]}


def test_official_polygon_is_just_observed_geometry_not_business_opportunity():
    layer = build_official_nws_review_layer(
        example(), now=NOW, verified_official_transport=True)
    assert layer["type"] == "FeatureCollection"
    assert layer["empire_review"]["counts"]["accepted"] == 1
    assert layer["empire_review"]["status"] == "GEOJSON_OBSERVATIONS_AVAILABLE"
    f = layer["features"][0]
    assert f["geometry"]["type"] == "Polygon"
    assert f["properties"]["property_damage_verified"] is False
    assert f["properties"]["buyer_intent_verified"] is False
    assert f["properties"]["commercial_opportunity_verified"] is False
    assert layer["empire_review"]["public_publish_authorized"] is False


def test_bare_user_claim_of_official_data_is_never_enough():
    with pytest.raises(ValueError, match="transport_verification"):
        build_official_nws_review_layer(example(), now=NOW)


@pytest.mark.parametrize("changes,missing", [
    ({"geometry": None}, "geometry_unavailable"),
    ({"geometry": {"type": "Point", "coordinates": [-97.0,32.8]}}, "geometry_unavailable"),
    ({"geometry": {"type": "Polygon", "coordinates": [[[-197, 32], [-97, 32], [-97, 33], [-197, 32]]]}}, "geometry_unavailable"),
    ({"sent": NOW-timedelta(days=2)}, "stale_or_inactive"),
    ({"status": "Test"}, "stale_or_inactive"),
    ({"expires": NOW-timedelta(minutes=1)}, "stale_or_inactive"),
])
def test_unknown_geometry_and_stale_or_test_alerts_never_drawn(changes,missing):
    d = example()
    for k,v in changes.items():
        if k in ("geometry",):d["features"][0][k] = v
        else:d["features"][0]["properties"][k] = v.isoformat() if isinstance(v,datetime) else v
    output = build_official_nws_review_layer(d, now=NOW, verified_official_transport=True)
    assert output["features"] == []
    assert output["empire_review"]["counts"][missing] == 1


def test_user_supplied_untrusted_url_fails_closed():
    d = example()
    d["features"][0]["id"] = "https://attacker.example/alerts/fake"
    result = build_official_nws_review_layer(d, now=NOW, verified_official_transport=True)
    assert result["features"] == [] and result["empire_review"]["counts"]["invalid"] == 1
