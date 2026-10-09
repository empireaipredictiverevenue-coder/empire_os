import empire_os.voice_gateway_api as voice_gateway_api
from empire_os.voice_gateway_api import (
    _record_turn,
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
        call_id="call-1",
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
    assert "call_id=call-1" in endpoint["uri"]
    assert endpoint["headers"]["voice_engine"] == "empire_voice_lab"
    assert endpoint["headers"]["call_id"] == "call-1"
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


def test_record_turn_persists_decision_judge_evidence(monkeypatch):
    captured = {}

    def fake_request_json(method, path, payload=None):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(
        voice_gateway_api,
        "request_json",
        fake_request_json,
    )

    decision = {
        "schema_version": "empire.decision_judge.v1",
        "action": "clarify",
        "confidence": 0.45,
    }
    result = _record_turn(
        "intent-1",
        "call-1",
        2,
        "inbound",
        "Now external voice vendor is being used.",
        {"decision_judge": decision},
    )

    assert result == {"ok": True}
    evidence = captured["payload"]["p_evidence"]
    assert evidence["stt"] == "sherpa_whisper"
    assert evidence["decision_judge"] == decision


def test_gateway_source_contains_streaming_zipformer_observation_lane():
    """
    Contract guard: gateway feeds a persistent Zipformer stream while
    speech is arriving, before the completed utterance response path.
    """
    from pathlib import Path

    source = Path("empire_os/voice_gateway_api.py").read_text()

    assert "streaming_asr = lab.verifier_stt" in source
    assert "streaming_asr.create_stream()" in source
    assert "streaming_asr.accept_pcm(" in source
    assert "streaming_asr.finish_stream(" in source


def test_gateway_streaming_partial_is_observation_only():
    """
    Partial ASR must not be passed directly into the closer or recorder.
    """
    from pathlib import Path

    source = Path("empire_os/voice_gateway_api.py").read_text()

    assert "Partial transcripts MUST NOT authorize commercial actions." in source
    assert "respond(streaming_partial" not in source
    assert "_record_turn(streaming_partial" not in source


def test_gateway_fast_and_fallback_share_guarded_consumer():
    from pathlib import Path

    source = Path("empire_os/voice_gateway_api.py").read_text()

    assert "async def consume_result(" in source
    assert "async def respond_fast(" in source
    assert "async def respond_fallback(" in source
    assert "await consume_result(result, index, generation)" in source
    assert 'result.setdefault("asr_mode", "dual_fallback")' in source


def test_gateway_has_stale_barrier_before_playback():
    from pathlib import Path

    source = Path("empire_os/voice_gateway_api.py").read_text()

    consumer = source[
        source.index("    async def consume_result("):
        source.index("    async def respond_fast(")
    ]

    assert consumer.count("generation != turn_generation") >= 3
    assert consumer.index("generation != turn_generation") < consumer.index(
        "history.append"
    )
    assert consumer.rindex("generation != turn_generation") < consumer.index(
        "await start_playback(response_text)"
    )


def test_gateway_barge_in_clear_is_not_conditioned_on_live_local_task():
    from pathlib import Path

    source = Path("empire_os/voice_gateway_api.py").read_text()

    start = source.index("    async def stop_playback()")
    end = source.index("    async def consume_result(", start)
    block = source[start:end]

    assert "playback_may_be_buffered" in block
    assert 'websocket.send_text(json.dumps({"action": "clear"}))' in block
