from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,os
import pytest

from empire_os.gods_eye_nws_refresh import refresh_official_nws_coverage,OUTPUT,ALERTS

NOW=datetime(2026,10,27,18,0,tzinfo=timezone.utc)
LINK="https://api.weather.gov/zones/forecast/TXZ001"
ALERT="https://api.weather.gov/alerts/urn:oid:1.2.3"
def alert():
    return {"type":"Feature","id":ALERT,"geometry":None,
      "properties":{"status":"Actual","sent":(NOW-timedelta(hours=1)).isoformat(),
        "expires":(NOW+timedelta(hours=2)).isoformat(),
        "affectedZones":[LINK],"severity":"Moderate","event":"Coastal Flood Advisory"}}
def alerts():
    return {"type":"FeatureCollection","features":[alert()]}
def zone():
    return {"type":"Feature","id":LINK,"properties":{"id":"TXZ001","name":"Fixture"},
        "geometry":{"type":"Polygon","coordinates":[[[-96,28],[-95,28],[-95,29],[-96,28]]]}}
def fake_get(url,cap):
    assert url in (ALERTS,LINK)
    assert cap > 1000
    return alerts() if url==ALERTS else zone()

def test_official_source_writes_only_private_0600_geojson(tmp_path):
    status=refresh_official_nws_coverage(tmp_path,now=NOW,get=fake_get)
    assert status["zone_count"]==1
    assert status["commercial_authority"]=="none"
    assert status["public_publish_authorized"] is False
    target=tmp_path/OUTPUT
    assert target.stat().st_mode&0o777==0o600
    data=json.loads(target.read_text())
    assert len(data["features"])==1
    assert data["features"][0]["properties"]["weather_impact_footprint_verified"] is False
    assert data["features"][0]["properties"]["buyer_intent_verified"] is False
    assert data["empire_review"]["public_publish_authorized"] is False

def test_official_source_failure_preserves_previous_evidence(tmp_path):
    refresh_official_nws_coverage(tmp_path,now=NOW,get=fake_get)
    target=tmp_path/OUTPUT
    orig=target.read_bytes()
    with pytest.raises(OSError):
        refresh_official_nws_coverage(tmp_path,now=NOW,get=lambda u,c:(_ for _ in ()).throw(OSError("offline")))
    assert target.read_bytes()==orig

def test_preview_cannot_fetch_or_mutate(tmp_path):
    def fail(*_):raise AssertionError("network called in preview")
    assert refresh_official_nws_coverage(tmp_path,now=NOW,get=fail,enable_fetch=False)["fetched"] is False
    assert not (tmp_path/OUTPUT).exists()

def test_old_and_empty_sources_cannot_invent_coverage(tmp_path):
    payload=alerts()
    payload["features"][0]["properties"]["expires"]=(NOW-timedelta(seconds=1)).isoformat()
    out=refresh_official_nws_coverage(tmp_path,now=NOW,get=lambda u,c:payload if u==ALERTS else zone())
    assert out["zone_count"]==0
    assert json.loads((tmp_path/OUTPUT).read_text())["features"]==[]
