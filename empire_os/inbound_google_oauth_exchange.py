"""Strict, opt-in Google OAuth token exchange/refresh transport.

No use of an Empire/Gmail token, no requests on import, no HTTP endpoint.
Token issuance requires an independently validated one-time PKCE code ticket.
OAuth responses are parsed only from Google's fixed HTTPS token endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from empire_os.inbound_calendar_oauth_boundary import (
    ALLOWED_GOOGLE_READ_SCOPES,
    CALENDAR_FREEBUSY, CALENDAR_LIST_READ, EVENTS_READ,
)
from empire_os.inbound_calendar_oauth_onboarding import OneTimeGoogleCodeTicket
from empire_os.inbound_google_calendar_adapter import CalendarVerificationError


class OAuthTokenEndpoint(Protocol):
    def post_form(self, fields: dict[str, str]) -> dict: ...


class _DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class GoogleOAuthTokenHTTP:
    """One fixed endpoint; no user-supplied URLs, redirects or error disclosure."""

    def __init__(self, *, timeout_seconds: float = 8):
        if not 1 <= timeout_seconds <= 15:
            raise ValueError("invalid_oauth_request_timeout")
        self.timeout_seconds = timeout_seconds
        self.opener = build_opener(_DenyRedirect)

    def post_form(self, fields: dict[str, str]) -> dict:
        if (not isinstance(fields, dict)
            or fields.get("grant_type") not in {"authorization_code", "refresh_token"}
            or any(not isinstance(x, str) or not x.strip() for x in fields.values())):
            raise CalendarVerificationError("invalid_oauth_token_request")
        request = Request(
            "https://oauth2.googleapis.com/token",
            data=urlencode(fields).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Accept": "application/json"},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise CalendarVerificationError("google_token_exchange_not_confirmed")
                payload = response.read(16385)
                if len(payload) > 16384:
                    raise CalendarVerificationError("google_token_reply_too_large")
                parsed = json.loads(payload)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
            raise CalendarVerificationError("google_oauth_token_transport_failed") from exc
        if not isinstance(parsed, dict):
            raise CalendarVerificationError("invalid_google_oauth_reply")
        return parsed


@dataclass(frozen=True)
class GoogleTokenBundle:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    granted_scopes: frozenset[str] = frozenset()
    issued_at: datetime = field(default=None)
    expires_at: datetime = field(default=None)
    source: str = "google_oauth_token_endpoint"

    def __post_init__(self) -> None:
        if not isinstance(self.access_token, str) or not self.access_token.strip() or len(self.access_token) > 8192:
            raise CalendarVerificationError("invalid_google_access_token")
        if self.refresh_token is not None and (
            not isinstance(self.refresh_token, str)
            or not self.refresh_token.strip()
            or len(self.refresh_token) > 8192
        ):
            raise CalendarVerificationError("invalid_google_refresh_token")
        if (not self.granted_scopes or not self.granted_scopes <= ALLOWED_GOOGLE_READ_SCOPES
            or not {EVENTS_READ, CALENDAR_FREEBUSY, CALENDAR_LIST_READ} <= self.granted_scopes):
            raise CalendarVerificationError("google_granted_scopes_not_minimal_readonly")
        if (not isinstance(self.issued_at, datetime)
            or self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None
            or not isinstance(self.expires_at, datetime)
            or self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None
            or not self.issued_at < self.expires_at
            or self.expires_at - self.issued_at > timedelta(hours=1)):
            raise CalendarVerificationError("invalid_google_access_token_expiry")


def _bundle(data: dict, *, now: datetime, refresh_fallback: str | None = None,
            prior_scopes: frozenset[str] | None = None) -> GoogleTokenBundle:
    if not isinstance(data, dict) or data.get("token_type") != "Bearer":
        raise CalendarVerificationError("google_oauth_bearer_response_required")
    ttl = data.get("expires_in")
    if isinstance(ttl, bool) or not isinstance(ttl, int) or not 60 <= ttl <= 3600:
        raise CalendarVerificationError("google_token_expiry_invalid")
    raw = data.get("scope")
    if isinstance(raw, str) and raw.strip():
        scopes = frozenset(raw.split())
    elif prior_scopes is not None:
        # Google's refresh response can omit scope. Only inherit scopes from
        # the *same* previously server-verified grant; never add permissions.
        scopes = prior_scopes
    else:
        raise CalendarVerificationError("google_granted_scope_response_required")
    if prior_scopes is not None and not scopes <= prior_scopes:
        raise CalendarVerificationError("google_refresh_scope_expansion_denied")
    refresh = data.get("refresh_token", refresh_fallback)
    return GoogleTokenBundle(
        access_token=data.get("access_token"),
        refresh_token=refresh,
        granted_scopes=scopes, issued_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )


def exchange_google_pkce_code(
    ticket: OneTimeGoogleCodeTicket, *,
    expected_client_id: str,
    client_secret: str,
    endpoint: OAuthTokenEndpoint,
    now: datetime,
) -> GoogleTokenBundle:
    if (not isinstance(ticket, OneTimeGoogleCodeTicket)
        or not isinstance(expected_client_id, str)
        or ticket.client_id != expected_client_id
        or not isinstance(client_secret, str) or not client_secret.strip()):
        raise CalendarVerificationError("google_oauth_client_not_authorized")
    result = endpoint.post_form({
        "grant_type": "authorization_code",
        "client_id": ticket.client_id,
        "client_secret": client_secret,
        "code": ticket.authorization_code,
        "redirect_uri": ticket.redirect_uri,
        "code_verifier": ticket.code_verifier,
    })
    bundle = _bundle(result, now=now)
    if bundle.refresh_token is None:
        raise CalendarVerificationError("google_offline_refresh_grant_required")
    return bundle


def refresh_google_calendar_access(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    prior_scopes: frozenset[str],
    endpoint: OAuthTokenEndpoint,
    now: datetime,
) -> GoogleTokenBundle:
    for candidate in (client_id, client_secret, refresh_token):
        if not isinstance(candidate, str) or not candidate.strip():
            raise CalendarVerificationError("google_oauth_refresh_not_configured")
    if not isinstance(prior_scopes, frozenset):
        raise CalendarVerificationError("google_oauth_prior_scope_contract_required")
    result = endpoint.post_form({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })
    return _bundle(result, now=now, refresh_fallback=refresh_token,
                   prior_scopes=prior_scopes)
