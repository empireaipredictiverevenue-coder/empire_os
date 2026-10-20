"""Optional calendar OAuth HTTP routes; dark unless owner session authority exists.

No issuer, login, Google tokens, public ingress or worker created here.
Start uses dedicated calendar JWT AND a separate verified browser session.
Callback checks the same session and SameSite=Lax Secure nonce before an
injected privileged completion adapter can exchange the OAuth code.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from empire_os.inbound_calendar_connection_identity import (
    CalendarConnectionPrincipal, CalendarIdentityDenied,
)
from empire_os.inbound_calendar_oauth_onboarding import (
    OfflineGoogleConsentStateStore, OAuthOnboardingDenied,
    OneTimeGoogleCodeTicket,
)
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry

PREFIX = "/v1/inbound-recovery/calendar-connect"
COOKIE = "__Host-empire-inbound-oauth-session"


class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calendar_id: str = Field(min_length=1, max_length=240)
    customer_approved_read_only: bool


def _check(principal: CalendarConnectionPrincipal) -> CalendarConnectionPrincipal:
    if (not isinstance(principal, CalendarConnectionPrincipal)
        or not principal.tenant_id or not principal.subject
        or principal.role not in ("owner", "admin")):
        raise CalendarIdentityDenied("canonical_owner_required")
    return principal


def create_calendar_connection_router(
    *, enabled: bool = False,
    verify_bearer: Callable[[Request], CalendarConnectionPrincipal] | None = None,
    verify_browser_session: Callable[[Request], CalendarConnectionPrincipal] | None = None,
    complete_callback: Callable[[OneTimeGoogleCodeTicket, CalendarConnectionPrincipal], bool] | None = None,
    state_db: Path | None = None,
    state_encryption_key: bytes | None = None,
    google_client_id: str = "",
    redirect_uri: str = "",
    application_origin: str = "",
    calendar_db: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    """Fail at configuration rather than accepting any untrusted HTTP claims."""
    if enabled:
        if (not callable(verify_bearer) or not callable(verify_browser_session)
            or not callable(complete_callback)
            or not isinstance(state_db, Path) or not isinstance(calendar_db, Path)
            or not isinstance(state_encryption_key, bytes)
            or not google_client_id.strip()
            or not redirect_uri.startswith("https://")
            or not application_origin.startswith("https://")
            or urlsplit(redirect_uri).scheme != "https"
            or urlsplit(application_origin).scheme != "https"
            or urlsplit(application_origin).path not in ("", "/")
            or urlsplit(application_origin).query or urlsplit(application_origin).fragment
            or redirect_uri != application_origin + PREFIX + "/callback"):
            raise ValueError("calendar_oauth_activation_requires_verified_backend_config")
    current_time = clock or (lambda: datetime.now(timezone.utc))
    router = APIRouter(prefix=PREFIX, tags=["inbound-calendar-connection"])

    def _active() -> None:
        if not enabled:
            raise HTTPException(status_code=404, detail="calendar_connection_disabled")

    def _principal(request: Request, *, bearer: bool) -> CalendarConnectionPrincipal:
        try:
            callback = verify_bearer if bearer else verify_browser_session
            return _check(callback(request))
        except Exception as exc:
            raise HTTPException(status_code=401, detail="calendar_owner_identity_required") from exc

    def _state() -> OfflineGoogleConsentStateStore:
        return OfflineGoogleConsentStateStore(
            state_db, encryption_key=state_encryption_key,
        )

    @router.post("/start")
    def start(body: ConnectRequest, request: Request, response: Response):
        _active()
        if request.headers.get("origin") != application_origin:
            raise HTTPException(status_code=403, detail="calendar_origin_mismatch")
        principal = _principal(request, bearer=True)
        session = _principal(request, bearer=False)
        if session.tenant_id != principal.tenant_id or session.subject != principal.subject:
            raise HTTPException(status_code=403, detail="calendar_browser_identity_mismatch")
        if body.customer_approved_read_only is not True:
            raise HTTPException(status_code=403, detail="customer_calendar_consent_required")
        # Selected calendar is merely an intended ID; provider Google
        # calendarList.get validates that exact ID after consent.
        nonce = secrets.token_urlsafe(32)
        try:
            with _state() as states:
                consent = states.begin(
                    tenant_id=principal.tenant_id,
                    admin_subject=principal.subject,
                    client_id=google_client_id,
                    redirect_uri=redirect_uri,
                    selected_calendar_id=body.calendar_id,
                    browser_nonce=nonce, now=current_time(),
                )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="calendar_connection_storage_unavailable") from exc
        response.set_cookie(
            COOKIE, nonce, max_age=600, secure=True, httponly=True,
            samesite="lax", path="/",
        )
        return {
            "authorization_url": consent.authorization_url,
            "expires_at": consent.expires_at,
            "connection_created": False,
            "calendar_write_authorized": False,
        }

    @router.get("/callback")
    def callback(
        request: Request, response: Response,
        state: str = "", code: str = "", error: str | None = None,
    ):
        _active()
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        if error is not None or not state or not code:
            raise HTTPException(status_code=400, detail="calendar_consent_not_completed")
        principal = _principal(request, bearer=False)
        nonce = request.cookies.get(COOKIE)
        if not nonce:
            raise HTTPException(status_code=403, detail="calendar_browser_session_required")
        try:
            with _state() as states:
                ticket = states.consume(
                    tenant_id=principal.tenant_id,
                    admin_subject=principal.subject,
                    state=state, authorization_code=code,
                    browser_nonce=nonce, now=current_time(),
                )
            if not ticket.selected_calendar_id:
                raise ValueError("calendar_selection_not_bound")
            # Must be implemented by a privileged server adapter using the
            # matching selected_calendar_id, canonical membership and vault.
            if complete_callback(ticket, principal) is not True:
                raise ValueError("connection_not_independently_verified")
        except Exception as exc:
            raise HTTPException(status_code=403, detail="calendar_connection_verification_failed") from exc
        return {
            "connected": True, "tenant_id": principal.tenant_id,
            "calendar_write_authorized": False,
            "booking_creation_authorized": False,
        }

    @router.get("/status")
    def status(request: Request):
        _active()
        principal = _principal(request, bearer=True)
        try:
            with OfflineCalendarRegistry(calendar_db, read_only=True) as registry:
                data = registry.tenant_summary(principal.tenant_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="calendar_status_unavailable") from exc
        return {**data, "identity": "canonical_owner_member", "access_tokens_returned": False}

    return router
