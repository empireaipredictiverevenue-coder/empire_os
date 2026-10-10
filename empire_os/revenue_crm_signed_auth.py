"""First-party, opt-in signed tenant-read authentication for Revenue CRM.

Trust: pinned Ed25519 issuer public keys -> strictly validated short-lived
CRM-only bearer claims -> authenticated tenant ID -> existing per-tenant DB
login -> PostgreSQL session_user tenant binding.

No auth is activated by importing this module. Token minting belongs to the
independently authenticated EmpireOS login/issuer, never a public CRM endpoint.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Request

from empire_os.saas_scale import TenantMembership

MAX_TOKEN_BYTES = 4096
MAX_LIFETIME_SECONDS = 900
ALLOWED_CLOCK_SKEW_SECONDS = 30
AUTHORIZATION_AUDIENCE = "empire-revenue-crm"
AUTHORIZATION_SCOPE = "crm:read"
AUTHORIZATION_ISSUER = "empire-os"
_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SUBJECT = re.compile(r"^[A-Za-z0-9:@._/-]{1,128}$")
_JTI = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def _no_duplicate_properties(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate signed-token property")
        result[key] = value
    return result


def _decode(encoded: str, maximum: int) -> bytes:
    if not isinstance(encoded, str) or not encoded or "=" in encoded:
        raise ValueError("invalid token segment")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise ValueError("invalid token alphabet")
    if len(encoded) > maximum * 2:
        raise ValueError("oversized token segment")
    try:
        raw = base64.b64decode(
            encoded + ("=" * (-len(encoded) % 4)),
            altchars=b"-_", validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid token encoding") from exc
    if len(raw) > maximum:
        raise ValueError("oversized token segment")
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != encoded:
        raise ValueError("noncanonical token encoding")
    return raw


def _object(segment: str, maximum: int) -> dict[str, Any]:
    raw = _decode(segment, maximum)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicate_properties,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid constant")),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid token JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("signed token object required")
    return value


class SignedCrmTenantVerifier:
    """Pinned-key JWT EdDSA verifier: never accepts caller-supplied keys."""

    def __init__(
        self, public_keys: Mapping[str, bytes | Ed25519PublicKey],
        *,
        load_membership: Callable[[str, str], TenantMembership | None],
        now: Callable[[], int] | None = None,
    ) -> None:
        if not callable(load_membership):
            raise ValueError("trusted CRM membership lookup required")
        if not public_keys:
            raise ValueError("trusted CRM signing public keys required")
        keys: dict[str, Ed25519PublicKey] = {}
        for key_id, key_material in public_keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise ValueError("invalid trusted CRM key ID")
            if isinstance(key_material, Ed25519PublicKey):
                key = key_material
            elif isinstance(key_material, bytes) and len(key_material) == 32:
                key = Ed25519PublicKey.from_public_bytes(key_material)
            else:
                raise ValueError("invalid trusted CRM Ed25519 key")
            keys[key_id] = key
        self._public_keys = keys
        self._load_membership = load_membership
        self._now = now or (lambda: int(time.time()))

    def authenticate(self, token: str) -> str:
        if not isinstance(token, str) or len(token) > MAX_TOKEN_BYTES:
            raise ValueError("invalid CRM bearer")
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("malformed CRM bearer")
        header = _object(parts[0], 384)
        if set(header) != {"alg", "typ", "kid"}:
            raise ValueError("unexpected CRM JWT headers")
        if header["alg"] != "EdDSA" or header["typ"] != "JWT":
            raise ValueError("unsupported CRM JWT algorithm")
        key_id = header["kid"]
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ValueError("invalid CRM signing key")
        key = self._public_keys.get(key_id)
        if key is None:
            raise ValueError("untrusted CRM signing key")
        signature = _decode(parts[2], 64)
        if len(signature) != 64:
            raise ValueError("invalid CRM signature length")
        try:
            key.verify(signature, (parts[0] + "." + parts[1]).encode("ascii"))
        except InvalidSignature as exc:
            raise ValueError("invalid CRM signature") from exc

        claims = _object(parts[1], 1536)
        if set(claims) != {
            "iss", "aud", "sub", "tenant_id", "scope", "iat", "nbf", "exp", "jti",
        }:
            raise ValueError("unexpected CRM identity claims")
        if (
            claims["iss"] != AUTHORIZATION_ISSUER
            or claims["aud"] != AUTHORIZATION_AUDIENCE
            or claims["scope"] != AUTHORIZATION_SCOPE
        ):
            raise ValueError("CRM issuer, audience or scope mismatch")
        if not isinstance(claims["sub"], str) or not _SUBJECT.fullmatch(claims["sub"]):
            raise ValueError("verified CRM subject required")
        if not isinstance(claims["jti"], str) or not _JTI.fullmatch(claims["jti"]):
            raise ValueError("valid CRM token ID required")
        iat, nbf, exp = (claims[name] for name in ("iat", "nbf", "exp"))
        if any(type(v) is not int for v in (iat, nbf, exp)):
            raise ValueError("integer CRM token timestamps required")
        now = int(self._now())
        if (
            exp <= iat or exp - iat > MAX_LIFETIME_SECONDS
            or iat > now + ALLOWED_CLOCK_SKEW_SECONDS
            or nbf > now + ALLOWED_CLOCK_SKEW_SECONDS
            or exp <= now - ALLOWED_CLOCK_SKEW_SECONDS
            or nbf > exp
        ):
            raise ValueError("expired or invalid CRM bearer lifetime")
        try:
            tenant = str(UUID(str(claims["tenant_id"])))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("invalid signed CRM tenant ID") from exc
        if tenant != claims["tenant_id"]:
            raise ValueError("noncanonical signed CRM tenant ID")

        # Cryptographic validity alone is NOT active user/tenant authority.
        # Require a fresh authoritative membership read on every request;
        # no caller-provided membership objects, booleans or bearer claims.
        try:
            membership = self._load_membership(claims["sub"], tenant)
            permitted = (
                isinstance(membership, TenantMembership)
                and membership.user_id == claims["sub"]
                and membership.tenant_id == tenant
                and membership.can("read")
            )
        except Exception:
            permitted = False
        if not permitted:
            raise ValueError("active canonical CRM membership required")
        return tenant


def build_signed_crm_tenant_authenticator(
    trusted_public_keys: Mapping[str, bytes | Ed25519PublicKey],
    *,
    load_membership: Callable[[str, str], TenantMembership | None],
    now: Callable[[], int] | None = None,
) -> Callable[[Request], str | None]:
    """Opt-in verified bearer hook; caller must provide authoritative membership.

    The lookup must query a trusted up-to-date identity store keyed by both
    signed user and signed tenant. It must never trust request-provided roles.
    If no such store exists in the live runtime, do not mount this hook.
    """
    verifier = SignedCrmTenantVerifier(
        trusted_public_keys, load_membership=load_membership, now=now,
    )

    def authenticate_tenant(request: Request) -> str | None:
        headers = request.headers.getlist("authorization")
        if len(headers) != 1:
            return None
        authorization = headers[0]
        if not authorization.startswith("Bearer "):
            return None
        token = authorization[len("Bearer "):]
        if not token or token != token.strip() or " " in token:
            return None
        try:
            return verifier.authenticate(token)
        except ValueError:
            # Invalid identity is unauthenticated (401 at the CRM router).
            return None

    return authenticate_tenant
