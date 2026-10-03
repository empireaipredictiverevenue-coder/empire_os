"""Short-lived authenticated session tokens for Digital Avatar Presence."""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import secrets
from typing import Any, Mapping


_AUDIENCE = "empire-digital-avatar-presence"
_VERSION = 1


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise ValueError("presence token base64 invalid") from exc


def _epoch(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("presence token time must include timezone")
    return int(value.astimezone(timezone.utc).timestamp())


@dataclass(frozen=True)
class AvatarPresenceClaims:
    meeting_id: str
    avatar_id: str
    bot_id: str
    issued_at: int
    expires_at: int
    nonce: str
    mode: str = "copilot"
    audience: str = _AUDIENCE
    version: int = _VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AvatarPresenceToken:
    token: str
    token_sha256: str
    claims: AvatarPresenceClaims
    raw_secret_persisted: bool = False
    execution_authority: str = "none"


def issue_avatar_presence_token(
    *,
    secret: str,
    meeting_id: str,
    avatar_id: str,
    bot_id: str,
    now: datetime,
    ttl_seconds: int = 300,
    nonce: str | None = None,
) -> AvatarPresenceToken:
    key = str(secret or "").encode("utf-8")
    if len(key) < 32:
        raise ValueError("presence signing secret must be at least 32 bytes")
    clean_meeting = str(meeting_id or "").strip()
    clean_avatar = str(avatar_id or "").strip()
    clean_bot = str(bot_id or "").strip()
    if not clean_meeting or not clean_avatar or not clean_bot:
        raise ValueError("presence meeting, avatar and bot identity required")
    if ttl_seconds < 30 or ttl_seconds > 3600:
        raise ValueError("presence token ttl must be between 30 and 3600 seconds")

    issued = _epoch(now)
    claims = AvatarPresenceClaims(
        meeting_id=clean_meeting,
        avatar_id=clean_avatar,
        bot_id=clean_bot,
        issued_at=issued,
        expires_at=issued + int(ttl_seconds),
        nonce=str(nonce or secrets.token_urlsafe(12)),
    )
    payload = json.dumps(
        claims.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = _b64url(payload)
    signature = _b64url(hmac.new(key, encoded.encode("ascii"), sha256).digest())
    token = encoded + "." + signature
    return AvatarPresenceToken(
        token=token,
        token_sha256=sha256(token.encode("utf-8")).hexdigest(),
        claims=claims,
    )


def verify_avatar_presence_token(
    *,
    secret: str,
    token: str,
    now: datetime,
    expected_meeting_id: str | None = None,
    expected_avatar_id: str | None = None,
    expected_bot_id: str | None = None,
) -> AvatarPresenceClaims:
    key = str(secret or "").encode("utf-8")
    if len(key) < 32:
        raise ValueError("presence signing secret must be at least 32 bytes")
    raw = str(token or "").strip()
    if raw.count(".") != 1:
        raise ValueError("presence token shape invalid")
    encoded, supplied_sig = raw.split(".", 1)
    expected_sig = _b64url(
        hmac.new(key, encoded.encode("ascii"), sha256).digest()
    )
    if not hmac.compare_digest(supplied_sig, expected_sig):
        raise ValueError("presence token signature invalid")

    try:
        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("presence token payload invalid") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("presence token claims must be object")
    try:
        claims = AvatarPresenceClaims(**dict(payload))
    except TypeError as exc:
        raise ValueError("presence token claims invalid") from exc

    if claims.version != _VERSION or claims.audience != _AUDIENCE:
        raise ValueError("presence token audience/version invalid")
    if claims.mode != "copilot":
        raise ValueError("presence token mode invalid")
    current = _epoch(now)
    if current < claims.issued_at:
        raise ValueError("presence token not active")
    if current >= claims.expires_at:
        raise ValueError("presence token expired")
    if claims.expires_at - claims.issued_at > 3600:
        raise ValueError("presence token lifetime invalid")

    expected = (
        ("meeting", expected_meeting_id, claims.meeting_id),
        ("avatar", expected_avatar_id, claims.avatar_id),
        ("bot", expected_bot_id, claims.bot_id),
    )
    for label, wanted, actual in expected:
        if wanted is not None and str(wanted).strip() != actual:
            raise ValueError(f"presence token {label} mismatch")
    return claims
