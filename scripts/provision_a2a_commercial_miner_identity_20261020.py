#!/usr/bin/env python3
"""Explicit opt-in Ed25519 identity for the isolated A2A research miner.

This is LOCAL testing only; does not configure production gateway keys, DSNs,
a trust store, public endpoint, internal live dispatcher or payment authority.
Never prints private keys, seeds or signed payloads containing secrets.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from empire_os.a2a_identity import AgentIdentityClaim, InMemoryNonceRegistry, verify_agent_identity
from empire_os.a2a_commercial_signal_miner import AGENT_ID

KEY_DIR = Path("/home/ubuntu/.local/share/empire_ai_a2a_signal_miner_identity")
PRIVATE_KEY = KEY_DIR / "ed25519_private.key"
PUBLIC_RECEIPT = KEY_DIR / "research_identity_public.json"
KEY_ID = "empire-ai-commercial-signal-miner-research-local-v1"


def _b64(binary: bytes) -> str:
    return base64.urlsafe_b64encode(binary).decode("ascii").rstrip("=")


def _private_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _public_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _write_exclusive(path: Path, payload: bytes, mode: int) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def provision() -> dict:
    if KEY_DIR.is_symlink():
        raise ValueError("unsafe_identity_directory")
    KEY_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(KEY_DIR, 0o700)
    if PRIVATE_KEY.exists() or PRIVATE_KEY.is_symlink():
        raise ValueError("existing_key_refused_overwrite")
    if PUBLIC_RECEIPT.exists() or PUBLIC_RECEIPT.is_symlink():
        raise ValueError("existing_public_receipt_refused_overwrite")
    key = Ed25519PrivateKey.generate()
    public = _public_bytes(key)
    record = {
        "schema_version": "empire.a2a.local_research_identity.v1",
        "agent_id": AGENT_ID, "key_id": KEY_ID,
        "public_key_b64url": _b64(public),
        "public_key_sha256": sha256(public).hexdigest(),
        "provisioned_at": datetime.now(timezone.utc).isoformat(),
        "identity_scope": "research_signed_discovery_only",
        "production_a2a_gateway_registered": False,
        "external_trust_registered": False,
        "production_commerce_authority": False,
        "secret_storage": "local_0600_software_key_not_production_secrets_manager",
    }
    _write_exclusive(PRIVATE_KEY, _private_bytes(key), 0o600)
    _write_exclusive(PUBLIC_RECEIPT,
                     (json.dumps(record, sort_keys=True, indent=2) + "\n").encode(), 0o600)
    return record


def verify_local() -> dict:
    if (KEY_DIR.is_symlink() or PRIVATE_KEY.is_symlink()
            or PUBLIC_RECEIPT.is_symlink()):
        raise ValueError("unsafe_key_or_receipt_symlink")
    if not PRIVATE_KEY.is_file() or not PUBLIC_RECEIPT.is_file():
        raise ValueError("no_provisioned_research_identity")
    if PRIVATE_KEY.stat().st_mode & 0o077 or PUBLIC_RECEIPT.stat().st_mode & 0o077:
        raise ValueError("identity_material_permissions_unsafe")
    record = json.loads(PUBLIC_RECEIPT.read_text())
    if (record.get("agent_id") != AGENT_ID or record.get("key_id") != KEY_ID
            or record.get("schema_version") != "empire.a2a.local_research_identity.v1"):
        raise ValueError("identity_receipt_mismatch")
    key = Ed25519PrivateKey.from_private_bytes(PRIVATE_KEY.read_bytes())
    pub = _public_bytes(key)
    if record.get("public_key_sha256") != sha256(pub).hexdigest():
        raise ValueError("key_fingerprint_mismatch")
    now = datetime.now(timezone.utc)
    claim = AgentIdentityClaim(
        agent_id=AGENT_ID, key_id=KEY_ID,
        nonce=secrets.token_urlsafe(32), issued_at=now.isoformat(),
        requested_scope="discovery", signature="pending",
    )
    signature = _b64(key.sign(claim.signing_payload()))
    claim = AgentIdentityClaim(
        agent_id=AGENT_ID, key_id=KEY_ID, nonce=claim.nonce,
        issued_at=claim.issued_at, requested_scope="discovery",
        signature=signature,
    )
    registry = InMemoryNonceRegistry()
    def verifier(key_id: str, payload: bytes, sig: str) -> bool:
        if key_id != KEY_ID:
            return False
        try:
            raw = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
            key.public_key().verify(raw, payload)
            return True
        except Exception:
            return False
    accepted = verify_agent_identity(
        claim, verifier=verifier,
        trusted_key_ids={KEY_ID}, nonce_registry=registry, now=lambda: now,
    )
    replay = verify_agent_identity(
        claim, verifier=verifier,
        trusted_key_ids={KEY_ID}, nonce_registry=registry, now=lambda: now,
    )
    foreign = verify_agent_identity(
        claim, verifier=verifier,
        trusted_key_ids=set(), nonce_registry=InMemoryNonceRegistry(),
        now=lambda: now,
    )
    if (not accepted.authenticated or accepted.granted_scope != "discovery"
            or replay.authenticated or foreign.authenticated):
        raise RuntimeError("LOCAL_IDENTITY_HANDSHAKE_FAILED")
    return {
        "agent_id": AGENT_ID, "key_id": KEY_ID,
        "local_signature_valid": accepted.authenticated,
        "local_replay_rejected": not replay.authenticated,
        "untrusted_peer_key_rejected": not foreign.authenticated,
        "public_key_sha256": sha256(pub).hexdigest(),
        "external_registered": False,
        "production_verified_trust": False,
        "persistent_nonce_replay_protection": False,
        "commerce_execution_authority": "NONE",
        "private_key_printed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-only signed identity")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--provision-local", action="store_true")
    command.add_argument("--verify-local", action="store_true")
    args = parser.parse_args()
    result = provision() if args.provision_local else verify_local()
    if args.provision_local:
        result.pop("public_key_b64url", None)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
