from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import empire_os.search_intelligence.api as search_api
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)
from empire_os.search_intelligence.serp import (
    SerpResultEvidence,
    SerpSnapshot,
)


class FakeSerpAdapter:
    def snapshot(self, query, *, num=10, engine=None):
        return SerpSnapshot(
            query=query,
            observed_at=datetime(
                2026, 9, 20, 23, 30, tzinfo=timezone.utc
            ).isoformat(),
            engine=engine or "bing_html",
            quality_gate="lexical_v1",
            cache=False,
            available=True,
            results=(
                SerpResultEvidence(
                    title="Example Roofing",
                    url="https://example.test/",
                    snippet="Roofing services",
                    position=1,
                    engine=engine or "bing_html",
                    relevance_score=0.91,
                    provenance=(
                        "search_fabric",
                        f"engine:{engine or 'bing_html'}",
                        "quality_gate:lexical_v1",
                    ),
                ),
            ),
            error=None,
        )


def test_serp_product_endpoint_preserves_observed_position_and_provenance(
    monkeypatch,
):
    monkeypatch.setattr(
        search_api,
        "SearchFabricSerpAdapter",
        FakeSerpAdapter,
    )

    app = FastAPI()
    app.include_router(
        search_api.create_search_router(
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
        "/v1/search/serp/snapshot",
        json={
            "query": "roofers dallas",
            "num": 10,
            "engine": "bing_html",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["commercial_product"] == "serp_intelligence_api"
    assert payload["mode"] == "OBSERVE"
    assert payload["execution_allowed"] is False
    assert payload["snapshot"]["results"][0]["position"] == 1
    assert "search_fabric" in (
        payload["snapshot"]["results"][0]["provenance"]
    )


def test_serp_product_endpoint_fails_closed_when_adapter_fails(
    monkeypatch,
):
    class BrokenAdapter:
        def snapshot(self, *args, **kwargs):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(
        search_api,
        "SearchFabricSerpAdapter",
        BrokenAdapter,
    )

    app = FastAPI()
    app.include_router(
        search_api.create_search_router(
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
        "/v1/search/serp/snapshot",
        json={"query": "roofers dallas"},
    )

    assert response.status_code == 503
    assert "serp_snapshot_unavailable" in response.json()["detail"]
