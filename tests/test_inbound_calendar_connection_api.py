"""Isolated loopback-only OAuth router gates and browser continuity tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.inbound_calendar_connection_api import create_calendar_connection_router
from empire_os.inbound_calendar_connection_identity import CalendarConnectionPrincipal
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_google_calendar_adapter import ApprovedCalendarBinding

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
BASE = "https://app.example.test"
CALLBACK = BASE + "/v1/inbound-recovery/calendar-connect/callback"
TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
GOOGLE = "client-id.apps.googleusercontent.com"
PREFIX = "/v1/inbound-recovery/calendar-connect"


def build(tmp_path, *, enabled=True, session=None, token=None, completed=None):
    state_db = tmp_path / "oauth-state.db"
    calendar_db = tmp_path / "calendar.db"
    with OfflineCalendarRegistry(calendar_db):
        pass
    active = CalendarConnectionPrincipal(
        tenant_id=TENANT, subject="actual-owner", token_id="verified-token-jti",
        role="owner",
    )
    session = [session if session is not None else active]
    token = [token if token is not None else active]
    records = []

    def complete(ticket, principal):
        records.append((ticket, principal))
        if completed is not None:
            return completed(ticket, principal)
        return False

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(create_calendar_connection_router(
        enabled=enabled,
        verify_bearer=lambda req: token[0],
        verify_browser_session=lambda req: session[0],
        complete_callback=complete,
        state_db=state_db,
        state_encryption_key=Fernet.generate_key(),
        google_client_id=GOOGLE,
        redirect_uri=CALLBACK,
        application_origin=BASE,
        calendar_db=calendar_db,
        clock=lambda: NOW,
    ))
    return TestClient(app, base_url=BASE), session, token, records, calendar_db


def start(client, *, origin=BASE, consent=True):
    headers = {"Origin": origin, "Authorization": "Bearer injected-by-authenticated-front-end"}
    return client.post(
        PREFIX + "/start",
        headers=headers,
        json={"calendar_id": "business-owned-calendar@example.org",
              "customer_approved_read_only": consent},
    )


def test_dark_by_default_has_no_calendar_oauth_activation():
    app = FastAPI()
    app.include_router(create_calendar_connection_router())
    client = TestClient(app, base_url=BASE)
    assert client.post(PREFIX + "/start", json={}).status_code in (404, 422)
    assert client.get(PREFIX + "/status").status_code == 404
    assert client.get(PREFIX + "/callback").status_code == 404


def test_enabled_without_identity_and_completion_rejected():
    with pytest.raises(ValueError, match="verified_backend_config"):
        create_calendar_connection_router(enabled=True)


def test_origin_consent_bearer_and_session_must_match(tmp_path):
    client, session, token, _, _ = build(tmp_path)
    assert start(client, origin="https://evil.example.org").status_code == 403
    assert start(client, consent=False).status_code == 403
    token[0] = None
    assert start(client).status_code == 401
    token[0] = CalendarConnectionPrincipal(TENANT, "actual-owner", "jti", "owner")
    session[0] = CalendarConnectionPrincipal(OTHER, "actual-owner", "jti", "owner")
    assert start(client).status_code == 403
    session[0] = CalendarConnectionPrincipal(TENANT, "someone-else", "jti", "owner")
    assert start(client).status_code == 403
    session[0] = CalendarConnectionPrincipal(TENANT, "actual-owner", "jti", "viewer")
    assert start(client).status_code == 401
    session[0] = token[0]
    okay = start(client)
    assert okay.status_code == 200, okay.text
    assert okay.json()["connection_created"] is False
    assert okay.json()["calendar_write_authorized"] is False
    assert "Secure" in okay.headers["set-cookie"]
    assert "HttpOnly" in okay.headers["set-cookie"]
    assert "samesite=lax" in okay.headers["set-cookie"].lower()
    assert okay.json()["authorization_url"].startswith("https://accounts.google.com/")
    assert okay.json()["expires_at"]


def test_oauth_callback_uses_exact_session_state_and_selected_calendar(tmp_path):
    client, session, token, calls, _ = build(tmp_path, completed=lambda *_: True)
    response = start(client)
    assert response.status_code == 200
    state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    done = client.get(PREFIX + "/callback", params={"state": state, "code": "test-code"})
    assert done.status_code == 200, done.text
    assert done.json() == {
        "connected": True, "tenant_id": TENANT,
        "calendar_write_authorized": False, "booking_creation_authorized": False,
    }
    assert calls[0][0].selected_calendar_id == "business-owned-calendar@example.org"
    assert calls[0][1].subject == "actual-owner"
    assert client.get(
        PREFIX + "/callback", params={"state": state, "code": "test-code"}
    ).status_code == 403  # one time
    assert len(calls) == 1


def test_callback_cannot_switch_session_or_replay_in_another_browser(tmp_path):
    client, session, token, calls, _ = build(tmp_path, completed=lambda *_: True)
    response = start(client)
    state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    session[0] = CalendarConnectionPrincipal(TENANT, "attacker", "different", "owner")
    denied = client.get(PREFIX + "/callback", params={"state": state, "code": "test-code"})
    assert denied.status_code == 403
    assert calls == []
    session[0] = token[0]
    # Session does not recover without the original browser nonce.
    client.cookies.clear()
    assert client.get(PREFIX + "/callback", params={
        "state": state, "code": "test-code",
    }).status_code == 403


def test_no_completion_adapter_can_claim_success(tmp_path):
    client, _, _, calls, _ = build(tmp_path)
    response = start(client)
    state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    denied = client.get(PREFIX + "/callback", params={"state": state, "code": "test-code"})
    assert denied.status_code == 403
    assert len(calls) == 1


def test_tenant_status_is_scoped_to_authenticated_owner(tmp_path):
    client, session, token, _, calendar_db = build(tmp_path)
    with OfflineCalendarRegistry(calendar_db) as registry:
        registry.register_binding_offline(ApprovedCalendarBinding(
            tenant_id=TENANT, calendar_id="secret-owned-calendar@example.org",
            provider_account_ref="scoped-google-account",
            owner_approved=True, account_access_verified=True,
        ), approval_ref="operator-verified-owner")
    response = client.get(PREFIX + "/status")
    assert response.status_code == 200
    assert response.json()["tenant_id"] == TENANT
    assert response.json()["access_tokens_returned"] is False
    assert "secret-owned-calendar" not in response.text
    token[0] = CalendarConnectionPrincipal(OTHER, "other-owner", "verified", "owner")
    other = client.get(PREFIX + "/status")
    assert other.status_code == 200
    assert other.json()["tenant_id"] == OTHER
    assert other.json()["tracked_appointments"] == 0
