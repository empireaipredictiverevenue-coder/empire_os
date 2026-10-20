"""Private, dependency-injected consumer opt-in service; never installed live.

Real AEAD encryption, keyed lookup, CSPRNG link tokens and purpose-isolated
receipts. Transactions and provider receipts are owned by injected private
repository and verified sender. There are no default connectors, credentials,
network routes, environment flags or production activation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from empire_os.consumer_optin_token_security import (
    canonical_email, email_lookup_hmac, issue_token, token_fingerprint,
)

NOTICE = "roofing-homeowner-updates-v1"
PURPOSE = "empire_own_brand_homeowner_updates"
ORIGIN = "https://empire-ai.co.uk"
URL = ORIGIN + "/roofing/email-preferences"
ENCRYPTION_CONTEXT = b"empire.consumer.roofing.private_email.v1|own_brand"


@dataclass(frozen=True)
class Keys:
    email_hmac: bytes
    token_hmac: bytes
    email_encryption: bytes
    email_key_reference: str

    def validate(self) -> None:
        for key in (self.email_hmac, self.token_hmac, self.email_encryption):
            if not isinstance(key, bytes) or len(key) != 32:
                raise ValueError("three 256-bit private keys required")
        if len({self.email_hmac, self.token_hmac, self.email_encryption}) != 3:
            raise ValueError("purpose-separated keys must differ")
        if not self.email_key_reference.startswith("consumer-key-v"):
            raise ValueError("approved nonsecret key reference required")


def encrypt_email(email: str, *, keys: Keys, nonce: bytes) -> bytes:
    """Nonce must be unique per encryption; in service it is CSPRNG generated."""
    keys.validate()
    if len(nonce) != 12:
        raise ValueError("GCM nonce must have 96 bits")
    return nonce + AESGCM(keys.email_encryption).encrypt(
        nonce, canonical_email(email).encode("ascii"), ENCRYPTION_CONTEXT
    )


def decrypt_email(data: bytes, *, keys: Keys) -> str:
    keys.validate()
    if not isinstance(data, bytes) or len(data) < 12 + 16 + 6:
        raise ValueError("invalid ciphertext")
    return AESGCM(keys.email_encryption).decrypt(
        data[:12], data[12:], ENCRYPTION_CONTEXT
    ).decode("ascii")


class PrivateStore(Protocol):
    def signup_writable(self) -> bool: ...
    def token_processing_writable(self) -> bool: ...
    def begin_pending(
        self, *, lookup: str, ciphertext: bytes, key_ref: str,
        capture_digest: str, confirm_hmac: str, confirm_expires: datetime,
        unsubscribe_hmac: str, unsubscribe_expires: datetime,
    ) -> bool: ...
    def claim_confirmation_send(self, *, lookup: str, confirm_hmac: str) -> bool: ...
    def record_confirmation_delivery(self, *, lookup: str,
                                     confirm_hmac: str, provider_receipt: str) -> bool: ...
    def consume_once(self, *, token_hmac: str, action: str,
                     checked_at: datetime) -> bool: ...


class PrivateConfirmationSender(Protocol):
    def provider_ready(self) -> bool: ...
    def send_verification(self, *, recipient: str, confirm_link: str,
                          unsubscribe_link: str) -> str | None: ...


class PrivateConsumerOptinService:
    """Implements the private API Protocol, with no live wiring by default."""

    def __init__(self, *, keys: Keys, store: PrivateStore,
                 sender: PrivateConfirmationSender,
                 clock: Callable[[], datetime] | None = None,
                 nonce_source: Callable[[int], bytes] | None = None):
        keys.validate()
        self._keys = keys
        self._store = store
        self._sender = sender
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if nonce_source is None:
            from secrets import token_bytes
            nonce_source = token_bytes
        self._nonce_source = nonce_source

    def independently_ready(self) -> bool:
        try:
            return (self._store.signup_writable() is True and
                    self._sender.provider_ready() is True and
                    self._store.token_processing_writable() is True)
        except Exception:
            return False

    def can_service_confirmations(self) -> bool:
        try:
            return self._store.token_processing_writable() is True
        except Exception:
            return False

    def can_service_withdrawals(self) -> bool:
        # This does NOT depend on the confirmation sender or signup availability.
        return self.can_service_confirmations()

    def request_verification(self, *, email: str, notice_version: str,
                             consent_receipt: dict[str, str]) -> bool:
        if not self.independently_ready() or notice_version != NOTICE:
            return False
        if (not isinstance(consent_receipt, dict)
            or consent_receipt.get("offer_slug") != "roofing-cost-guide"
            or consent_receipt.get("source") != "EMPIRE_OWNED_PUBLIC_ROOFING_GUIDE"
            or consent_receipt.get("notice_version") != NOTICE
            or consent_receipt.get("own_brand_updates") != "explicit_true"
            or consent_receipt.get("third_party_buyer_sharing") != "explicit_false"):
            return False

        address = canonical_email(email)
        now = self._clock()
        confirm = issue_token(action="confirm", key=self._keys.token_hmac,
                              now=now, ttl=timedelta(hours=2))
        unsubscribe = issue_token(action="unsubscribe", key=self._keys.token_hmac,
                                  now=now, ttl=timedelta(days=30))
        nonce = self._nonce_source(12)
        encrypted = encrypt_email(address, keys=self._keys, nonce=nonce)
        lookup = email_lookup_hmac(address, key=self._keys.email_hmac)

        # Hash *only the consent document*, never a raw address or a bearer
        # secret in an evidence field; names/IPs/IDs are excluded.
        canonical = json.dumps({
            "original_choice": consent_receipt,
            "lookup": lookup,
            "captured_at": now.isoformat(),
            "unique_request_hmac": confirm.token_hmac,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        capture = hmac.new(self._keys.email_hmac,
                           b"empire.consumer.roofing.original_choice.v1|" + canonical,
                           hashlib.sha256).hexdigest()

        saved = self._store.begin_pending(
            lookup=lookup, ciphertext=encrypted,
            key_ref=self._keys.email_key_reference,
            capture_digest=capture,
            confirm_hmac=confirm.token_hmac,
            confirm_expires=confirm.expires_at,
            unsubscribe_hmac=unsubscribe.token_hmac,
            unsubscribe_expires=unsubscribe.expires_at,
        )
        if saved is not True:
            # Suppression, already-verified, duplicate or owner hold: never send.
            return False
        # An independent transaction checks current suppression and claims the
        # exact confirmation token once, immediately before provider delivery.
        # The email owner must also recheck suppression at its send boundary.
        if self._store.claim_confirmation_send(
            lookup=lookup, confirm_hmac=confirm.token_hmac
        ) is not True:
            return False
        try:
            provider_receipt = self._sender.send_verification(
                recipient=address,
                confirm_link=URL + "#confirm=" + confirm.token,
                unsubscribe_link=URL + "#unsubscribe=" + unsubscribe.token,
            )
        except Exception:
            return False
        if not isinstance(provider_receipt, str) or not provider_receipt.strip():
            return False
        receipt_hmac = hmac.new(
            self._keys.token_hmac,
            b"empire.consumer.provider_verification_receipt.v1|" +
            provider_receipt.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return self._store.record_confirmation_delivery(
            lookup=lookup, confirm_hmac=confirm.token_hmac,
            provider_receipt=receipt_hmac,
        ) is True

    def confirm_with_token(self, *, token: str) -> None:
        if not self.can_service_confirmations():
            raise RuntimeError("consumer confirmation service unavailable")
        # The repository MUST use a DB row lock, consume the token exactly
        # once and check current suppression inside the same transaction.
        self._store.consume_once(
            token_hmac=token_fingerprint(token, action="confirm",
                                         key=self._keys.token_hmac),
            action="confirm", checked_at=self._clock(),
        )

    def withdraw_with_token(self, *, token: str) -> None:
        if not self.can_service_withdrawals():
            raise RuntimeError("consumer withdrawal service unavailable")
        self._store.consume_once(
            token_hmac=token_fingerprint(token, action="unsubscribe",
                                         key=self._keys.token_hmac),
            action="unsubscribe", checked_at=self._clock(),
        )
