import asyncio

import httpx


def test_hub_exposes_only_fail_closed_coder_surface(monkeypatch):
    monkeypatch.setenv("EMPIRE_CODER_API_ENABLED", "0")

    from empire_os.hub import app

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            health = await client.get("/v1/coder/health")
            assert health.status_code == 200
            body = health.json()
            assert body["api_enabled"] is False
            assert body["execution_mode"] == "OBSERVE"
            assert body["production_authority"] is False

            blocked = await client.post(
                "/v1/coder/tasks",
                json={"objective": "Inspect safely"},
            )
            assert blocked.status_code == 503

    asyncio.run(run())
