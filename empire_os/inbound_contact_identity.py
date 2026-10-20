"""Pseudonymous tenant-scoped contact key generation, no persistence."""
from __future__ import annotations

import hashlib
import hmac
import re


def pseudonymise_inbound_contact(
    phone_e164: str,
    *,
    tenant_id: str,
    signing_key: str,
) -> str:
    """HMAC-SHA256 of tenant and E.164 phone, never return the phone.

    Not anonymisation: reversible through dictionary attacks if the secret
    leaks. Keep the key server-side, rotated and separately protected.
    """
    if not isinstance(phone_e164, str) or not re.fullmatch(r"\+[1-9][0-9]{6,14}", phone_e164):
        raise ValueError("valid_e164_phone_required")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id_required")
    if not isinstance(signing_key, str) or len(signing_key.encode("utf-8")) < 32:
        raise ValueError("contact_pseudonym_key_not_configured")
    payload = f"{tenant_id}\x00{phone_e164}".encode("utf-8")
    return hmac.new(signing_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
