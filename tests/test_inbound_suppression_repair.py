from fastapi.testclient import TestClient

from empire_os.outbound_role_transport import ROLE_FUNCTIONS
from empire_os.resend_webhook_app import create_app


INTENT = "00000000-0000-0000-0000-000000000001"
HEADERS = {"svix-id": "test", "svix-timestamp": "123", "svix-signature": "v1,test"}


def client(body, calls, *, rpc=True):
    event = {"type": "email.received", "data": {
        "email_id": "test-reply", "from": "buyer@example.com",
        "to": [f"reply+{INTENT}@example.com"], "subject": "Re: proposal",
        "created_at": "2026-09-29T00:31:01Z",
    }}

    def record(name, params):
        calls.append((name, params))
        return {"reply_id": "test-id", "classification": params.get("p_classification")}

    return TestClient(create_app(
        verify_webhook=lambda _: event,
        fetch_email=lambda _: {**event["data"], "text": body},
        reply_rpc=record if rpc else None,
        webhook_secret="whsec_test", reply_to="reply@example.com",
        reply_forward_to="",
    ))


def test_opt_out_reply_is_classified_and_original_evidence_preserved():
    calls = []
    body = 'Opt out\nOn Mon, someone wrote:\n> Reply "opt out".'
    response = client(body, calls).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert response.status_code == 200
    assert calls[0][1]["p_body_text"] == body
    assert calls[1][1]["p_classification"] == "unsubscribe"
    assert calls[1][1]["p_confidence"] == 0.99


def test_quoted_outbound_footer_does_not_suppress_interested_buyer():
    calls = []
    response = client('Interested, tell me more.\nOn Mon, someone wrote:\n> Reply "opt out".', calls).post(
        "/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert response.status_code == 200
    assert calls[1][1]["p_classification"] == "positive"


def test_missing_dedicated_dsn_fails_closed_without_generic_transport(monkeypatch):
    monkeypatch.delenv("EMPIRE_REPLY_INGEST_DSN", raising=False)
    c = client("Opt out", [], rpc=False)
    assert c.get("/health").status_code == 503
    assert c.get("/health").json()["reply_transport_configured"] is False
    assert c.post("/webhooks/resend-inbound", content="{}", headers=HEADERS).status_code == 503


def test_classification_float_is_explicitly_cast_to_database_numeric():
    sql, keys = ROLE_FUNCTIONS["empire_reply_ingest"]["classify_outbound_reply"]
    assert sql == "select public.classify_outbound_reply(%s,%s,%s::numeric,%s)"
    assert keys[2] == "p_confidence"
