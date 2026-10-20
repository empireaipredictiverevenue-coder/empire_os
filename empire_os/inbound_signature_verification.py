"""Strict Vonage Voice signed-webhook verifier, independent of live routing.

The signature is the provider's HS256 JWT in Authorization: Bearer. Validate
issuer, API key, optional Voice application ID, iat/jti and *raw* body SHA-256.
This returns authenticated claims, not permission to place or route calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import time


@dataclass(frozen=True)
class VerifiedVoiceCallback:
    provider: str
    api_key: str
    application_id: str | None
    jwt_id: str
    issued_at: int
    payload_sha256: str


class InvalidVoiceCallback(ValueError):
    """External callback cannot be trusted; do not expose validation detail."""


def verify_vonage_voice_callback(
    authorization: str,
    raw_body: bytes,
    *,
    signature_secret: str,
    expected_api_key: str,
    expected_application_id: str | None = None,
    now: int | None = None,
    max_age_seconds: int = 300,
    max_payload_bytes: int = 65536,
) -> VerifiedVoiceCallback:
    """Validate a Voice callback before any conversion or persistence.

    jwt_id should additionally be deduplicated in a durable replay cache when
    enabling a future live HTTP adapter. No request or response side effects.
    """
    if not signature_secret or not expected_api_key:
        raise ValueError("vonage_verification_not_configured")
    if not isinstance(raw_body, bytes) or len(raw_body) > max_payload_bytes or not raw_body:
        raise InvalidVoiceCallback("invalid_callback_payload")
    parts = authorization.strip().split() if isinstance(authorization, str) else []
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise InvalidVoiceCallback("invalid_callback_authorization")
    if max_age_seconds < 1 or max_age_seconds > 900:
        raise ValueError("invalid_max_age")
    try:
        import jwt  # PyJWT; installed in the existing voice optional dependency group.

        claims = jwt.decode(
            parts[1],
            signature_secret,
            algorithms=["HS256"],
            issuer="Vonage",
            options={
                "require": ["iss", "iat", "jti", "api_key", "payload_hash"],
                "verify_exp": False,  # Some Vonage callback JWTs contain no exp.
                "verify_nbf": True,
            },
            leeway=0,
        )
    except Exception as exc:
        # Missing JWT dependency or malformed/unsigned token fails closed.
        raise InvalidVoiceCallback("invalid_callback_signature_or_claims") from exc
    api_key = claims.get("api_key")
    if not isinstance(api_key, str) or not hmac.compare_digest(api_key, expected_api_key):
        raise InvalidVoiceCallback("callback_api_key_mismatch")
    application_id = claims.get("application_id")
    if expected_application_id is not None:
        if not isinstance(application_id, str) or not hmac.compare_digest(application_id, expected_application_id):
            raise InvalidVoiceCallback("callback_application_mismatch")
    issued_at = claims.get("iat")
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise InvalidVoiceCallback("invalid_callback_issued_at")
    current_time = int(time.time() if now is None else now)
    if issued_at > current_time + 30 or issued_at < current_time - max_age_seconds:
        raise InvalidVoiceCallback("callback_outside_freshness_window")
    jwt_id = claims.get("jti")
    if not isinstance(jwt_id, str) or not jwt_id.strip() or len(jwt_id) > 180:
        raise InvalidVoiceCallback("invalid_callback_jti")
    payload_hash = claims.get("payload_hash")
    digest = sha256(raw_body).hexdigest()
    if not isinstance(payload_hash, str) or not hmac.compare_digest(payload_hash, digest):
        raise InvalidVoiceCallback("callback_payload_hash_mismatch")
    # JSON must decode to an object, not a list or scalar. Do not trust business ID in it.
    try:
        body = json.loads(raw_body)
    except (ValueError, UnicodeError) as exc:
        raise InvalidVoiceCallback("invalid_callback_json") from exc
    if not isinstance(body, dict):
        raise InvalidVoiceCallback("callback_object_required")
    return VerifiedVoiceCallback(
        provider="vonage",
        api_key=api_key,
        application_id=application_id if isinstance(application_id, str) else None,
        jwt_id=jwt_id,
        issued_at=issued_at,
        payload_sha256=digest,
    )
