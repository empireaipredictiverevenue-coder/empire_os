from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.local_visibility import (
    LocalGridObservation,
    analyse_local_grid,
)
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)


def point(lat, lon, position):
    return LocalGridObservation(
        query="roofer near me",
        latitude=lat,
        longitude=lon,
        observed_at="2026-09-20T12:00:00Z",
        engine="google_maps",
        provenance=(f"grid:{lat}:{lon}",),
        position=position,
    )


def test_local_grid_calculates_only_observed_coverage():
    rows = (
        point(32.77, -96.80, 2),
        point(32.78, -96.81, 5),
        point(32.79, -96.82, 14),
        point(32.80, -96.83, None),
    )

    result = analyse_local_grid(
        rows,
        query="roofer near me",
        engine="google_maps",
    )

    assert result["available"] is True
    assert result["observed_points"] == 4
    assert result["ranked_points"] == 3
    assert result["unknown_points"] == 1
    assert result["top3_share"] == 0.3333
    assert result["top10_share"] == 0.6667
    assert result["median_observed_position"] == 5.0
    assert result["weak_point_count"] == 1
    assert result["synthetic_points"] == 0


def test_local_grid_without_evidence_stays_unknown():
    result = analyse_local_grid(
        (),
        query="roofer near me",
        engine="google_maps",
    )

    assert result["available"] is False
    assert result["top3_share"] is None
    assert result["synthetic_points"] == 0


def test_local_grid_requires_provenance():
    try:
        LocalGridObservation(
            query="roofer near me",
            latitude=32.77,
            longitude=-96.80,
            observed_at="2026-09-20T12:00:00Z",
            engine="google_maps",
            provenance=(),
            position=2,
        )
    except ValueError as exc:
        assert "provenance required" in str(exc)
    else:
        raise AssertionError("local grid evidence must require provenance")


def test_local_grid_api_is_observe_only():
    app = FastAPI()
    app.include_router(
        create_search_router(
            repository=None,
            search_console_adapter=DisabledSearchConsoleAdapter(
                SearchConsoleStatus(
                    enabled=False,
                    configured=False,
                    available=False,
                    reason="not_configured",
                )
            ),
        )
    )
    client = TestClient(app)

    response = client.post(
        "/v1/search/local-grid/preview",
        json={
            "query": "roofer near me",
            "engine": "google_maps",
            "observations": [
                {
                    "query": "roofer near me",
                    "latitude": 32.77,
                    "longitude": -96.80,
                    "observed_at": "2026-09-20T12:00:00Z",
                    "engine": "google_maps",
                    "provenance": ["grid:1"],
                    "position": 3,
                },
                {
                    "query": "roofer near me",
                    "latitude": 32.78,
                    "longitude": -96.81,
                    "observed_at": "2026-09-20T12:00:00Z",
                    "engine": "google_maps",
                    "provenance": ["grid:2"],
                    "position": None,
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "OBSERVE"
    assert payload["execution_allowed"] is False
    assert payload["analysis"]["top3_share"] == 1.0
    assert payload["analysis"]["unknown_points"] == 1
