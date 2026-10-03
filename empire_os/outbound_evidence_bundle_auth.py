"""Integrity/authenticity helpers for local Ringleader evidence bundles."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping


def canonical_bundle_payload(bundle: Mapping[str, Any]) -> bytes:
    payload = {
        "schema_version": bundle.get("schema_version"),
        "generated_at": bundle.get("generated_at"),
        "sources": bundle.get("sources") or {},
        "mutation_authorized": False,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def sign_evidence_bundle(
    bundle: Mapping[str, Any],
    *,
    key: str,
) -> dict[str, Any]:
    secret = str(key or "")
    if len(secret) < 16:
        raise ValueError("evidence_bundle_hmac_key_too_short")

    result = dict(bundle)
    result["mutation_authorized"] = False
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical_bundle_payload(result),
        hashlib.sha256,
    ).hexdigest()
    result["signature"] = {
        "algorithm": "hmac-sha256",
        "digest": digest,
    }
    return result


def verify_evidence_bundle_signature(
    bundle: Mapping[str, Any],
    *,
    key: str,
) -> bool:
    secret = str(key or "")
    if len(secret) < 16:
        return False

    signature = bundle.get("signature")
    if not isinstance(signature, Mapping):
        return False
    if str(signature.get("algorithm") or "") != "hmac-sha256":
        return False

    supplied = str(signature.get("digest") or "").lower()
    if len(supplied) != 64:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        canonical_bundle_payload(bundle),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied, expected)
