"""Encrypted local vault, strict Google token exchange and owner-grant bridge."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3
from urllib.parse import quote

from cryptography.fernet import Fernet
import pytest

from empire_os.inbound_calendar_token_vault import (
    CalendarCredential, OfflineCalendarCredentialVault,
)
from empire_os.inbound_google_oauth_exchange import (
    exchange_google_pkce_code, refresh_google_calendar_access,
    GoogleOAuthTokenHTTP,
)
from empire_os.inbound_google_calendar_credentials import (
    VaultBackedGoogleCalendarResolver, verify_google_calendar_access_role,
)
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarVerificationError, GoogleCalendarReadOnlyHTTP,
)
from empire_os.inbound_calendar_oauth_onboarding import OneTimeGoogleCodeTicket
from empire_os.inbound_calendar_oauth_boundary import (
    CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "owner-calendar@example.com"
SCOPE = frozenset({EVENTS_READ, CALENDAR_FREEBUSY, CALENDAR_LIST_READ})
GOOGLE_CLIENT = "customer-calendar-oauth.apps.googleusercontent.com"


def owned():
    return ApprovedCalendarBinding(
        tenant_id="tenant-a", calendar_id=CAL,
        provider_account_ref="approved-google-account",
        owner_approved=True, account_access_verified=True,
    )


def cred(*, tenant="tenant-a", calendar=CAL, expires=NOW + timedelta(minutes=20),
         access="access-token-value-should-be-secret", refresh="refresh-token-value-should-be-secret"):
    return CalendarCredential(
        tenant_id=tenant, calendar_id=calendar,
        provider_account_ref="approved-google-account",
        google_client_id=GOOGLE_CLIENT,
        access_token=access, refresh_token=refresh,
        scopes=SCOPE, issued_at=NOW - timedelta(minutes=2),
        expires_at=expires, customer_approved=True, provider_grant_verified=True,
    )


class FakeEndpoint:
    def __init__(self, payload):
        self.payload = payload
        self.fields = []

    def post_form(self, fields):
        self.fields.append(fields.copy())
        return self.payload


def google_grant(**kwargs):
    default = {
        "access_token": "new-google-access-token",
        "refresh_token": "new-google-refresh-token",
        "token_type": "Bearer", "expires_in": 1800,
        "scope": " ".join(sorted(SCOPE)),
    }
    default.update(kwargs)
    return default


def test_vault_encrypts_material_on_disk_and_does_not_echo_tokens(tmp_path):
    file = tmp_path / "private-vault.db"
    key = Fernet.generate_key()
    with OfflineCalendarCredentialVault(file, active_key=key) as vault:
        vault.put_verified_offline(cred(), at=NOW)
        assert vault.get_active(
            tenant_id="tenant-a", calendar_id=CAL,
            provider_account_ref="approved-google-account",
        ) == cred()
        assert vault.status(tenant_id="tenant-a")["active_local_credentials"] == 1
        assert vault.status(tenant_id="tenant-b")["active_local_credentials"] == 0
        assert "should-be-secret" not in str(cred())
    assert file.stat().st_mode & 0o077 == 0
    assert b"access-token-value-should-be-secret" not in file.read_bytes()
    assert b"refresh-token-value-should-be-secret" not in file.read_bytes()


def test_wrong_tenant_account_and_new_calendar_reassignment_denied(tmp_path):
    with OfflineCalendarCredentialVault(tmp_path / "vault.db", active_key=Fernet.generate_key()) as vault:
        vault.put_verified_offline(cred(), at=NOW)
        with pytest.raises(CalendarVerificationError, match="not_active_or_not_owned"):
            vault.get_active(
                tenant_id="tenant-b", calendar_id=CAL,
                provider_account_ref="approved-google-account",
            )
        with pytest.raises(CalendarVerificationError, match="cross_tenant_overwrite"):
            vault.put_verified_offline(cred(tenant="tenant-b"), at=NOW)


def test_explicit_revocation_deletes_encrypted_secret_and_disallows_reuse(tmp_path):
    path = tmp_path / "vault.db"
    with OfflineCalendarCredentialVault(path, active_key=Fernet.generate_key()) as vault:
        vault.put_verified_offline(cred(), at=NOW)
        assert vault.revoke_local(
            tenant_id="tenant-a", calendar_id=CAL,
            provider_account_ref="approved-google-account", at=NOW,
        )
        assert not vault.revoke_local(
            tenant_id="tenant-a", calendar_id=CAL,
            provider_account_ref="approved-google-account", at=NOW,
        )
        with pytest.raises(CalendarVerificationError, match="not_active"):
            vault.get_active(
                tenant_id="tenant-a", calendar_id=CAL,
                provider_account_ref="approved-google-account",
            )
        with pytest.raises(CalendarVerificationError, match="requires_new_explicit_onboarding"):
            vault.put_verified_offline(cred(), at=NOW)
        assert vault.status(tenant_id="tenant-a")["revoked_local_credentials"] == 1
    assert b"access-token-value" not in path.read_bytes()


def test_key_rotation_and_wrong_key_fail_closed(tmp_path):
    path = tmp_path / "vault.db"
    old, new = Fernet.generate_key(), Fernet.generate_key()
    with OfflineCalendarCredentialVault(path, active_key=old) as vault:
        vault.put_verified_offline(cred(), at=NOW)
    with OfflineCalendarCredentialVault(
        path, active_key=new, previous_keys=(old,)
    ) as vault:
        assert vault.rotate_encryption_offline() == 1
    with OfflineCalendarCredentialVault(path, active_key=new) as vault:
        assert vault.get_active(
            tenant_id="tenant-a", calendar_id=CAL,
            provider_account_ref="approved-google-account",
        ).access_token == "access-token-value-should-be-secret"
    with OfflineCalendarCredentialVault(path, active_key=old) as vault:
        with pytest.raises(CalendarVerificationError, match="decryption_failed"):
            vault.get_active(
                tenant_id="tenant-a", calendar_id=CAL,
                provider_account_ref="approved-google-account",
            )


def test_existing_world_readable_vault_rejected(tmp_path):
    path = tmp_path / "bad.db"
    path.write_bytes(b"not a safe vault")
    path.chmod(0o644)
    with pytest.raises(CalendarVerificationError, match="owner_only"):
        OfflineCalendarCredentialVault(path, active_key=Fernet.generate_key())


def test_exchange_requires_one_time_ticket_client_match_and_narrow_scopes():
    ticket = OneTimeGoogleCodeTicket(
        tenant_id="tenant-a", admin_subject="approved-admin",
        client_id=GOOGLE_CLIENT, redirect_uri="https://example.org/oauth/callback",
        authorization_code="mock-code", code_verifier="mock-pkce",
    )
    endpoint = FakeEndpoint(google_grant())
    result = exchange_google_pkce_code(
        ticket, expected_client_id=GOOGLE_CLIENT,
        client_secret="mock-client-secret", endpoint=endpoint, now=NOW,
    )
    assert result.granted_scopes == SCOPE
    assert endpoint.fields[0]["code_verifier"] == "mock-pkce"
    assert result.refresh_token == "new-google-refresh-token"
    assert "new-google-access-token" not in repr(result)
    with pytest.raises(CalendarVerificationError, match="client_not_authorized"):
        exchange_google_pkce_code(
            ticket, expected_client_id="another-client", client_secret="secret",
            endpoint=endpoint, now=NOW,
        )
    assert len(endpoint.fields) == 1


@pytest.mark.parametrize("response", [
    google_grant(scope="https://www.googleapis.com/auth/calendar"),
    google_grant(scope=EVENTS_READ + " " + CALENDAR_FREEBUSY),
    google_grant(refresh_token=None),
    google_grant(token_type="MAC"),
    google_grant(expires_in=999999),
    google_grant(access_token=None),
])
def test_invalid_google_grants_rejected(response):
    ticket = OneTimeGoogleCodeTicket(
        tenant_id="tenant-a", admin_subject="admin", client_id=GOOGLE_CLIENT,
        redirect_uri="https://example.org/oauth/callback",
        authorization_code="mock-code", code_verifier="mock-verifier",
    )
    with pytest.raises(CalendarVerificationError):
        exchange_google_pkce_code(
            ticket, expected_client_id=GOOGLE_CLIENT,
            client_secret="secret", endpoint=FakeEndpoint(response), now=NOW,
        )


def test_refresh_keeps_prior_grant_scope_if_google_omits_scope():
    endpoint = FakeEndpoint({
        "access_token": "refreshed-access-token", "expires_in": 1200,
        "token_type": "Bearer",
    })
    grant = refresh_google_calendar_access(
        client_id=GOOGLE_CLIENT, client_secret="private-client-secret",
        refresh_token="original-refresh-token",
        prior_scopes=SCOPE, endpoint=endpoint, now=NOW,
    )
    assert grant.granted_scopes == SCOPE
    assert grant.refresh_token == "original-refresh-token"
    assert endpoint.fields[0]["grant_type"] == "refresh_token"
    assert endpoint.fields[0]["refresh_token"] == "original-refresh-token"


def test_scope_expansion_on_refresh_is_denied():
    endpoint = FakeEndpoint(google_grant(
        scope="https://www.googleapis.com/auth/calendar " + " ".join(sorted(SCOPE)),
    ))
    with pytest.raises(CalendarVerificationError):
        refresh_google_calendar_access(
            client_id=GOOGLE_CLIENT, client_secret="secret", refresh_token="refresh",
            prior_scopes=SCOPE, endpoint=endpoint, now=NOW,
        )


def test_vault_resolver_gets_valid_token_and_refreshes_near_expiry(tmp_path):
    path = tmp_path / "vault.db"
    endpoint = FakeEndpoint({
        "access_token": "fresh-access-token",
        "token_type": "Bearer", "expires_in": 1200,
    })
    with OfflineCalendarCredentialVault(path, active_key=Fernet.generate_key()) as vault:
        vault.put_verified_offline(cred(expires=NOW + timedelta(seconds=20)), at=NOW)
        resolver = VaultBackedGoogleCalendarResolver(
            vault=vault, token_endpoint=endpoint,
            client_secret_provider=lambda cid: "private-client-secret",
            now_provider=lambda: NOW,
        )
        lease, access = resolver.acquire(binding=owned())
        assert access == "fresh-access-token"
        assert lease.granted_scopes == SCOPE
        assert lease.expires_at == NOW + timedelta(minutes=20)
        assert len(endpoint.fields) == 1
        assert resolver.acquire(binding=owned())[1] == access
        assert len(endpoint.fields) == 1


def test_vault_resolver_denies_revoked_before_refresh(tmp_path):
    with OfflineCalendarCredentialVault(tmp_path / "vault.db", active_key=Fernet.generate_key()) as vault:
        vault.put_verified_offline(cred(), at=NOW)
        vault.revoke_local(
            tenant_id="tenant-a", calendar_id=CAL,
            provider_account_ref="approved-google-account", at=NOW,
        )
        endpoint = FakeEndpoint(google_grant())
        resolver = VaultBackedGoogleCalendarResolver(
            vault=vault, token_endpoint=endpoint,
            client_secret_provider=lambda cid: "secret",
            now_provider=lambda: NOW,
        )
        with pytest.raises(CalendarVerificationError, match="not_active"):
            resolver.acquire(binding=owned())
        assert endpoint.fields == []


class ListTransport:
    def __init__(self, access_role="owner", calendar_id=CAL):
        self.role = access_role
        self.id = calendar_id
        self.calls = []

    def fetch(self, *, method, path, token, body=None):
        self.calls.append((method, path))
        assert token == "active-token" and body is None
        return {"id": self.id, "accessRole": self.role}


def test_google_calendar_access_role_requires_exact_calendar_identity():
    transport = ListTransport()
    result = verify_google_calendar_access_role(
        binding=owned(), token="active-token",
        granted_scopes=SCOPE, transport=transport,
    )
    assert result.google_access_role == "owner"
    assert not result.calendar_write_authorized
    assert transport.calls == [
        ("GET", "/calendar/v3/users/me/calendarList/" + quote(CAL, safe=""))
    ]
    for role in ("reader", "freeBusyReader"):
        with pytest.raises(CalendarVerificationError, match="private_access_denied"):
            verify_google_calendar_access_role(
                binding=owned(), token="active-token",
                granted_scopes=SCOPE, transport=ListTransport(access_role=role),
            )
    with pytest.raises(CalendarVerificationError, match="identity_mismatch"):
        verify_google_calendar_access_role(
            binding=owned(), token="active-token",
            granted_scopes=SCOPE,
            transport=ListTransport(calendar_id="intruder@example.org"),
        )


def test_google_calendar_access_requires_explicit_calendar_list_scope():
    with pytest.raises(CalendarVerificationError, match="list_read_scope"):
        verify_google_calendar_access_role(
            binding=owned(), token="active-token",
            granted_scopes=frozenset({EVENTS_READ, CALENDAR_FREEBUSY}),
            transport=ListTransport(),
        )


def test_token_transport_allowlist_refuses_non_google_token_grants():
    from empire_os.inbound_google_oauth_exchange import GoogleOAuthTokenHTTP
    transport = GoogleOAuthTokenHTTP()
    with pytest.raises(CalendarVerificationError, match="invalid_oauth_token_request"):
        transport.post_form({"grant_type": "password", "username": "anything"})


def test_calendar_http_transport_allows_only_readonly_calendar_list_get():
    transport = GoogleCalendarReadOnlyHTTP()
    for method, path in [
        ("POST", "/calendar/v3/users/me/calendarList/" + quote(CAL, safe="")),
        ("DELETE", "/calendar/v3/users/me/calendarList/" + quote(CAL, safe="")),
    ]:
        with pytest.raises(CalendarVerificationError, match="method_denied"):
            transport.fetch(method=method, path=path, token="dummy-token")
