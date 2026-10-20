"""Short-lived tenant-scoped access token validation for a disabled management API.

No tokens are minted here. Production deployment must integrate authoritative
identity-provider lifecycle, key rotation/revocation and user membership.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import time


SUPPORTED_SCOPES = frozenset({
    "recovery:read", "recovery:queue", "recovery:patterns", "recovery:knowledge",
    "recovery:workflow",
})
ISSUER = "empire-inbound-recovery"
AUDIENCE = "empire-inbound-recovery-management"


class RecoveryAccessDenied(ValueError):
    """Fail closed without disclosing credential details."""


@dataclass(frozen=True)
class RecoveryActor:
    tenant_id: str
    subject: str
    token_id: str
    scopes: frozenset[str]


def authenticate_recovery_reader(
    authorization: str | None,
    *,
    signing_secret: str,
    required_scope: str,
    now: int | None = None,
) -> RecoveryActor:
    if required_scope not in SUPPORTED_SCOPES:
        raise ValueError("unsupported_management_scope")
    if not isinstance(signing_secret, str) or len(signing_secret.encode("utf-8")) < 32:
        raise RecoveryAccessDenied("management_auth_not_configured")
    tokens = authorization.strip().split() if isinstance(authorization, str) else []
    if len(tokens) != 2 or tokens[0].lower() != "bearer":
        raise RecoveryAccessDenied("management_credential_required")
    try:
        import jwt
        claims = jwt.decode(
            tokens[1], signing_secret, algorithms=["HS256"],
            issuer=ISSUER, audience=AUDIENCE,
            options={
                "require": ["iss", "aud", "iat", "nbf", "exp", "jti", "sub", "tenant_id", "scopes"],
            },
            leeway=5,
        )
    except Exception as exc:
        raise RecoveryAccessDenied("invalid_management_credential") from exc

    current = int(time.time() if now is None else now)
    iat, expires, not_before = (claims.get(x) for x in ("iat", "exp", "nbf"))
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (iat, expires, not_before)):
        raise RecoveryAccessDenied("invalid_management_timestamps")
    if expires <= iat or expires - iat > 900 or iat > current + 5 or expires <= current:
        raise RecoveryAccessDenied("management_token_lifetime_exceeded")
    if not_before > current + 5 or not_before < iat - 5:
        raise RecoveryAccessDenied("invalid_management_not_before")
    for item in ("tenant_id", "sub", "jti"):
        value = claims.get(item)
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise RecoveryAccessDenied("invalid_management_identity")
    raw_scopes = claims.get("scopes")
    if not isinstance(raw_scopes, list) or any(
        not isinstance(scope, str) or scope not in SUPPORTED_SCOPES for scope in raw_scopes
    ):
        raise RecoveryAccessDenied("invalid_management_scopes")
    scopes = frozenset(raw_scopes)
    if required_scope not in scopes:
        raise RecoveryAccessDenied("management_scope_denied")
    return RecoveryActor(
        tenant_id=claims["tenant_id"],
        subject=claims["sub"],
        token_id=claims["jti"],
        scopes=scopes,
    )
