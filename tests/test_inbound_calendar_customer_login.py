"""Native CRM customer owner login, purpose-separated calendar OAuth identity."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.inbound_calendar_customer_login import (
    create_calendar_owner_login_router, build_calendar_owner_resolvers,
)
from empire_os.inbound_calendar_connection_api import create_calendar_connection_router
from empire_os.inbound_calendar_connection_identity import (
    BROWSER_COOKIE, CalendarIdentityDenied, SignedCalendarConnectionVerifier,
)
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_google_calendar_adapter import ApprovedCalendarBinding
from empire_os.inbound_google_calendar_enrollment import GoogleCalendarEnrollmentResult
from empire_os.revenue_crm_first_party_login import (
    PostgresCrmPasswordLogin, build_account_bound_membership_lookup,
)
from empire_os.saas_scale import TenantMembership

NOW = 1_800_000_000
ORIGIN = "https://app.example.test"
TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
CAL = "example-calendar@example.org"
PREFIX = "/v1/inbound-recovery/calendar-connect"
LOGIN = "/v1/inbound-recovery/calendar-auth/login"
PASSWORD = "very-long-test-only-password-not-real"


class FakeCanonicalCRMLogin(PostgresCrmPasswordLogin):
    """In-memory stand-in for existing invite-only password and account state."""

    def __init__(self):
        self.account_active = True
        self.login_attempts = 0

    def authenticate(self, email, password):
        self.login_attempts += 1
        if email == "owner@example.test" and password == PASSWORD and self.account_active:
            return "owner:verified"
        return None

    def active_account(self, subject):
        return self.account_active and subject == "owner:verified"


def setup(tmp_path=None):
    password_login = FakeCanonicalCRMLogin()
    state = {"role": "owner", "membership_status": "active"}
    calls = []

    def canonical_membership(subject, tenant):
        calls.append((subject, tenant))
        if tenant != TENANT:
            return None
        return TenantMembership(
            tenant_id=tenant, user_id=subject,
            role=state["role"], status=state["membership_status"],
        )

    # Critically: same account-bound first-party CRM membership lookup as
    # native EmpireOS CRM. Revoking account blocks cookie and bearer alike.
    lookup = build_account_bound_membership_lookup(password_login, canonical_membership)
    key = Ed25519PrivateKey.generate()
    public_keys = {"existing-crm-issuer": key.public_key()}
    bearer, browser = build_calendar_owner_resolvers(
        public_keys, load_membership=lookup, now=lambda: NOW,
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(create_calendar_owner_login_router(
        password_login=password_login, load_membership=lookup, signing_key=key,
        key_id="existing-crm-issuer", application_origin=ORIGIN, now=lambda: NOW,
    ))
    if tmp_path is not None:
        db = tmp_path / "calendar.db"
        with OfflineCalendarRegistry(db):
            pass

        def provider_completion(ticket, principal):
            # TEST FIXTURE: simulate independent provider role read-back and
            # durable enrollment; the real adapter is enrolled separately.
            with OfflineCalendarRegistry(db) as registry:
                registry.register_binding_offline(ApprovedCalendarBinding(
                    tenant_id=principal.tenant_id,
                    calendar_id=ticket.selected_calendar_id,
                    provider_account_ref="test-provider-owner",
                    owner_approved=True, account_access_verified=True,
                ), approval_ref="test-only-simulated-google-proof")
            return GoogleCalendarEnrollmentResult(
                tenant_id=principal.tenant_id,
                calendar_id=ticket.selected_calendar_id,
                provider_account_ref="test-provider-owner",
                credential_vault_write=True, calendar_binding_created=True,
            )
        app.include_router(create_calendar_connection_router(
            enabled=True,
            verify_bearer=bearer, verify_browser_session=browser,
            complete_callback=provider_completion,
            state_db=tmp_path / "oauth-state.db",
            state_encryption_key=Fernet.generate_key(),
            google_client_id="test-google-client.apps.googleusercontent.com",
            redirect_uri=ORIGIN + PREFIX + "/callback",
            application_origin=ORIGIN,
            calendar_db=db,
            clock=lambda: datetime.fromtimestamp(NOW, timezone.utc),
        ))
    return TestClient(app, base_url=ORIGIN), password_login, state, calls, public_keys, lookup


def login(client, *, email="owner@example.test", password=PASSWORD, tenant=TENANT,
          origin=ORIGIN, consent=True):
    return client.post(LOGIN, headers={"Origin": origin}, json={
        "email": email, "password": password, "tenant_id": tenant,
        "customer_approved_read_only": consent,
    })


def test_native_owner_login_uses_new_calendar_only_identity_and_browser_cookie():
    client, _, _, calls, keys, lookup = setup()
    response = login(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "recovery:calendar:connect"
    assert body["calendar_connected"] is False
    assert body["expires_in"] == 300
    assert PASSWORD not in response.text
    assert BROWSER_COOKIE in client.cookies
    assert "Secure" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert response.headers["Cache-Control"] == "no-store"

    bearer = SignedCalendarConnectionVerifier(keys, load_membership=lookup, now=lambda: NOW)
    browser = SignedCalendarConnectionVerifier(
        keys, load_membership=lookup, now=lambda: NOW,
        credential_kind="browser_session",
    )
    assert bearer.authenticate(body["access_token"]).tenant_id == TENANT
    assert browser.authenticate(client.cookies[BROWSER_COOKIE]).subject == "owner:verified"
    with pytest.raises(CalendarIdentityDenied):
        bearer.authenticate(client.cookies[BROWSER_COOKIE])
    with pytest.raises(CalendarIdentityDenied):
        browser.authenticate(body["access_token"])
    assert calls == [("owner:verified", TENANT)] * 3


@pytest.mark.parametrize("override", [
    {"origin": "https://evil.example.test"},
    {"consent": False},
    {"password": "wrong-password-123"},
    {"tenant": "invalid-tenant"},
    {"tenant": OTHER},
])
def test_wrong_origin_consent_password_tenant_rejected(override):
    client, _, _, _, _, _ = setup()
    assert login(client, **override).status_code in (401, 403, 422)
    assert BROWSER_COOKIE not in client.cookies


@pytest.mark.parametrize("role", ["viewer", "operator", "analyst", "gtm_research_reviewer"])
def test_nonadmin_membership_does_not_get_calendar_credentials(role):
    client, _, state, _, _, _ = setup()
    state["role"] = role
    result = login(client)
    assert result.status_code == 401
    assert BROWSER_COOKIE not in client.cookies


def test_revoked_account_or_membership_blocks_issued_credentials():
    client, password_login, state, _, keys, lookup = setup()
    result = login(client)
    token = result.json()["access_token"]
    assert token
    password_login.account_active = False
    verifier = SignedCalendarConnectionVerifier(
        keys, load_membership=lookup, now=lambda: NOW,
    )
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(token)
    password_login.account_active = True
    state["membership_status"] = "disabled"
    with pytest.raises(CalendarIdentityDenied):
        verifier.authenticate(token)


def test_real_first_party_login_boundary_through_mock_calendar_callback(tmp_path):
    client, _, state, _, _, _ = setup(tmp_path)
    result = login(client)
    assert result.status_code == 200
    token = result.json()["access_token"]
    start = client.post(PREFIX + "/start",
        headers={"Origin": ORIGIN, "Authorization": "Bearer " + token},
        json={"calendar_id": CAL, "customer_approved_read_only": True},
    )
    assert start.status_code == 200, start.text
    assert start.json()["connection_created"] is False
    state_id = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
    callback = client.get(PREFIX + "/callback", params={"state": state_id, "code": "test-only-code"})
    assert callback.status_code == 200, callback.text
    assert callback.json()["connected"] is True
    assert callback.json()["calendar_write_authorized"] is False
    assert client.get(PREFIX + "/status",
        headers={"Authorization": "Bearer " + token},
    ).status_code == 200


def test_owner_revoked_between_start_and_callback_fails_closed(tmp_path):
    client, _, state, _, _, _ = setup(tmp_path)
    token = login(client).json()["access_token"]
    start = client.post(PREFIX + "/start",
        headers={"Origin": ORIGIN, "Authorization": "Bearer " + token},
        json={"calendar_id": CAL, "customer_approved_read_only": True},
    )
    state_id = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
    state["role"] = "viewer"
    callback = client.get(PREFIX + "/callback", params={"state": state_id, "code": "test-only-code"})
    assert callback.status_code == 401


def test_existing_crm_identity_bundle_uses_one_live_account_and_membership_source():
    from empire_os.inbound_calendar_customer_login import (
        build_calendar_identity_from_existing_crm,
    )
    password_login = FakeCanonicalCRMLogin()
    state = {"role": "owner"}
    def real_membership(subject, tenant):
        if tenant != TENANT:
            return None
        return TenantMembership(
            tenant_id=tenant, user_id=subject,
            role=state["role"], status="active",
        )
    bundle = build_calendar_identity_from_existing_crm(
        password_login=password_login,
        canonical_membership_lookup=real_membership,
        signing_key=Ed25519PrivateKey.generate(),
        key_id="first-party-crm",
        application_origin=ORIGIN,
        now=lambda: NOW,
    )
    assert bundle.live_account_and_membership_required
    assert bundle.public_routes_enabled is False
    app = FastAPI()
    app.include_router(bundle.login_router)
    client = TestClient(app, base_url=ORIGIN)
    result = login(client)
    assert result.status_code == 200
    token = result.json()["access_token"]
    state["role"] = "viewer"
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest
    from starlette.datastructures import Headers
    request = StarletteRequest({
        "type": "http", "method": "GET",
        "path": "/v1/inbound-recovery/calendar-connect/status",
        "headers": [(b"authorization", ("Bearer " + token).encode())],
    })
    with pytest.raises(CalendarIdentityDenied):
        bundle.verify_bearer(request)
