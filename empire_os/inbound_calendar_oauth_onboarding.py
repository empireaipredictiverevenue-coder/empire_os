"""Offline, short-lived Google Calendar OAuth onboarding state + PKCE.

This is only the consent-request/callback STATE contract, not a web endpoint,
Google token exchange, vault, customer identity provider or live account link.
OAuth credentials NEVER enter this database. Server-only Fernet key is required.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import base64
from hashlib import sha256
import secrets
import sqlite3
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from cryptography.fernet import Fernet, InvalidToken

from empire_os.inbound_calendar_oauth_boundary import (
    EVENTS_READ, CALENDAR_FREEBUSY,
)


class OAuthOnboardingDenied(ValueError):
    pass


READ_SCOPES = (EVENTS_READ, CALENDAR_FREEBUSY)


@dataclass(frozen=True)
class GoogleConsentRequest:
    tenant_id: str
    authorization_url: str
    expires_at: str
    scopes: tuple[str, ...] = READ_SCOPES
    live_provider_access_granted: bool = False


@dataclass(frozen=True)
class OneTimeGoogleCodeTicket:
    tenant_id: str
    admin_subject: str
    client_id: str
    redirect_uri: str
    authorization_code: str = field(repr=False)
    code_verifier: str = field(repr=False)
    live_provider_access_granted: bool = False


def _as_of(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OAuthOnboardingDenied("oauth_timestamp_timezone_required")


def _https_redirect(value: str) -> None:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or
        parsed.username or parsed.password or parsed.fragment or
        parsed.query or len(value) > 500):
        raise OAuthOnboardingDenied("registered_https_callback_required")


class OfflineGoogleConsentStateStore:
    def __init__(self, path: str | Path, *, encryption_key: bytes):
        self.path = Path(path)
        if (self.path != Path(":memory:") and (
            not self.path.parent.is_dir() or self.path.is_symlink()
        )):
            raise OAuthOnboardingDenied("private_oauth_state_store_required")
        try:
            self.fernet = Fernet(encryption_key)
        except (ValueError, TypeError) as exc:
            raise OAuthOnboardingDenied("valid_server_side_fernet_key_required") from exc
        self.db = sqlite3.connect(str(self.path), timeout=3)
        self.db.execute("PRAGMA busy_timeout=3000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS oauth_pending (
                state_sha256 TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                admin_subject TEXT NOT NULL,
                client_id TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                encrypted_verifier BLOB NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0
            );
        """)

    def __enter__(self) -> "OfflineGoogleConsentStateStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    def begin(
        self, *, tenant_id: str, admin_subject: str,
        client_id: str, redirect_uri: str,
        now: datetime,
    ) -> GoogleConsentRequest:
        _as_of(now)
        for field_name, value in (
            ("tenant_id", tenant_id), ("admin_subject", admin_subject),
            ("client_id", client_id),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise OAuthOnboardingDenied(f"oauth_{field_name}_required")
        _https_redirect(redirect_uri)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        expire = now + timedelta(minutes=10)
        with self.db:
            self.db.execute(
                "INSERT INTO oauth_pending "
                "(state_sha256,tenant_id,admin_subject,client_id,redirect_uri,"
                "encrypted_verifier,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?)",
                (sha256(state.encode()).hexdigest(), tenant_id, admin_subject,
                 client_id, redirect_uri, self.fernet.encrypt(verifier.encode()),
                 now.isoformat(), expire.isoformat()),
            )
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(READ_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "false",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return GoogleConsentRequest(
            tenant_id=tenant_id,
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth?" + params,
            expires_at=expire.isoformat(),
        )

    def consume(
        self, *, tenant_id: str, admin_subject: str,
        state: str, authorization_code: str, now: datetime,
    ) -> OneTimeGoogleCodeTicket:
        """One-time callback state validation; NO token exchange or persistence."""
        _as_of(now)
        if (not isinstance(state, str) or len(state) < 40 or len(state) > 256
            or not isinstance(authorization_code, str)
            or not authorization_code.strip() or len(authorization_code) > 8192):
            raise OAuthOnboardingDenied("invalid_oauth_callback")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT tenant_id,admin_subject,client_id,redirect_uri,"
                "encrypted_verifier,created_at,expires_at,consumed "
                "FROM oauth_pending WHERE state_sha256=?",
                (sha256(state.encode()).hexdigest(),),
            ).fetchone()
            if (row is None or row[0] != tenant_id or row[1] != admin_subject
                or row[7] != 0):
                raise OAuthOnboardingDenied("oauth_state_missing_replayed_or_mismatched")
            created = datetime.fromisoformat(row[5])
            expires = datetime.fromisoformat(row[6])
            if not created <= now < expires:
                raise OAuthOnboardingDenied("oauth_state_expired_or_future")
            try:
                verifier = self.fernet.decrypt(row[4]).decode("ascii")
            except (InvalidToken, UnicodeDecodeError) as exc:
                raise OAuthOnboardingDenied("oauth_pkce_integrity_failure") from exc
            self.db.execute(
                "UPDATE oauth_pending SET consumed=1, encrypted_verifier=x'' "
                "WHERE state_sha256=? AND consumed=0",
                (sha256(state.encode()).hexdigest(),),
            )
            self.db.commit()
            return OneTimeGoogleCodeTicket(
                tenant_id=tenant_id, admin_subject=admin_subject,
                client_id=row[2], redirect_uri=row[3],
                authorization_code=authorization_code, code_verifier=verifier,
            )
        except Exception:
            self.db.rollback()
            raise
