import asyncio

import httpx


def run(coro):
    return asyncio.run(coro)


def test_lead_counts_route_is_registered_once():
    from empire_os import hub

    matches = [
        route
        for route in hub.app.routes
        if getattr(route, "path", None) == "/v1/leads/counts"
    ]
    assert len(matches) == 1


def test_legacy_intake_url_uses_canonical_ingestor(monkeypatch):
    from empire_os import crawler_runner, hub

    captured = {}

    def fake_ingest(candidate):
        captured.update(candidate)
        return {
            "decision": "new",
            "prospect": {"id": "canonical-prospect-1"},
        }

    monkeypatch.setattr(
        crawler_runner,
        "ingest_candidate",
        fake_ingest,
    )

    async def request():
        transport = httpx.ASGITransport(app=hub.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/v1/leads/intake",
                json={
                    "lead_id": "ppl-42",
                    "name": "Acme Ltd",
                    "niche": "roofing",
                    "metro": "London",
                    "source": "ppl-9210",
                    "intent": "emergency_water_removal",
                    "consent": "explicit_form_submit",
                    "metadata": {"campaign": "storm"},
                },
            )

    response = run(request())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "canonical_owned"
    assert body["prospect_id"] == "canonical-prospect-1"
    assert captured["raw"]["external_lead_id"] == "ppl-42"
    assert captured["raw"]["metadata"] == {"campaign": "storm"}


def test_direct_intake_uses_same_canonical_contract(monkeypatch):
    from empire_os import crawler_runner, hub

    def fake_ingest(candidate):
        return {
            "decision": "matched",
            "prospect": {"id": "canonical-prospect-2"},
        }

    monkeypatch.setattr(
        crawler_runner,
        "ingest_candidate",
        fake_ingest,
    )

    async def request():
        transport = httpx.ASGITransport(app=hub.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/v1/leads/direct",
                json={
                    "name": "Acme Ltd",
                    "niche": "roofing",
                    "metro": "London",
                },
            )

    response = run(request())
    assert response.status_code == 200
    assert response.json()["decision"] == "matched"
    assert response.json()["status"] == "canonical_owned"


def test_list_leads_returns_crm_dictionary_contract(monkeypatch):
    from empire_os import crm, hub

    monkeypatch.setattr(hub, "backend", object())

    def fake_list(backend, **kwargs):
        assert kwargs["status"] == "raw"
        assert kwargs["niche"] is None
        assert kwargs["metro"] is None
        assert kwargs["limit"] == 25
        assert kwargs["offset"] == 5
        return {
            "total": 1,
            "limit": 25,
            "offset": 5,
            "leads": [{"id": 7, "status": "raw"}],
        }

    monkeypatch.setattr(crm, "list_leads", fake_list)

    async def request():
        transport = httpx.ASGITransport(app=hub.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get(
                "/v1/leads",
                params={
                    "status": "raw",
                    "limit": 25,
                    "offset": 5,
                },
            )

    response = run(request())
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["leads"][0]["id"] == 7


def test_status_route_uses_existing_pipeline_api(monkeypatch):
    from empire_os import crm, hub

    monkeypatch.setattr(hub, "backend", object())
    calls = []

    def fake_stage(backend, lead_id, stage_name, actor):
        calls.append(("stage", lead_id, stage_name, actor))
        return {"ok": True, "stage": stage_name}

    def fake_activity(
        backend,
        lead_id,
        act_type,
        summary,
        detail="",
        actor="user",
    ):
        calls.append(
            (
                "activity",
                lead_id,
                act_type,
                summary,
                detail,
                actor,
            )
        )
        return {"ok": True, "activity_id": 1}

    monkeypatch.setattr(crm, "set_pipeline_stage", fake_stage)
    monkeypatch.setattr(crm, "add_activity", fake_activity)

    async def request():
        transport = httpx.ASGITransport(app=hub.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.patch(
                "/v1/leads/7/status",
                params={
                    "status": "qualified",
                    "notes": "reviewed",
                },
            )

    response = run(request())

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "lead_id": 7,
        "status": "qualified",
    }
    assert calls[0] == ("stage", 7, "qualified", "api")
    assert calls[1][0] == "activity"
    assert calls[1][4] == "reviewed"


def test_status_route_rejects_non_integer_legacy_id(monkeypatch):
    from empire_os import hub

    monkeypatch.setattr(hub, "backend", object())

    async def request():
        transport = httpx.ASGITransport(app=hub.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.patch(
                "/v1/leads/not-an-int/status",
                params={"status": "qualified"},
            )

    response = run(request())
    assert response.status_code == 400
