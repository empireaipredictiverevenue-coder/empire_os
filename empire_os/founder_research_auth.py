"""Research-only Founder identity adapter for the existing Cloudflare Access edge.

Never trust an unverified forwarded email, local request, or client-supplied role.
An unset configuration denies all. Service accounts and tenant sessions cannot
implicitly become Founder sessions. No alternate account/identity database.
"""
from __future__ import annotations

import hmac
import os
import re
from functools import lru_cache

from fastapi import HTTPException, Request
import jwt


@lru_cache(maxsize=4)
def _jwks_client(team_domain: str):
    return jwt.PyJWKClient(
        f"https://{team_domain}/cdn-cgi/access/certs",
        cache_jwk_set=True,
        lifespan=300,
        timeout=4,
    )


def require_founder_access_jwt(request: Request) -> str:
    """Validate signature, issuer, audience, expiry and exact Founder subject."""
    team = os.environ.get("EMPIRE_FOUNDER_CF_TEAM_DOMAIN", "").strip().lower()
    audience = os.environ.get("EMPIRE_FOUNDER_CF_ACCESS_AUD", "").strip()
    founder_sub = os.environ.get("EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB", "").strip()
    if (not re.fullmatch(r"[a-z0-9-]+\.cloudflareaccess\.com", team)
        or not audience or len(audience) > 300 or not founder_sub
        or len(founder_sub) > 300):
        raise HTTPException(503, "FOUNDER_RESEARCH_IDENTITY_NOT_CONFIGURED")
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or len(auth) > 8199:
        raise HTTPException(401, "VERIFIED_FOUNDER_SESSION_REQUIRED")
    token = auth[7:]
    if not token or any(ch.isspace() for ch in token):
        raise HTTPException(401, "VERIFIED_FOUNDER_SESSION_REQUIRED")
    try:
        key = _jwks_client(team).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], audience=audience,
            issuer=f"https://{team}",
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=15,
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not hmac.compare_digest(subject, founder_sub):
            raise HTTPException(403, "FOUNDER_RESEARCH_SUBJECT_NOT_ALLOWED")
        return subject
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError, TimeoutError, OSError):
        raise HTTPException(401, "VERIFIED_FOUNDER_SESSION_REQUIRED") from None
