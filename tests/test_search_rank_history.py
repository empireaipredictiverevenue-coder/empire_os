from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.rank_history import (
    RankObservation,
    analyse_rank_history,
)
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)


def obs(position: int, observed_at: str) -> RankObservation:
    return RankObservation(
        query="roofing leads",
        url="https://example.test/roofing",
        observed_at=observed_at,
        position=position,
        engine="google",
        source="search_fabric",
        provenance=(f"serp:{observed_at}",),
    )


def test_rank_history_detects_improvement_without_synthetic_points():
    result = analyse_rank_history(
        (
            obs(18, "2026-09-01T09:00:00Z"),
            obs(11, "2026-09-08T09:00:00Z"),
            obs(6, "2026-09-20T09:00:00Z"),
        ),
        query="roofing leads",
        url="https://example.test/roofing",
        engine="google",
    )

    assert result["available"] is True
    assert result["latest_position"] == 6
    assert result["previous_position"] == 11
    assert result["position_change"] == 5
    assert result["best_position"] == 6
    assert result["worst_position"] == 18
    assert result["trend"] == "improving"
    assert result["synthetic_points"] == 0
    assert result["forecast_position"] is None


def test_rank_history_missing_evidence_stays_unknown():
    result = analyse_rank_history(
        (),
        query="roofing leads",
        url="https://example.test/roofing",
        engine="google",
    )

    assert result["available"] is False
    assert result["reason"] == "no_observed_rank_history"
    assert result["latest_position"] is None
    assert result["synthetic_points"] == 0


def test_rank_observation_requires_provenance():
    try:
        RankObservation(
            query="roofing leads",
            url="https://example.test/roofing",
            observed_at="2026-09-20T09:00:00Z",
            position=5,
            engine="google",
            source="search_fabric",
            provenance=(),
        )
    except ValueError as exc:
        assert "provenance required" in str(exc)
    else:
        raise AssertionError("rank evidence without provenance must fail")


def test_rank_history_api_is_observe_only():
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
        "/v1/search/rank-history/preview",
        json={
            "query": "roofing leads",
            "url": "https://example.test/roofing",
            "engine": "google",
            "observations": [
                {
                    "query": "roofing leads",
                    "url": "https://example.test/roofing",
                    "observed_at": "2026-09-01T09:00:00Z",
                    "position": 12,
                    "engine": "google",
                    "source": "search_fabric",
                    "provenance": ["serp:1"],
                },
                {
                    "query": "roofing leads",
                    "url": "https://example.test/roofing",
                    "observed_at": "2026-09-20T09:00:00Z",
                    "position": 8,
                    "engine": "google",
                    "source": "search_fabric",
                    "provenance": ["serp:2"],
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "OBSERVE"
    assert payload["execution_allowed"] is False
    assert payload["analysis"]["trend"] == "improving"
    assert payload["analysis"]["synthetic_points"] == 0
