from empire_os.voice_gateway_api import (
    build_vonage_ncco,
    map_vonage_status,
)


def test_vonage_ncco_uses_empire_voice_lab_websocket(monkeypatch):
    monkeypatch.setenv("EMPIRE_VOICE_WS_TOKEN", "ws-secret")
    monkeypatch.setenv(
        "EMPIRE_PUBLIC_BASE_URL",
        "https://empire-ai.co.uk",
    )

    ncco = build_vonage_ncco(
        intent_id="intent-1",
        prospect_id="prospect-1",
        context={
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "metro": "Austin",
        },
    )

    endpoint = ncco[0]["endpoint"][0]
    assert ncco[0]["action"] == "connect"
    assert endpoint["type"] == "websocket"
    assert endpoint["content-type"] == "audio/l16;rate=16000"
    assert endpoint["uri"].startswith(
        "wss://empire-ai.co.uk/v1/voice-lab/vonage/socket?"
    )
    assert "intent_id=intent-1" in endpoint["uri"]
    assert endpoint["headers"]["voice_engine"] == "empire_voice_lab"
    assert endpoint["authorization"] == {
        "type": "custom",
        "value": "Bearer ws-secret",
    }


def test_vonage_status_mapping_is_voice_specific():
    assert map_vonage_status("ringing") == "call_ringing"
    assert map_vonage_status("answered") == "call_answered"
    assert map_vonage_status("completed") == "call_completed"
    assert map_vonage_status("busy") == "call_busy"
    assert map_vonage_status("unanswered") == "call_unanswered"
    assert map_vonage_status("failed") == "call_failed"
    assert map_vonage_status("mystery") is None
