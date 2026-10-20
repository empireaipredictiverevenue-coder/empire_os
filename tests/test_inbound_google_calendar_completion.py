"""End-to-end offline proof for authenticated owner → Google OAuth → vault."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.inbound_calendar_connection_api import create_calendar_connection_router
from empire_os.inbound_calendar_connection_identity import CalendarConnectionPrincipal
from empire_os.inbound_calendar_oauth_onboarding import OneTimeGoogleCodeTicket
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_calendar_token_vault import OfflineCalendarCredentialVault
from empire_os.inbound_google_calendar_adapter import CalendarVerificationError
from empire_os.inbound_google_calendar_completion import ApprovedGoogleCalendarCompletion
from empire_os.inbound_calendar_oauth_boundary import (
    CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
SUBJECT = "real-owner-from-crm"
CAL = "customer-calendar@example.org"
CLIENT = "example-client-id.apps.googleusercontent.com"
ORIGIN = "https://app.example.test"
PREFIX = "/v1/inbound-recovery/calendar-connect"
CALLBACK = ORIGIN + PREFIX + "/callback"
NOW = datetime(2026, 10, 20, 16, tzinfo=timezone.utc)
SCOPES = frozenset({CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ})


class MockTokenEndpoint:
    def __init__(self, *, scope=None):
        self.scope = scope or " ".join(sorted(SCOPES))
        self.calls = []

    def post_form(self, payload):
        self.calls.append(dict(payload))
        return {
            "token_type": "Bearer", "expires_in": 1800,
            "access_token": "fixture-google-access-secret",
            "refresh_token": "fixture-google-refresh-secret",
            "scope": self.scope,
        }


class MockReadOnlyGoogle:
    def __init__(self, *, role="owner", calendar=CAL):
        self.role, self.calendar = role, calendar
        self.calls = []

    def fetch(self, *, method, path, token, body=None):
        self.calls.append((method, path))
        assert method == "GET"
        assert path == "/calendar/v3/users/me/calendarList/" + quote(CAL, safe="")
        assert token == "fixture-google-access-secret"
        assert body is None
        return {"id": self.calendar, "accessRole": self.role}


def principal(tenant=TENANT, *, role="owner", subject=SUBJECT):
    return CalendarConnectionPrincipal(tenant, subject, "unique-token-id-verified", role)


def ticket(tenant=TENANT, *, selected_calendar=CAL, subject=SUBJECT):
    return OneTimeGoogleCodeTicket(
        tenant_id=tenant, admin_subject=subject, client_id=CLIENT,
        redirect_uri=CALLBACK, authorization_code="fixture-code",
        code_verifier="fixture-pkce", selected_calendar_id=selected_calendar,
    )


def assembly(tmp_path, *, token=None, provider=None, role_active=True,
             approved=True, account_ref="authorized-calendar-account"):
    encryption_key = Fernet.generate_key()
    def open_vault():
        return OfflineCalendarCredentialVault(
            tmp_path / "vault.db", active_key=encryption_key,
        )
    def open_registry():
        return OfflineCalendarRegistry(tmp_path / "registry.db")
    vault = open_vault()
    registry = open_registry()
    endpoint = token or MockTokenEndpoint()
    google = provider or MockReadOnlyGoogle()
    seen = []

    def owner_live(subject, tenant):
        seen.append(("membership", subject, tenant))
        return role_active and subject == SUBJECT and tenant == TENANT

    def approved_calendar(tenant, subject, selected):
        seen.append(("approved_binding", tenant, subject, selected))
        if approved and tenant == TENANT and subject == SUBJECT and selected == CAL:
            return account_ref
        return None

    completion = ApprovedGoogleCalendarCompletion(
        expected_client_id=CLIENT, expected_redirect_uri=CALLBACK,
        client_secret_provider=lambda: "fixture-client-secret",
        account_binding=approved_calendar,
        token_endpoint=endpoint, calendar_transport=google,
        open_vault=open_vault, open_registry=open_registry,
        owner_membership_check=owner_live,
        evidence_key=b"server-held-owner-approval-evidence-key-32-bytes",
        now=lambda: NOW,
    )
    return completion, vault, registry, endpoint, google, seen


def test_customer_owner_completed_credential_is_encrypted_and_registry_verified(tmp_path):
    completion, vault, registry, endpoint, google, seen = assembly(tmp_path)
    try:
        result = completion(ticket(), principal())
        assert result.credential_vault_write
        assert result.calendar_binding_created
        assert result.tenant_id == TENANT
        assert registry.get_binding(CAL).provider_account_ref == "authorized-calendar-account"
        credential = vault.get_active(
            tenant_id=TENANT, calendar_id=CAL,
            provider_account_ref="authorized-calendar-account",
        )
        assert credential.refresh_token == "fixture-google-refresh-secret"
        assert credential.customer_approved
        assert b"fixture-google-refresh-secret" not in (tmp_path / "vault.db").read_bytes()
        assert b"fixture-google-refresh-secret" not in (tmp_path / "registry.db").read_bytes()
        assert len(endpoint.calls) == 1
        assert len(google.calls) == 1
        assert seen == [
            ("membership", SUBJECT, TENANT),
            ("approved_binding", TENANT, SUBJECT, CAL),
        ]
    finally:
        vault.db.close()
        registry.db.close()


@pytest.mark.parametrize("kind", [
    "revoked", "unapproved", "wrong_tenant", "wrong_subject", "wrong_calendar",
    "viewer", "wrong_oauth_client", "wrong_redirect",
])
def test_wrong_owner_consent_or_oauth_ticket_cannot_exchange_tokens(tmp_path, kind):
    kwargs = {
        "role_active": kind != "revoked",
        "approved": kind != "unapproved",
    }
    completion, vault, registry, endpoint, google, _ = assembly(tmp_path, **kwargs)
    current_ticket = ticket(
        tenant=OTHER if kind == "wrong_tenant" else TENANT,
        selected_calendar="other-calendar@example.org" if kind == "wrong_calendar" else CAL,
        subject="different-subject" if kind == "wrong_subject" else SUBJECT,
    )
    if kind == "wrong_oauth_client":
        current_ticket = OneTimeGoogleCodeTicket(
            tenant_id=TENANT, admin_subject=SUBJECT, client_id="wrong-client",
            redirect_uri=CALLBACK, authorization_code="code",
            code_verifier="pkce", selected_calendar_id=CAL,
        )
    if kind == "wrong_redirect":
        current_ticket = OneTimeGoogleCodeTicket(
            tenant_id=TENANT, admin_subject=SUBJECT, client_id=CLIENT,
            redirect_uri="https://phishing.example.test/callback",
            authorization_code="code", code_verifier="pkce", selected_calendar_id=CAL,
        )
    current_principal = principal(role="viewer" if kind == "viewer" else "owner")
    try:
        with pytest.raises(CalendarVerificationError):
            completion(current_ticket, current_principal)
        assert endpoint.calls == []
        assert google.calls == []
        assert registry.get_binding(CAL) is None
        assert vault.status(tenant_id=TENANT)["active_local_credentials"] == 0
    finally:
        vault.db.close()
        registry.db.close()


@pytest.mark.parametrize("scope,role,cal", [
    (" ".join(sorted(SCOPES)), "reader", CAL),
    ("https://www.googleapis.com/auth/calendar", "owner", CAL),
    (" ".join(sorted(SCOPES)), "owner", "other-calendar@example.org"),
])
def test_google_readback_denial_does_not_write_credentials(tmp_path, scope, role, cal):
    endpoint = MockTokenEndpoint(scope=scope)
    google = MockReadOnlyGoogle(role=role, calendar=cal)
    completion, vault, registry, endpoint, google, _ = assembly(
        tmp_path, token=endpoint, provider=google,
    )
    try:
        with pytest.raises(CalendarVerificationError):
            completion(ticket(), principal())
        assert len(endpoint.calls) == 1
        assert registry.get_binding(CAL) is None
        assert vault.status(tenant_id=TENANT)["active_local_credentials"] == 0
    finally:
        vault.db.close()
        registry.db.close()


def test_full_guarded_http_flow_uses_actual_enrollment_and_registry_readback(tmp_path):
    completion, vault, registry, endpoint, google, seen = assembly(tmp_path)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(create_calendar_connection_router(
        enabled=True,
        verify_bearer=lambda req: principal(),
        verify_browser_session=lambda req: principal(),
        complete_callback=completion,
        state_db=tmp_path / "oauth-state.db",
        state_encryption_key=Fernet.generate_key(),
        google_client_id=CLIENT, redirect_uri=CALLBACK,
        application_origin=ORIGIN, calendar_db=tmp_path / "registry.db",
        clock=lambda: NOW,
    ))
    try:
        client = TestClient(app, base_url=ORIGIN)
        start = client.post(
            PREFIX + "/start",
            headers={"Origin": ORIGIN, "Authorization": "Bearer test-only"},
            json={"calendar_id": CAL, "customer_approved_read_only": True},
        )
        assert start.status_code == 200, start.text
        consent_state = parse_qs(
            urlsplit(start.json()["authorization_url"]).query
        )["state"][0]
        confirmed = client.get(
            PREFIX + "/callback",
            params={"code": "fixture-google-consent-code", "state": consent_state},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["connected"] is True
        assert confirmed.json()["booking_creation_authorized"] is False
        assert len(google.calls) == 1
        assert len(endpoint.calls) == 1
        again = client.get(
            PREFIX + "/callback",
            params={"code": "fixture-google-consent-code", "state": consent_state},
        )
        assert again.status_code == 403
        assert len(endpoint.calls) == 1
    finally:
        vault.db.close()
        registry.db.close()
