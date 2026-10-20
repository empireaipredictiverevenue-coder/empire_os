"""Read-only Google OAuth consent handshake with encrypted ephemeral PKCE."""
from datetime import datetime, timedelta, timezone
import base64
from hashlib import sha256
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
import pytest

from empire_os.inbound_calendar_oauth_onboarding import (
    OAuthOnboardingDenied, OfflineGoogleConsentStateStore,
)
from empire_os.inbound_calendar_oauth_boundary import EVENTS_READ, CALENDAR_FREEBUSY

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
REDIRECT = "https://empire.example.org/oauth/google/calendar/callback"


def begin(store, **overrides):
    kwargs = {
        "tenant_id": "business-a", "admin_subject": "approved-owner-1",
        "client_id": "google-client-id-placeholder.apps.googleusercontent.com",
        "redirect_uri": REDIRECT, "now": NOW,
    }
    kwargs.update(overrides)
    request = store.begin(**kwargs)
    params = parse_qs(urlsplit(request.authorization_url).query)
    return request, params


def claim(store, params, **overrides):
    options = {
        "tenant_id": "business-a", "admin_subject": "approved-owner-1",
        "state": params["state"][0],
        "authorization_code": "test-only-provider-auth-code",
        "now": NOW + timedelta(minutes=1),
    }
    options.update(overrides)
    return store.consume(**options)


def test_one_time_consent_has_exact_readonly_scopes_pkce_and_state(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "oauth-state.db"
    with OfflineGoogleConsentStateStore(path, encryption_key=key) as store:
        start, params = begin(store)
        assert start.live_provider_access_granted is False
        assert urlsplit(start.authorization_url).hostname == "accounts.google.com"
        assert set(params["scope"][0].split()) == {EVENTS_READ, CALENDAR_FREEBUSY}
        assert params["response_type"] == ["code"]
        assert params["code_challenge_method"] == ["S256"]
        assert params["include_granted_scopes"] == ["false"]
        assert params["access_type"] == ["offline"]
        assert params["redirect_uri"] == [REDIRECT]
        ticket = claim(store, params)
        expected = base64.urlsafe_b64encode(
            sha256(ticket.code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        assert params["code_challenge"] == [expected]
        assert ticket.tenant_id == "business-a"
        assert "test-only-provider-auth-code" not in repr(ticket)
        assert ticket.live_provider_access_granted is False
        with pytest.raises(OAuthOnboardingDenied, match="replayed"):
            claim(store, params)
    raw = path.read_bytes()
    assert ticket.code_verifier.encode() not in raw
    assert b"test-only-provider-auth-code" not in raw
    assert b"google-client-id-placeholder" in raw  # Non-secret client ID.


def test_cross_tenant_or_wrong_admin_cannot_consume_state(tmp_path):
    with OfflineGoogleConsentStateStore(
        tmp_path / "oauth.db", encryption_key=Fernet.generate_key()
    ) as store:
        _, params = begin(store)
        with pytest.raises(OAuthOnboardingDenied, match="mismatched"):
            claim(store, params, tenant_id="business-b")
        with pytest.raises(OAuthOnboardingDenied, match="mismatched"):
            claim(store, params, admin_subject="other-user")
        assert claim(store, params).admin_subject == "approved-owner-1"


def test_expiry_and_future_time_cannot_exchange_callback(tmp_path):
    with OfflineGoogleConsentStateStore(
        tmp_path / "oauth.db", encryption_key=Fernet.generate_key()
    ) as store:
        _, params = begin(store)
        with pytest.raises(OAuthOnboardingDenied, match="expired_or_future"):
            claim(store, params, now=NOW + timedelta(minutes=11))
        with pytest.raises(OAuthOnboardingDenied, match="expired_or_future"):
            claim(store, params, now=NOW - timedelta(minutes=1))


def test_invalid_state_and_code_denied_without_consume(tmp_path):
    with OfflineGoogleConsentStateStore(
        tmp_path / "oauth.db", encryption_key=Fernet.generate_key()
    ) as store:
        _, params = begin(store)
        with pytest.raises(OAuthOnboardingDenied):
            claim(store, params, state="unknown-random-string-0000000000000000000000")
        with pytest.raises(OAuthOnboardingDenied):
            claim(store, params, authorization_code="")
        assert claim(store, params).authorization_code == "test-only-provider-auth-code"


@pytest.mark.parametrize("url", [
    "http://attacker.example/callback",
    "https://user:password@host.example/callback",
    "https://host.example/callback?tenant=other",
    "https://host.example/callback#fragment",
    "javascript:alert(1)",
    "https:///invalid-path",
])
def test_callback_registration_requires_exact_secure_https_form(tmp_path, url):
    with OfflineGoogleConsentStateStore(
        tmp_path / "oauth.db", encryption_key=Fernet.generate_key()
    ) as store:
        with pytest.raises(OAuthOnboardingDenied, match="registered_https"):
            begin(store, redirect_uri=url)


def test_plaintext_encryption_key_or_invalid_identity_denied(tmp_path):
    with pytest.raises(OAuthOnboardingDenied, match="fernet_key"):
        OfflineGoogleConsentStateStore(tmp_path / "oauth.db", encryption_key=b"plaintext")
    with OfflineGoogleConsentStateStore(
        tmp_path / "other.db", encryption_key=Fernet.generate_key()
    ) as store:
        with pytest.raises(OAuthOnboardingDenied, match="admin_subject_required"):
            begin(store, admin_subject="  ")


def test_consumption_removes_encrypted_verifier_from_db(tmp_path):
    key = Fernet.generate_key()
    with OfflineGoogleConsentStateStore(
        tmp_path / "oauth.db", encryption_key=key
    ) as store:
        _, params = begin(store)
        assert store.db.execute(
            "SELECT length(encrypted_verifier) FROM oauth_pending"
        ).fetchone()[0] > 50
        claim(store, params)
        assert store.db.execute(
            "SELECT length(encrypted_verifier) FROM oauth_pending"
        ).fetchone()[0] == 0
