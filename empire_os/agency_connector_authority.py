"""Agency connector access gate over EXISTING EmpireOS tenant-isolation primitives.

No issuer, database login, signing key, environment auth, or production service is
created here. Trusted, freshly authenticated membership and site-grant readers
must be wired by the *canonical* owners. CRM-audience tokens never grant agency
rights. Absence of any authority dependency fails closed.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.saas_scale import TenantMembership
from empire_os.tenant_isolation import TenantResourceRef, authorize_tenant_resource

SCHEMA = "empire.agency.connector.authority.v1"
AUDIENCE = "empire-agency-connector"
ISSUER = "empire-os"
DOMAIN = b"empire-agency-connector-authority-v1:"
OPERATIONS = ("capabilities:read", "vehicles:read")
MAX_AGE = 180
_ALLOWED = frozenset({
    "schema", "iss", "aud", "sub", "tenant_id", "site_id",
    "connector_id", "credential_ref", "wp_origin", "operations",
    "iat", "nbf", "exp", "jti",
})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,95}$")
_SUB = re.compile(r"^[A-Za-z0-9:@._/-]{3,128}$")
_JTI = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
_LOOPBACK = re.compile(r"^http://127[.]0[.]0[.]1:[1-9][0-9]{1,4}$")


@dataclass(frozen=True)
class AgencySiteGrant:
    user_id: str
    tenant_id: str
    site_id: str
    connector_id: str
    credential_ref: str
    wp_origin: str
    status: str
    operations: tuple[str, ...]


@dataclass(frozen=True)
class AuthorizedConnectorRead:
    tenant_id: str
    site_id: str
    connector_id: str
    credential_ref: str
    wp_origin: str
    user_id: str
    operations: tuple[str, ...]
    expires_at: int


def _decode(value: Any, length: int) -> bytes:
    if (not isinstance(value, str) or not value or len(value) > 128
            or "=" in value or not re.fullmatch(r"[A-Za-z0-9_-]+", value)):
        raise ValueError("Invalid authority signature encoding")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid authority signature encoding") from None
    if len(raw) != length or base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != value:
        raise ValueError("Invalid authority signature bytes")
    return raw


def _signed_bytes(claims: Mapping[str, Any]) -> bytes:
    return DOMAIN + json.dumps(dict(claims), sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")


def authorize_agency_connector(
    envelope: Mapping[str, Any], *,
    pinned_authority_keys: Mapping[str, bytes],
    membership_reader: Callable[[str, str], TenantMembership | None],
    site_grant_reader: Callable[[str, str, str, str], AgencySiteGrant | None],
    consume_nonce: Callable[[str], bool],
    now: Callable[[], int] | None = None,
) -> AuthorizedConnectorRead:
    """Verify purpose-bound issuer signature AND fresh canonical membership/site grant.

    No raw request role, self-asserted tenant, CRM audience or environment
    selector can substitute for both trust readers. Signed proof is short-lived,
    replay-checked, and can only carry two synthetic read operations.
    """
    if (not isinstance(envelope, Mapping) or set(envelope) != {"kid", "payload", "signature"}
            or not isinstance(envelope.get("payload"), Mapping)
            or not pinned_authority_keys or not callable(membership_reader)
            or not callable(site_grant_reader) or not callable(consume_nonce)):
        raise ValueError("Trusted agency authority dependencies required")

    kid, claims = envelope["kid"], envelope["payload"]
    if not isinstance(kid, str) or not _ID.fullmatch(kid) or set(claims) != _ALLOWED:
        raise ValueError("Invalid agency authority claims")
    key = pinned_authority_keys.get(kid)
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Untrusted agency authority key")
    try:
        signed_payload = _signed_bytes(claims)
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("Invalid signed agency authority payload") from None
    if len(signed_payload) > 3072:
        raise ValueError("Oversized agency authority payload")
    signature = _decode(envelope["signature"], 64)
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature, signed_payload)
    except (InvalidSignature, ValueError, TypeError):
        raise ValueError("Invalid signed agency authority") from None

    if (claims["schema"] != SCHEMA or claims["aud"] != AUDIENCE
            or claims["iss"] != ISSUER or type(claims["iat"]) is not int
            or type(claims["nbf"]) is not int or type(claims["exp"]) is not int):
        raise ValueError("Agency issuer, audience or time invalid")
    issued, not_before, expiry = claims["iat"], claims["nbf"], claims["exp"]
    current = int((now or time.time)())
    if (issued > current + 15 or not_before > current or expiry <= current
            or expiry <= issued or expiry - issued > MAX_AGE):
        raise ValueError("Expired or invalid agency grant")
    if (not isinstance(claims["sub"], str) or not _SUB.fullmatch(claims["sub"])
            or not isinstance(claims["jti"], str) or not _JTI.fullmatch(claims["jti"])):
        raise ValueError("Invalid signed subject or nonce")
    try:
        tenant = str(UUID(claims["tenant_id"]))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Noncanonical tenant ID") from None
    if tenant != claims["tenant_id"]:
        raise ValueError("Noncanonical tenant ID")
    for field in ("site_id", "connector_id", "credential_ref"):
        if not isinstance(claims[field], str) or not _ID.fullmatch(claims[field]):
            raise ValueError("Invalid signed resource binding")
    if (not isinstance(claims["wp_origin"], str)
            or not _LOOPBACK.fullmatch(claims["wp_origin"])
            or not 1 <= urlsplit(claims["wp_origin"]).port <= 65535
            or type(claims["operations"]) is not list
            or claims["operations"] != list(OPERATIONS)):
        raise ValueError("Untrusted URL or permissions")

    try:
        membership = membership_reader(claims["sub"], tenant)
        if (not isinstance(membership, TenantMembership)
                or membership.user_id != claims["sub"]
                or membership.tenant_id != tenant
                or membership.role not in ("owner", "admin")):
            raise ValueError()
        decision = authorize_tenant_resource(
            membership=membership,
            resource=TenantResourceRef(tenant_id=tenant, resource_type="agency_wordpress_site",
                                       resource_id=claims["site_id"]),
            permission="read",
        )
        if not decision.allowed:
            raise ValueError()
        grant = site_grant_reader(claims["sub"], tenant, claims["site_id"], claims["connector_id"])
        if (not isinstance(grant, AgencySiteGrant) or grant.status != "active"
                or grant.user_id != claims["sub"] or grant.tenant_id != tenant
                or grant.site_id != claims["site_id"] or grant.connector_id != claims["connector_id"]
                or grant.credential_ref != claims["credential_ref"]
                or grant.wp_origin != claims["wp_origin"]
                or grant.operations != OPERATIONS):
            raise ValueError()
        if consume_nonce(claims["jti"]) is not True:
            raise ValueError()
    except Exception:
        raise ValueError("Fresh agency membership, site grant or replay protection denied") from None

    return AuthorizedConnectorRead(
        tenant_id=tenant, site_id=claims["site_id"], connector_id=claims["connector_id"],
        credential_ref=claims["credential_ref"], wp_origin=claims["wp_origin"],
        user_id=claims["sub"], operations=OPERATIONS, expires_at=expiry,
    )
