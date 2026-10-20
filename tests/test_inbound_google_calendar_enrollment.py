"""Customer calendar enroll-before-read contract, isolated provider mocks."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from cryptography.fernet import Fernet
import pytest

from empire_os.inbound_calendar_oauth_onboarding import OneTimeGoogleCodeTicket
from empire_os.inbound_calendar_oauth_boundary import (
    CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ,
)
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_calendar_token_vault import OfflineCalendarCredentialVault
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarVerificationError,
)
from empire_os.inbound_google_calendar_enrollment import enroll_google_calendar_offline
from empire_os.inbound_google_calendar_credentials import VaultBackedGoogleCalendarResolver
from empire_os.inbound_google_oauth_exchange import refresh_google_calendar_access

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "business-owned-calendar@example.org"
CLIENT = "test-google-client-id.apps.googleusercontent.com"
SCOPE = frozenset({EVENTS_READ, CALENDAR_FREEBUSY, CALENDAR_LIST_READ})


def ticket(tenant="a"):
    return OneTimeGoogleCodeTicket(
        tenant_id=tenant, admin_subject="authorized-admin-1",
        client_id=CLIENT, redirect_uri="https://empire.example.com/calendar/oauth/callback",
        authorization_code="once-only-code", code_verifier="pkce-verifier",
    )


def binding(tenant="a"):
    return ApprovedCalendarBinding(
        tenant_id=tenant, calendar_id=CAL,
        provider_account_ref="google-calendar-authorised-owner",
        owner_approved=True, account_access_verified=True,
    )


class Tokens:
    def __init__(self, scopes=None):
        self.scopes = scopes if scopes is not None else " ".join(sorted(SCOPE))
        self.calls = []

    def post_form(self, fields):
        self.calls.append(fields.copy())
        return {
            "token_type": "Bearer", "access_token": "client-approved-access",
            "refresh_token": "client-approved-refresh",
            "expires_in": 1800, "scope": self.scopes,
        }


class GoogleCalendar:
    def __init__(self, *, calendar=CAL, role="owner"):
        self.calendar = calendar
        self.role = role
        self.calls = []

    def fetch(self, *, method, path, token, body=None):
        self.calls.append((method, path, token))
        assert method == "GET"
        assert path == "/calendar/v3/users/me/calendarList/" + quote(CAL, safe="")
        return {"id": self.calendar, "accessRole": self.role}


def enroll(tmp_path, *, tenant="a", scopes=None, calendar=None, role="owner"):
    with OfflineCalendarCredentialVault(
        tmp_path / "vault.db", active_key=Fernet.generate_key()
    ) as vault, OfflineCalendarRegistry(tmp_path / "registry.db") as registry:
        token_source = Tokens(scopes)
        google = GoogleCalendar(calendar=calendar or CAL, role=role)
        result = enroll_google_calendar_offline(
            ticket=ticket(tenant), binding=binding(),
            expected_client_id=CLIENT, client_secret="super-secret-client-credential",
            owner_approval_evidence_ref="customer-approved-owner-evidence",
            endpoint=token_source, google_read_transport=google,
            vault=vault, registry=registry, now=NOW,
        )
        return result, token_source, google


def test_successfully_enrolls_owned_calendar_to_separate_encrypted_vault(tmp_path):
    result, google_tokens, readback = enroll(tmp_path)
    assert result.calendar_binding_created
    assert result.credential_vault_write
    assert result.status == "onboarded_to_offline_secret_vault_only"
    assert not result.live_bookings_created
    assert len(google_tokens.calls) == 1
    assert len(readback.calls) == 1

    # No bearer, refresh or client-secret material in the calendar registry.
    contents = (tmp_path / "registry.db").read_bytes()
    assert b"client-approved-access" not in contents
    assert b"client-approved-refresh" not in contents
    assert b"super-secret-client-credential" not in contents

    # Separate vault retains encrypted credential only.
    assert b"client-approved-access" not in (tmp_path / "vault.db").read_bytes()


def test_tenant_mismatch_denied_before_google_exchange(tmp_path):
    with OfflineCalendarCredentialVault(
        tmp_path / "vault.db", active_key=Fernet.generate_key()
    ) as vault, OfflineCalendarRegistry(tmp_path / "registry.db") as registry:
        token_source = Tokens()
        with pytest.raises(CalendarVerificationError, match="tenant_mismatch"):
            enroll_google_calendar_offline(
                ticket=ticket("unrelated"), binding=binding(),
                expected_client_id=CLIENT, client_secret="secret",
                owner_approval_evidence_ref="customer-proof",
                endpoint=token_source, google_read_transport=GoogleCalendar(),
                vault=vault, registry=registry, now=NOW,
            )
        assert not token_source.calls


@pytest.mark.parametrize("bad_scopes,role,calendar", [
    ("https://www.googleapis.com/auth/calendar", "owner", CAL),
    (" ".join(sorted({EVENTS_READ, CALENDAR_FREEBUSY})), "owner", CAL),
    (" ".join(sorted(SCOPE)), "reader", CAL),
    (" ".join(sorted(SCOPE)), "owner", "another-calendar@example.org"),
])
def test_denied_grant_never_creates_calendar_connection(tmp_path, bad_scopes, role, calendar):
    with OfflineCalendarCredentialVault(
        tmp_path / "vault.db", active_key=Fernet.generate_key()
    ) as vault, OfflineCalendarRegistry(tmp_path / "registry.db") as registry:
        with pytest.raises(CalendarVerificationError):
            enroll_google_calendar_offline(
                ticket=ticket(), binding=binding(),
                expected_client_id=CLIENT, client_secret="secret",
                owner_approval_evidence_ref="customer-proof",
                endpoint=Tokens(bad_scopes),
                google_read_transport=GoogleCalendar(calendar=calendar, role=role),
                vault=vault, registry=registry, now=NOW,
            )
        assert registry.get_binding(CAL) is None
        assert vault.status(tenant_id="a")["active_local_credentials"] == 0


def test_registry_provisioning_failure_restricts_credential_locally(tmp_path):
    from unittest.mock import patch
    with OfflineCalendarCredentialVault(
        tmp_path / "vault.db", active_key=Fernet.generate_key()
    ) as vault, OfflineCalendarRegistry(tmp_path / "registry.db") as registry:
        with patch.object(
            registry, "register_binding_offline",
            side_effect=ValueError("injected calendar registry failure"),
        ):
            with pytest.raises(ValueError, match="injected"):
                enroll_google_calendar_offline(
                    ticket=ticket(), binding=binding(), expected_client_id=CLIENT,
                    client_secret="secret",
                    owner_approval_evidence_ref="customer-proof",
                    endpoint=Tokens(), google_read_transport=GoogleCalendar(),
                    vault=vault, registry=registry, now=NOW,
                )
        assert vault.status(tenant_id="a")["active_local_credentials"] == 0
        assert vault.status(tenant_id="a")["revoked_local_credentials"] == 1
