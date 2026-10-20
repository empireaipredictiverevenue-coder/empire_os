"""Customer calendar connection identity, derived from existing EmpireOS authority.

Consumes Ed25519 tokens minted ONLY by a separately authorised EmpireOS issuer,
with a calendar-specific audience. It reuses the canonical CRM/EmpireDB
TenantMembership reader; NO tokens or accounts are minted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from uuid import UUID
import re
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Request

from empire_os.revenue_crm_signed_auth import _decode, _object
from empire_os.saas_scale import TenantMembership

AUDIENCE = "empire-inbound-recovery-calendar"
ISSUER = "empire-os"
SCOPE = "recovery:calendar:connect"
ADMIN_ROLES = frozenset({"owner", "admin"})
KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SUBJECT = re.compile(r"^[A-Za-z0-9:@._/-]{1,128}$")
JTI = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class CalendarIdentityDenied(ValueError):
    """Denied connection management identity; no diagnostic credentials."""


@dataclass(frozen=True)
class CalendarConnectionPrincipal:
    tenant_id: str
    subject: str
    token_id: str
    role: str


class SignedCalendarConnectionVerifier:
    """Pinned Ed25519 key + exact audience + fresh active owner/admin membership."""

    def __init__(
        self,
        public_keys: Mapping[str, bytes | Ed25519PublicKey],
        *, load_membership: Callable[[str, str], TenantMembership | None],
        now: Callable[[], int] | None = None,
    ) -> None:
        if not public_keys or not callable(load_membership):
            raise ValueError("canonical_identity_and_membership_required")
        keys: dict[str, Ed25519PublicKey] = {}
        for kid, value in public_keys.items():
            if not isinstance(kid, str) or not KEY_ID.fullmatch(kid):
                raise ValueError("invalid_calendar_identity_key_id")
            if isinstance(value, Ed25519PublicKey):
                keys[kid] = value
            elif isinstance(value, bytes) and len(value) == 32:
                keys[kid] = Ed25519PublicKey.from_public_bytes(value)
            else:
                raise ValueError("invalid_calendar_identity_key")
        self.keys = keys
        self.membership = load_membership
        self.now = now or (lambda: int(time.time()))

    def authenticate(self, bearer: str) -> CalendarConnectionPrincipal:
        try:
            if not isinstance(bearer, str) or not 1 <= len(bearer) <= 4096:
                raise ValueError("invalid_calendar_bearer")
            parts = bearer.split(".")
            if len(parts) != 3:
                raise ValueError("invalid_calendar_bearer_shape")
            header = _object(parts[0], 384)
            if set(header) != {"alg", "typ", "kid"} or header["alg"] != "EdDSA" or header["typ"] != "JWT":
                raise ValueError("invalid_calendar_bearer_algorithm")
            kid = header["kid"]
            if not isinstance(kid, str) or not KEY_ID.fullmatch(kid) or kid not in self.keys:
                raise ValueError("untrusted_calendar_signing_key")
            signed = (parts[0] + "." + parts[1]).encode("ascii")
            signature = _decode(parts[2], 64)
            if len(signature) != 64:
                raise ValueError("invalid_calendar_signature_length")
            self.keys[kid].verify(signature, signed)
            claims = _object(parts[1], 1536)
            if set(claims) != {"iss", "aud", "sub", "tenant_id", "scope", "iat", "nbf", "exp", "jti"}:
                raise ValueError("unexpected_calendar_claim")
            if claims["iss"] != ISSUER or claims["aud"] != AUDIENCE or claims["scope"] != SCOPE:
                raise ValueError("wrong_calendar_identity_audience")
            subject, jti = claims["sub"], claims["jti"]
            if (not isinstance(subject, str) or not SUBJECT.fullmatch(subject)
                or not isinstance(jti, str) or not JTI.fullmatch(jti)):
                raise ValueError("bad_calendar_subject")
            iat, nbf, exp = (claims[k] for k in ("iat", "nbf", "exp"))
            now = int(self.now())
            if (any(type(x) is not int for x in (iat, nbf, exp))
                or not (iat <= nbf <= exp) or exp <= iat
                or exp - iat > 300 or iat > now + 5 or nbf > now + 5
                or exp <= now):
                raise ValueError("calendar_token_expired_or_invalid")
            tenant = str(UUID(str(claims["tenant_id"])))
            if tenant != claims["tenant_id"]:
                raise ValueError("noncanonical_calendar_tenant")
            # Membership is read from the same canonical EmpireDB authority
            # as first-party CRM. Never accept role from bearer/client.
            membership = self.membership(subject, tenant)
            if (not isinstance(membership, TenantMembership)
                or membership.user_id != subject
                or membership.tenant_id != tenant
                or membership.status != "active"
                or membership.role not in ADMIN_ROLES
                or not membership.can("read")):
                raise ValueError("canonical_calendar_owner_membership_required")
            return CalendarConnectionPrincipal(
                tenant_id=tenant, subject=subject, token_id=jti,
                role=membership.role,
            )
        except Exception as exc:
            raise CalendarIdentityDenied("calendar_connection_identity_denied") from exc


def resolve_calendar_connection_principal(
    request: Request, *, verifier: SignedCalendarConnectionVerifier,
) -> CalendarConnectionPrincipal:
    values = request.headers.getlist("authorization")
    if len(values) != 1 or not values[0].startswith("Bearer "):
        raise CalendarIdentityDenied("calendar_connection_identity_denied")
    token = values[0][7:]
    if not token or token != token.strip() or " " in token:
        raise CalendarIdentityDenied("calendar_connection_identity_denied")
    return verifier.authenticate(token)
