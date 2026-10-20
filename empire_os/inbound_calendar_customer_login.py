"""Opt-in Calendar owner login using EmpireOS's existing first-party CRM accounts.

Never mounted in the default dark service. No customer sign-up, no self-service
membership grants, no Google access. Uses the canonical invited CRM account
login and a fresh account-bound EmpireDB membership lookup.
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from empire_os.inbound_calendar_connection_identity import (
    AUDIENCE, BROWSER_AUDIENCE, BROWSER_COOKIE, BROWSER_SCOPE, ISSUER,
    SCOPE, SignedCalendarConnectionVerifier, CalendarConnectionPrincipal,
    CalendarIdentityDenied, resolve_calendar_connection_principal,
)
from empire_os.revenue_crm_first_party_login import PostgresCrmPasswordLogin
from empire_os.saas_scale import TenantMembership

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class CalendarOwnerLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    tenant_id: str = Field(min_length=36, max_length=36)
    customer_approved_read_only: bool


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign(
    private_key: Ed25519PrivateKey, key_id: str, *,
    audience: str, scope: str, subject: str, tenant: str,
    issued: int, duration: int,
) -> str:
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id}
    claims = {
        "iss": ISSUER, "aud": audience, "sub": subject,
        "tenant_id": tenant, "scope": scope, "iat": issued,
        "nbf": issued, "exp": issued + duration,
        "jti": secrets.token_urlsafe(24),
    }
    text = (
        _b64(json.dumps(header, separators=(",", ":")).encode()) + "." +
        _b64(json.dumps(claims, separators=(",", ":")).encode())
    )
    return text + "." + _b64(private_key.sign(text.encode("ascii")))


def create_calendar_owner_login_router(
    *, password_login: PostgresCrmPasswordLogin,
    load_membership: Callable[[str, str], TenantMembership | None],
    signing_key: Ed25519PrivateKey,
    key_id: str,
    application_origin: str,
    now: Callable[[], int] | None = None,
) -> APIRouter:
    """Privileged opt-in login route. Never call with a client-selected key."""
    parsed = urlsplit(application_origin)
    if (not isinstance(password_login, PostgresCrmPasswordLogin)
        or not callable(load_membership)
        or not isinstance(signing_key, Ed25519PrivateKey)
        or not isinstance(key_id, str) or not _ID.fullmatch(key_id)
        or parsed.scheme != "https" or not parsed.hostname
        or parsed.path not in ("", "/") or parsed.query or parsed.fragment
        or parsed.username or parsed.password):
        raise ValueError("approved_first_party_calendar_login_config_required")
    clock = now or (lambda: int(time.time()))
    router = APIRouter(prefix="/v1/inbound-recovery/calendar-auth",
                       tags=["inbound-calendar-owner-auth"])

    @router.post("/login")
    def login(body: CalendarOwnerLoginRequest, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.headers.get("origin") != application_origin:
            raise HTTPException(status_code=403, detail="calendar_login_origin_denied")
        if body.customer_approved_read_only is not True:
            raise HTTPException(status_code=403, detail="calendar_owner_consent_required")
        try:
            tenant = str(UUID(body.tenant_id))
        except (TypeError, ValueError, AttributeError):
            tenant = ""
        if tenant != body.tenant_id:
            raise HTTPException(status_code=401, detail="calendar_owner_login_denied")

        # Same DB account lockout and password verification as native CRM.
        # The supplied membership callback MUST be constructed with
        # build_account_bound_membership_lookup from the existing canonical
        # CRM login + EmpireDbCrmMembershipReader (041).
        subject = password_login.authenticate(body.email, body.password)
        try:
            membership = load_membership(subject, tenant) if subject else None
            permitted = (
                isinstance(membership, TenantMembership)
                and membership.user_id == subject
                and membership.tenant_id == tenant
                and membership.status == "active"
                and membership.role in {"owner", "admin"}
                and membership.can("admin")
            )
        except Exception:
            permitted = False
        if not permitted:
            raise HTTPException(status_code=401, detail="calendar_owner_login_denied")
        issued = int(clock())
        bearer = _sign(
            signing_key, key_id, audience=AUDIENCE, scope=SCOPE,
            subject=subject, tenant=tenant, issued=issued, duration=300,
        )
        session = _sign(
            signing_key, key_id, audience=BROWSER_AUDIENCE, scope=BROWSER_SCOPE,
            subject=subject, tenant=tenant, issued=issued, duration=600,
        )
        response.set_cookie(
            BROWSER_COOKIE, session, max_age=600, secure=True,
            httponly=True, samesite="lax", path="/",
        )
        return {
            "access_token": bearer,
            "token_type": "Bearer",
            "expires_in": 300,
            "scope": SCOPE,
            "calendar_connected": False,
            "google_access_granted": False,
        }

    return router


def build_calendar_owner_resolvers(
    trusted_public_keys: Mapping[str, bytes | Ed25519PublicKey],
    *, load_membership: Callable[[str, str], TenantMembership | None],
    now: Callable[[], int] | None = None,
) -> tuple[
    Callable[[Request], CalendarConnectionPrincipal],
    Callable[[Request], CalendarConnectionPrincipal],
]:
    """Separate bearer and HttpOnly browser-cookie audiences, same live DB."""
    bearer = SignedCalendarConnectionVerifier(
        trusted_public_keys, load_membership=load_membership,
        now=now, credential_kind="bearer",
    )
    browser = SignedCalendarConnectionVerifier(
        trusted_public_keys, load_membership=load_membership,
        now=now, credential_kind="browser_session",
    )

    def verify_bearer(request: Request) -> CalendarConnectionPrincipal:
        return resolve_calendar_connection_principal(request, verifier=bearer)

    def verify_browser_session(request: Request) -> CalendarConnectionPrincipal:
        values = request.cookies.get(BROWSER_COOKIE)
        if not isinstance(values, str) or not values:
            raise CalendarIdentityDenied("calendar_browser_identity_required")
        return browser.authenticate(values)

    return verify_bearer, verify_browser_session


@dataclass(frozen=True)
class CalendarOwnerIdentityBundle:
    """Ready for a separately approved private app, never auto-mounted."""
    login_router: APIRouter
    verify_bearer: Callable[[Request], CalendarConnectionPrincipal]
    verify_browser_session: Callable[[Request], CalendarConnectionPrincipal]
    live_account_and_membership_required: bool = True
    public_routes_enabled: bool = False


def build_calendar_identity_from_existing_crm(
    *, password_login: PostgresCrmPasswordLogin,
    canonical_membership_lookup: Callable[[str, str], TenantMembership | None],
    signing_key: Ed25519PrivateKey,
    key_id: str, application_origin: str,
    now: Callable[[], int] | None = None,
) -> CalendarOwnerIdentityBundle:
    """Reuse CRM's verified account+membership seam instead of a new user DB.

    The dedicated CRM account and membership logins must already be provisioned
    through the existing first-party CRM pilot. No attempt to create those
    roles, copy private keys or modify live routes occurs here.
    """
    from empire_os.revenue_crm_first_party_login import (
        build_account_bound_membership_lookup,
    )
    bound = build_account_bound_membership_lookup(
        password_login, canonical_membership_lookup,
    )
    login_router = create_calendar_owner_login_router(
        password_login=password_login, load_membership=bound,
        signing_key=signing_key, key_id=key_id,
        application_origin=application_origin, now=now,
    )
    bearer, browser = build_calendar_owner_resolvers(
        {key_id: signing_key.public_key()}, load_membership=bound,
        now=now,
    )
    return CalendarOwnerIdentityBundle(
        login_router=login_router,
        verify_bearer=bearer,
        verify_browser_session=browser,
    )
