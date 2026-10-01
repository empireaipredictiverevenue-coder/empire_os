"""Environment-backed production binding for governed A2A identity/commerce."""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.a2a_commerce_transport import (
    PostgresA2AIntentRpc,
    RpcCommercialIntentRepository,
)
from empire_os.a2a_identity import NonceRegistry, SignatureVerifier
from empire_os.a2a_identity_transport import (
    PostgresA2AIdentityNonceRpc,
    RpcNonceRegistry,
)

KEYS_ENV = "EMPIRE_A2A_TRUSTED_ED25519_KEYS_JSON"
IDENTITY_DSN_ENV = "EMPIRE_A2A_IDENTITY_DSN"
INTENT_DSN_ENV = "EMPIRE_A2A_INTENT_DSN"
LIVE_VERIFIED_ENV = "EMPIRE_A2A_LIVE_VERIFIED"


@dataclass(frozen=True)
class A2ARuntimeBinding:
    configured: bool
    authentication_status: str
    blockers: tuple[str, ...]
    trusted_key_ids: frozenset[str]
    verifier: SignatureVerifier | None
    nonce_registry: NonceRegistry | None
    repository: RpcCommercialIntentRepository | None

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "authentication_status": self.authentication_status,
            "blockers": list(self.blockers),
            "trusted_key_count": len(self.trusted_key_ids),
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
        }


def _decode_base64(value: str, *, field: str) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field} required")
    padded = raw + ("=" * (-len(raw) % 4))
    try:
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{field} must be base64") from exc


def _load_keys(raw: str | None) -> tuple[dict[str, Ed25519PublicKey], str | None]:
    text = str(raw or "").strip()
    if not text:
        return {}, "trusted_ed25519_keys_missing"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}, "trusted_ed25519_keys_invalid_json"
    if not isinstance(payload, Mapping) or not payload:
        return {}, "trusted_ed25519_keys_missing"

    keys: dict[str, Ed25519PublicKey] = {}
    try:
        for raw_id, raw_key in payload.items():
            key_id = str(raw_id or "").strip()
            if not key_id:
                raise ValueError("key_id required")
            key_bytes = _decode_base64(str(raw_key or ""), field=f"public_key:{key_id}")
            if len(key_bytes) != 32:
                raise ValueError("ed25519 public key must be 32 bytes")
            keys[key_id] = Ed25519PublicKey.from_public_bytes(key_bytes)
    except (TypeError, ValueError):
        return {}, "trusted_ed25519_keys_invalid"
    return keys, None


def load_a2a_runtime(env: Mapping[str, str] | None = None) -> A2ARuntimeBinding:
    values = dict(env or {})
    keys, key_error = _load_keys(values.get(KEYS_ENV))
    identity_dsn = str(values.get(IDENTITY_DSN_ENV) or "").strip()
    intent_dsn = str(values.get(INTENT_DSN_ENV) or "").strip()

    blockers: list[str] = []
    if key_error:
        blockers.append(key_error)
    if not identity_dsn:
        blockers.append("identity_dsn_missing")
    if not intent_dsn:
        blockers.append("intent_dsn_missing")

    if blockers:
        return A2ARuntimeBinding(
            configured=False,
            authentication_status="not_activated",
            blockers=tuple(blockers),
            trusted_key_ids=frozenset(keys),
            verifier=None,
            nonce_registry=None,
            repository=None,
        )

    def verifier(key_id: str, payload: bytes, signature: str) -> bool:
        public_key = keys.get(str(key_id))
        if public_key is None:
            return False
        try:
            signature_bytes = _decode_base64(signature, field="signature")
            if len(signature_bytes) != 64:
                return False
            public_key.verify(signature_bytes, payload)
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True

    nonce_registry = RpcNonceRegistry(PostgresA2AIdentityNonceRpc(identity_dsn))
    repository = RpcCommercialIntentRepository(PostgresA2AIntentRpc(intent_dsn))

    live_verified = str(values.get(LIVE_VERIFIED_ENV) or "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    return A2ARuntimeBinding(
        configured=True,
        authentication_status=("activated" if live_verified else "configured_unverified"),
        blockers=(),
        trusted_key_ids=frozenset(keys),
        verifier=verifier,
        nonce_registry=nonce_registry,
        repository=repository,
    )
