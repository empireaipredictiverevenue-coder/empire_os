from fastapi.testclient import TestClient

from empire_os import carrier_rosters
from empire_os.hub import app


client = TestClient(app)


def test_missing_roster_cache_reads_empty_without_creation(tmp_path, monkeypatch):
    db_path = tmp_path / "missing.db"
    monkeypatch.setattr(carrier_rosters, "DB", str(db_path))

    assert carrier_rosters.list_rosters() == []
    assert carrier_rosters.roster_stats() == []
    assert db_path.exists() is False


def test_public_carrier_scrape_is_retired():
    response = client.post("/v1/carrier-rosters/scrape")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_carrier_roster_scrape_retired_use_governed_source_mesh"
    )


def test_roster_list_route_is_read_only(monkeypatch):
    monkeypatch.setattr(
        carrier_rosters,
        "list_rosters",
        lambda carrier=None, limit=100: [
            {
                "id": 1,
                "carrier": "statefarm",
                "company_name": "Example Roofing",
                "license_no": "ABC",
                "city": "Austin",
                "state": "TX",
                "scraped_at": "2026-09-19T00:00:00+00:00",
            }
        ],
    )
    response = client.get("/v1/carrier-rosters")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["data"][0]["carrier"] == "statefarm"


def test_roster_stats_route_is_read_only(monkeypatch):
    monkeypatch.setattr(
        carrier_rosters,
        "roster_stats",
        lambda: [{"carrier": "statefarm", "count": 1}],
    )
    response = client.get("/v1/carrier-rosters/stats")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["stats"][0]["count"] == 1
