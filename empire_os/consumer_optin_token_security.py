"""Key-separated, purpose-scoped consumer email tokens and state decisions.

Pure, no network / DB / email. A live private backend must keep keys outside
the database and control transactional token consumption, suppression and
delivery. This module is useful for fixture-based security verification.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

EMAIL_SCOPE = b"empire.consumer.own_brand_homeowner_email_lookup.v1"
TOKEN_SCOPE = b"empire.consumer.roofing_token.v1"
ACTIONS = frozenset({"confirm", "unsubscribe"})


@dataclass(frozen=True)
class TokenReceipt:
    # The cleartext secret is intended ONLY for private sender delivery and
    # must never be retained in logs, analytics, database rows or CRM.
    token: str
    token_hmac: str
    action: str
    issued_at: datetime
    expires_at: datetime


def canonical_email(email: str) -> str:
    if not isinstance(email, str) or email != email.strip() or len(email) > 254:
        raise ValueError("email format invalid")
    local, at, domain = email.rpartition("@")
    if not at or not local or "@" in local or not domain or "." not in domain:
        raise ValueError("email format invalid")
    # Lowering the domain is safe, but never strip local dots, plus tags or
    # other provider-specific semantics that could merge two identities.
    if any(ord(char) < 33 or ord(char) > 126 for char in email):
        raise ValueError("email format invalid")
    return local + "@" + domain.lower()


def _key(secret: bytes) -> bytes:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("a distinct 256-bit private key is required")
    return secret


def email_lookup_hmac(email: str, *, key: bytes) -> str:
    return hmac.new(_key(key), EMAIL_SCOPE + b"|" +
                    canonical_email(email).encode("ascii"), hashlib.sha256).hexdigest()


def token_fingerprint(token: str, *, action: str, key: bytes) -> str:
    if action not in ACTIONS:
        raise ValueError("unknown token purpose")
    if not isinstance(token, str) or len(token) != 43:
        raise ValueError("token length invalid")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in token):
        raise ValueError("token alphabet invalid")
    return hmac.new(_key(key), TOKEN_SCOPE + b"|" + action.encode("ascii")
                    + b"|" + token.encode("ascii"), hashlib.sha256).hexdigest()


def issue_token(*, action: str, key: bytes, now: datetime,
                ttl: timedelta) -> TokenReceipt:
    if action not in ACTIONS:
        raise ValueError("unknown token purpose")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware clock required")
    if not isinstance(ttl, timedelta):
        raise ValueError("time-to-live required")
    max_ttl = timedelta(hours=24) if action == "confirm" else timedelta(days=30)
    if ttl <= timedelta(0) or ttl > max_ttl:
        raise ValueError("token expiry outside policy")
    raw = secrets.token_urlsafe(32)
    return TokenReceipt(
        token=raw, token_hmac=token_fingerprint(raw, action=action, key=key),
        action=action, issued_at=now, expires_at=now + ttl
    )


def review_token_use(
    *, action: str, presented_token: str, expected_hmac: str,
    key: bytes, expires_at: datetime, now: datetime,
    already_consumed: bool, currently_suppressed: bool,
    subscription_state: str,
) -> str:
    """One pure, deny-first decision to be committed under a DB row lock.

    Calls cannot substitute for a transactional implementation; especially
    check suppression again before any email is sent.
    """
    if action not in ACTIONS:
        return "DENIED_ACTION"
    if already_consumed or currently_suppressed:
        return "DENIED_REPLAY_OR_SUPPRESSION"
    if any(t.tzinfo is None or t.utcoffset() is None for t in (expires_at, now)):
        return "DENIED_CLOCK"
    if now >= expires_at:
        return "DENIED_EXPIRED"
    try:
        calculated = token_fingerprint(presented_token, action=action, key=key)
    except ValueError:
        return "DENIED_INVALID_TOKEN"
    if not isinstance(expected_hmac, str) or not hmac.compare_digest(calculated, expected_hmac):
        return "DENIED_INVALID_TOKEN"
    if action == "confirm" and subscription_state == "pending_verification":
        return "ALLOW_ATOMIC_CONFIRMATION"
    if action == "unsubscribe" and subscription_state in {
        "pending_verification", "verified"
    }:
        return "ALLOW_ATOMIC_UNSUBSCRIBE"
    return "DENIED_STATE"
