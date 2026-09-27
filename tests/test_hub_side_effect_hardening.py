from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_direct_video_shell_render_is_retired():
    response = client.post(
        "/v1/video/brief",
        json={"copy": "hello; rm -rf /", "niche": "roofing"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_video_brief_retired_use_governed_advertising_creative_flow"
    )


def test_public_agent_dispatch_is_retired():
    response = client.post(
        "/v1/agents/storm/dispatch",
        json={"action": "run"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_agent_dispatch_retired_use_governed_execution_bus"
    )


def test_cinematic_render_is_in_memory_escaped_preview():
    response = client.post(
        "/v1/cinematic/render",
        json={
            "headline": "<script>alert(1)</script>",
            "subhead": "\"quoted\"",
            "price": "<b>£99</b>",
            "cta": "<img src=x onerror=alert(1)>",
            "niche": "roofing",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "PREVIEW"
    assert body["published"] is False
    assert body["execution_authority"] == "none"
    assert "url" not in body
    assert "artifact_path" not in body
    assert "<script>" not in body["html"]
    assert "&lt;script&gt;" in body["html"]
    assert "<img" not in body["html"]


def test_media_schedule_is_preview_only():
    response = client.post(
        "/v1/media/schedule",
        json={"channel": "linkedin", "at": "tomorrow"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scheduled"] is False
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
