"""Research-only Founder identity adapter for the existing Cloudflare Access edge.

Never trust an unverified forwarded email, local request, or client-supplied role.
An unset configuration denies all. Service accounts and tenant sessions cannot
implicitly become Founder sessions. No alternate account/identity database.
"""
from __future__ import annotations

import hmac
import ipaddress
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


# An alternative *existing* authenticated Founder path is the SSH/loopback-only
# Console. It must be independently ingress-reviewed and explicitly enabled.
# This is NOT a public header- or email-based identity shortcut. SSH authenticates
# the operator, while this bearer gates the server-to-server API bridge.
SSH_AUTH_MODE = "ssh_loopback"
SSH_KEY_ENV = "EMPIRE_RESEARCH_SSH_BRIDGE_SECRET"
SSH_GATE_ENV = "EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED"
SSH_INGRESS_ENV = "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED"


def _valid_ssh_bridge_key(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{48,256}", value) is not None


def require_ssh_loopback_founder(request: Request) -> str:
    """Local SSH-authenticated operator mode; no anonymous local API requests.

    This is deliberately independent from Cloudflare Access and cannot be
    selected by request headers, cookies, JWT claims or arbitrary hostnames.
    It requires a strong privately configured server-to-server credential.
    """
    secret = os.environ.get(SSH_KEY_ENV, "")
    if (os.environ.get(SSH_GATE_ENV) != "1"
            or os.environ.get(SSH_INGRESS_ENV) != "1"
            or not _valid_ssh_bridge_key(secret)):
        raise HTTPException(503, "FOUNDER_RESEARCH_SSH_BOUNDARY_NOT_CONFIGURED")
    peer = request.client.host if request.client else ""
    try:
        local_peer = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        local_peer = False
    # Forwarding signals at the internal API are never part of our trusted
    # direct Next-to-loopback service-to-service request.
    if (not local_peer or any(request.headers.get(key) for key in (
            "forwarded", "x-forwarded-for", "x-forwarded-host",
            "x-real-ip", "cf-connecting-ip", "cf-ray", "via"))):
        raise HTTPException(403, "FOUNDER_RESEARCH_SSH_LOOPBACK_ONLY")
    bearer = request.headers.get("authorization", "")
    if (not bearer.startswith("Bearer ") or len(bearer) > 280
            or not hmac.compare_digest(bearer[7:], secret)):
        raise HTTPException(401, "FOUNDER_RESEARCH_PRIVATE_BRIDGE_REQUIRED")
    return "founder-ssh-authenticated-operator"


def require_founder_research_authority(request: Request) -> str:
    """Default: verified Cloudflare JWT. SSH mode only via gated server env."""
    mode = os.environ.get("EMPIRE_FOUNDER_RESEARCH_AUTH_MODE", "cloudflare_access")
    if mode == "cloudflare_access":
        return require_founder_access_jwt(request)
    if mode == SSH_AUTH_MODE:
        return require_ssh_loopback_founder(request)
    raise HTTPException(503, "FOUNDER_RESEARCH_AUTH_MODE_UNRECOGNISED")
