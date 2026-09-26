from empire_os.vonage_call_transport import (
    VonageCallConfig,
    VonageCallTransport,
)


def config():
    return VonageCallConfig(
        application_id="app-1",
        private_key="not-used-in-build-request",
        virtual_number="+12026401234",
        answer_url=(
            "https://empire-ai.co.uk/v1/voice-lab/vonage/answer"
        ),
        event_url=(
            "https://empire-ai.co.uk/v1/voice-lab/vonage/event"
        ),
        live_authority=True,
    )


def test_call_request_binds_callbacks_to_canonical_context(monkeypatch):
    monkeypatch.setenv("EMPIRE_VONAGE_WEBHOOK_TOKEN", "hook-secret")
    monkeypatch.setenv("EMPIRE_VOICE_WS_TOKEN", "ws-secret")
    transport = VonageCallTransport(config())

    body = transport.build_request({
        "intent_id": "00000000-0000-0000-0000-000000000101",
        "prospect_id": "00000000-0000-0000-0000-000000000201",
        "phone": "+13106401234",
    })

    assert body["to"][0]["number"] == "13106401234"
    answer = body["answer_url"][0]
    event = body["event_url"][0]
    assert "intent_id=00000000-0000-0000-0000-000000000101" in answer
    assert "prospect_id=00000000-0000-0000-0000-000000000201" in answer
    assert "token=hook-secret" in answer
    assert "intent_id=00000000-0000-0000-0000-000000000101" in event


def test_readiness_requires_both_callback_tokens(monkeypatch):
    monkeypatch.delenv("EMPIRE_VONAGE_WEBHOOK_TOKEN", raising=False)
    monkeypatch.delenv("EMPIRE_VOICE_WS_TOKEN", raising=False)
    readiness = config().readiness()
    assert readiness["configured"] is False
    assert "EMPIRE_VONAGE_WEBHOOK_TOKEN" in readiness["missing"]
    assert "EMPIRE_VOICE_WS_TOKEN" in readiness["missing"]
