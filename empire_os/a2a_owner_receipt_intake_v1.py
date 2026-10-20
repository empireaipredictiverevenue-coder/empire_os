"""Bounded owner receipt file intake without granting local write-based trust.

Trusted owner Ed25519 public keys must be installed by the A2A identity owner
in a root-owned file. Worktree-local receipts cannot establish their own trust.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
from typing import Any

from empire_os.a2a_owner_research_protocol_v1 import OWNERS, review_owner_receipts

KEY_CONFIG = Path("/etc/empire_ai_a2a_owner_public_keys_v1.json")
MAX_RECEIPTS = 20
_RECEIPT_FILE = re.compile(r"^(buyer_scout|community_intent)_[a-f0-9]{24}\.json$")


def trusted_owner_keys(path: Path = KEY_CONFIG) -> dict[str, bytes]:
    """Do not trust caller-controlled worktree files as an owner trust store."""
    if path.is_symlink() or not path.is_file():
        return {}
    stat = path.stat()
    if (stat.st_uid != 0 or stat.st_mode & 0o022
            or stat.st_size > 4096):
        raise ValueError("UNTRUSTED_OWNER_TRUST_STORE_PERMISSIONS")
    obj = json.loads(path.read_bytes())
    if not isinstance(obj, dict) or obj.get("schema_version") != "empire.a2a.trusted_owner_keys.v1":
        raise ValueError("INVALID_OWNER_TRUST_STORE_SCHEMA")
    rows = obj.get("trusted_owners")
    if not isinstance(rows, dict) or set(rows) - set(OWNERS):
        raise ValueError("UNKNOWN_OWNER_TRUST_BINDING")
    result: dict[str, bytes] = {}
    for owner, val in rows.items():
        if not isinstance(val, str) or not re.fullmatch(r"[A-Za-z0-9_-]{42,44}", val):
            raise ValueError("INVALID_OWNER_KEY_ENCODING")
        try:
            key = base64.urlsafe_b64decode(val + "=" * (-len(val) % 4))
        except (ValueError, TypeError):
            raise ValueError("OWNER_KEY_DECODE_FAILED") from None
        if len(key) != 32:
            raise ValueError("WRONG_OWNER_PUBLIC_KEY_SIZE")
        result[owner] = key
    return result


def load_candidate_receipts(folder: Path, *, max_receipts: int = MAX_RECEIPTS) -> list[dict[str, Any]]:
    if max_receipts != MAX_RECEIPTS:
        raise ValueError("FIXED_RECEIPT_LIMIT_REQUIRED")
    if folder.is_symlink():
        raise ValueError("UNSAFE_OWNER_RECEIPT_DIRECTORY")
    if not folder.is_dir():
        return []
    result = []
    entries = list(folder.iterdir())
    if len(entries) > MAX_RECEIPTS:
        raise ValueError("OWNER_RECEIPT_INBOX_LIMIT_EXCEEDED")
    for file in sorted(entries):
        if file.is_symlink() or not file.is_file() or not _RECEIPT_FILE.fullmatch(file.name):
            raise ValueError("UNSAFE_OWNER_RECEIPT_ENTRY")
        if file.stat().st_size > 16_384:
            raise ValueError("OWNER_RECEIPT_OVERSIZED")
        doc = json.loads(file.read_bytes())
        if not isinstance(doc, dict):
            raise ValueError("OWNER_RECEIPT_MUST_BE_OBJECT")
        if file.name != f'{doc.get("owner")}_{doc.get("ticket_id")}.json':
            raise ValueError("OWNER_RECEIPT_FILENAME_BINDING_FAILED")
        result.append(doc)
    return result


def inspect_owner_receipt_files(pickup: dict, folder: Path,
                                *, trusted_config: Path = KEY_CONFIG) -> dict:
    """Structured fail-closed readback; never auto-accept invalid trust config."""
    try:
        trust = trusted_owner_keys(trusted_config)
    except (OSError, ValueError, json.JSONDecodeError):
        trust = {}
        trust_status = "TRUST_STORE_INVALID_NEEDS_A2A_IDENTITY_OWNER"
    else:
        trust_status = ("OWNER_TRUSTED_PUBLIC_KEYS_CONFIGURED"
                        if trust else "NO_PRODUCTION_OWNER_PUBLIC_KEYS_CONFIGURED")
    try:
        receipts = load_candidate_receipts(folder)
    except (OSError, ValueError, json.JSONDecodeError):
        # Never count a malformed local file as authenticated.
        receipts = []
        receipt_input_state = "OWNER_RECEIPT_DIRECTORY_REJECTED"
    else:
        receipt_input_state = "OWNER_RECEIPTS_READ" if receipts else "NO_OWNER_RECEIPTS"
    review = review_owner_receipts(pickup, receipts, trust)
    review["trust_store_state"] = trust_status
    review["receipt_input_state"] = receipt_input_state
    review["received_receipt_file_count"] = len(receipts)
    review["verified_buyer_outcomes_from_untrusted_disk"] = 0
    return review
