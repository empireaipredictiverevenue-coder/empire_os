"""HMAC verification for inbound Recall.ai requests."""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from hashlib import sha256
import hmac
from typing import Any, Mapping


@dataclass(frozen=True)
class RecallVerificationEvidence:
    webhook_id: str
    webhook_timestamp: str
    signature_version: str
    payload_sha256: str
    verification_method: str = "recall_hmac_sha256"
    verified: bool = True
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def evidence_ref(self) -> str:
        return (
            "recall-verification:"
            f"{self.webhook_id}:{self.webhook_timestamp}:"
            f"{self.payload_sha256[:24]}"
        )


def _headers(headers: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(key).strip().lower(): str(value or "").strip()
        for key, value in headers.items()
    }


def verify_recall_request(
    *,
    secret: str,
    headers: Mapping[str, Any],
    raw_payload: bytes | str | None,
) -> RecallVerificationEvidence:
    clean_secret = str(secret or "").strip()
    if not clean_secret.startswith("whsec_"):
        raise ValueError("Recall verification secret missing or invalid")

    normalized = _headers(headers)
    webhook_id = normalized.get("webhook-id") or normalized.get("svix-id") or ""
    timestamp = (
        normalized.get("webhook-timestamp")
        or normalized.get("svix-timestamp")
        or ""
    )
    signatures = (
        normalized.get("webhook-signature")
        or normalized.get("svix-signature")
        or ""
    )
    if not webhook_id or not timestamp or not signatures:
        raise ValueError("Recall verification headers missing")
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise ValueError("Recall webhook timestamp invalid") from exc
    if timestamp_value <= 0:
        raise ValueError("Recall webhook timestamp invalid")

    if raw_payload is None:
        payload_bytes = b""
    elif isinstance(raw_payload, bytes):
        payload_bytes = raw_payload
    elif isinstance(raw_payload, str):
        payload_bytes = raw_payload.encode("utf-8")
    else:
        raise ValueError("raw_payload must be bytes, string, or null")


    encoded_key = clean_secret[len("whsec_") :]
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except Exception as exc:
        raise ValueError("Recall verification secret encoding invalid") from exc
    if not key:
        raise ValueError("Recall verification secret key empty")

    payload_text = payload_bytes.decode("utf-8")
    signed = f"{webhook_id}.{timestamp}.{payload_text}".encode("utf-8")
    expected = hmac.new(key, signed, sha256).digest()

    matched = False
    for versioned in signatures.split():
        if "," not in versioned:
            continue
        version, signature = versioned.split(",", 1)
        if version != "v1":
            continue
        try:
            provided = base64.b64decode(signature, validate=True)
        except Exception:
            continue
        if hmac.compare_digest(expected, provided):
            matched = True
            break

    if not matched:
        raise ValueError("Recall webhook signature verification failed")


    return RecallVerificationEvidence(
        webhook_id=webhook_id,
        webhook_timestamp=timestamp,
        signature_version="v1",
        payload_sha256=sha256(payload_bytes).hexdigest(),
    )
