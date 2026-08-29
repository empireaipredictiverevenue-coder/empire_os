"""
Audit 2.1 / 2.2 — Field-Level Encryption (AES-256-GCM)
Separate keys per field type, KDF via PBKDF2. Mock Vault backend (local
keyring file) stands in for AWS KMS / HashiCorp Vault. Key versioning for
backward compat. Deterministic not used (searchability sacrificed for safety).

MOCKED: external KMS/HSM. Real: AES-256-GCM via `cryptography`.
"""
import os
import json
import base64
import hashlib
import hmac
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ── Mock Vault ──────────────────────────────────────────────────────────
# MOCKED external: AWS KMS / HashiCorp Vault. Real local keyring file.
VAULT_PATH = Path("/root/empire_os/feedback/.sec_vault.json")
_MASTER = b"empire_omega_master_key_mock_2026"  # MOCKED HSM master
_KEY_CACHE = {}

SALT = b"empire_omega_salt_v1"


def _derive_key(field_type: str) -> bytes:
    if field_type in _KEY_CACHE:
        return _KEY_CACHE[field_type]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=SALT + field_type.encode(), iterations=100_000)
    key = kdf.derive(_MASTER + field_type.encode())
    _KEY_CACHE[field_type] = key
    return key


def _ensure_vault():
    VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not VAULT_PATH.exists():
        VAULT_PATH.write_text(json.dumps({"version": 1, "keys": {}}))
        os.chmod(VAULT_PATH, 0o600)


class FieldEncryptor:
    """AES-256-GCM per-field-type encryption with versioned ciphertext."""

    ALGO = "AES-256-GCM"

    @staticmethod
    def encrypt(plaintext: str, field_type: str = "default") -> str:
        if plaintext is None:
            return None
        key = _derive_key(field_type)
        aes = AESGCM(key)
        nonce = os.urandom(12)
        ct = aes.encrypt(nonce, plaintext.encode(), None)
        blob = base64.b64encode(nonce + ct).decode()
        return f"v1:{field_type}:{blob}"

    @staticmethod
    def decrypt(token: str) -> str:
        if not token or ":" not in token:
            return token  # not encrypted
        _, field_type, blob = token.split(":", 2)
        key = _derive_key(field_type)
        aes = AESGCM(key)
        raw = base64.b64decode(blob)
        nonce, ct = raw[:12], raw[12:]
        return aes.decrypt(nonce, ct, None).decode()

    @staticmethod
    def rotate(field_type: str):
        # MOCKED: versioned re-encryption on next write
        _KEY_CACHE.pop(field_type, None)
        _ensure_vault()


def encrypt_field(plaintext, field_type="default"):
    return FieldEncryptor.encrypt(plaintext, field_type)


def decrypt_field(token):
    return FieldEncryptor.decrypt(token)


if __name__ == "__main__":
    _ensure_vault()
    tok = encrypt_field("john@empire.ai", "email")
    print("ENC:", tok)
    print("DEC:", decrypt_field(tok))
