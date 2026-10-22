"""Root-custodied Ed25519 PRIVATE KEY contract for EXISTING EmpireOS Agent OS.

NOT installed into the live privileged helper. No key is provisioned by
importing or running this source. No socket, registry, queue or send action.

Use root-only custody rather than storing secrets under the shared
`ubuntu` UID. Signing here is deliberately domain-separated from the
DepartmentCollaboration A2A envelope until independently approved.
"""
from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

# A future trusted root release must pin this directory and never let the
# socket caller choose any path, profile, signer ID or key material.
ROOT_SIGNING_DIRECTORY = Path("/var/lib/empire-ai/agent-os-signing")
PINNED_CODER_KEY = "empire_coder.ed25519"
CODER_UNIT = "empire-coder-worker.service"
CODER_AGENT = "empire_coder"
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,96}$")
ROOT_ORIGIN_DOMAIN = b"empire.agent-os.root-origin-observe.v1:"


class RootSigningCustodyDenied(ValueError):
    pass


@dataclass(frozen=True)
class RootCustodyReceipt:
    """Values only the future ROOT helper may source from the kernel.

    Constructing this object is not proof of root attestation; this module
    is not yet connected to the existing kernel-origin checked entrypoint.
    """
    agent_id: str
    unit: str
    process_pid: int
    process_origin_verified: bool
    tenant_scope: str = "unbound"


def _safe_private_key_read(
    directory: Path,
    *,
    expected_owner_uid: int,
) -> Ed25519PrivateKey:
    """Read exactly one key via root-owned dirfd; never follow symlinks.

    expected_owner_uid=0 is mandatory for the public root interface.
    An injected value is solely for synthetic temporary tests.
    """
    if directory != ROOT_SIGNING_DIRECTORY and expected_owner_uid == 0:
        raise RootSigningCustodyDenied("unapproved_root_key_directory")
    if not directory.is_absolute():
        raise RootSigningCustodyDenied("absolute_root_custody_path_required")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_DIRECTORY
    try:
        dirfd = os.open(directory, flags)
    except OSError as exc:
        raise RootSigningCustodyDenied("protected_signing_directory_unavailable") from exc
    try:
        s = os.fstat(dirfd)
        if (
            not stat.S_ISDIR(s.st_mode) or s.st_uid != expected_owner_uid
            or stat.S_IMODE(s.st_mode) != 0o700
        ):
            raise RootSigningCustodyDenied("protected_signing_directory_not_private")
        try:
            fd = os.open(
                PINNED_CODER_KEY,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=dirfd,
            )
        except OSError as exc:
            raise RootSigningCustodyDenied("protected_signing_key_unavailable") from exc
        try:
            f = os.fstat(fd)
            if (
                not stat.S_ISREG(f.st_mode)
                or f.st_uid != expected_owner_uid
                or stat.S_IMODE(f.st_mode) not in (0o400, 0o600)
                or f.st_nlink != 1
                or f.st_size != 32
            ):
                raise RootSigningCustodyDenied("protected_signing_key_not_private")
            raw = os.read(fd, 33)
            if len(raw) != 32:
                raise RootSigningCustodyDenied("protected_signing_key_invalid_length")
            return Ed25519PrivateKey.from_private_bytes(raw)
        finally:
            os.close(fd)
    finally:
        os.close(dirfd)


def _root_only_private_key() -> Ed25519PrivateKey:
    """No client-defined key path. Cannot run from a shared-UID worker."""
    if os.geteuid() != 0:
        raise RootSigningCustodyDenied("root_helper_custody_required")
    return _safe_private_key_read(
        ROOT_SIGNING_DIRECTORY, expected_owner_uid=0,
    )


def _observation(
    origin: RootCustodyReceipt, *,
    nonce: str,
    issued_at: datetime,
) -> dict[str, object]:
    if (
        type(origin) is not RootCustodyReceipt
        or origin.agent_id != CODER_AGENT
        or origin.unit != CODER_UNIT
        or type(origin.process_pid) is not int or origin.process_pid <= 1
        or origin.process_origin_verified is not True
        or origin.tenant_scope != "unbound"
        or not isinstance(nonce, str) or NONCE_RE.fullmatch(nonce) is None
        or not isinstance(issued_at, datetime)
        or issued_at.tzinfo is None or issued_at.utcoffset() is None
    ):
        raise RootSigningCustodyDenied("untrusted_origin_scope")
    now = issued_at.astimezone(timezone.utc)
    return {
        "schema_version": "empire.agent-os.root-origin-observe.v1",
        "agent_id": CODER_AGENT,
        "unit": CODER_UNIT,
        "pid": origin.process_pid,
        "scope": "ROOT_ATTESTED_PROCESS_OBSERVATION_ONLY",
        "tenant_scope": "unbound",
        "nonce": nonce,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=60)).isoformat(),
        "trusted_collaboration_registration": False,
        "message_transport_activated": False,
        "queue_authority": False,
        "execution_authority": "none",
    }


def _canonical_observation_bytes(payload: Mapping[str, Any]) -> bytes:
    return ROOT_ORIGIN_DOMAIN + json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def _create_observe_only_receipt(
    origin: RootCustodyReceipt, *,
    nonce: str, issued_at: datetime, private_key: Ed25519PrivateKey,
) -> dict[str, object]:
    """Internal test/proposal helper. No collaboration signature created."""
    payload = _observation(origin, nonce=nonce, issued_at=issued_at)
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "payload": payload,
        "signature_hex": private_key.sign(_canonical_observation_bytes(payload)).hex(),
        "public_key_hex": public.hex(),
        "key_issued": False,
        "trusted_collaboration_registration": False,
        "no_live_a2a_message_signed": True,
        "root_observation_only": True,
    }


def create_root_origin_observation(
    origin: RootCustodyReceipt, *,
    nonce: str,
    issued_at: datetime,
) -> dict[str, object]:
    """Potential root-helper-only hook; MUST NOT expose until owner approval.

    Future helper must obtain origin from attested peer, not client JSON.
    """
    _observation(origin, nonce=nonce, issued_at=issued_at)
    private_key = _root_only_private_key()
    return _create_observe_only_receipt(
        origin, nonce=nonce, issued_at=issued_at, private_key=private_key,
    )


def verify_pinned_root_origin_observation(
    receipt: Mapping[str, Any],
    *,
    trusted_public_key: object,
    now: datetime,
) -> dict[str, object]:
    """Public-only, read-only verifier; never trust the receipt's own key.

    A separately root-enrolled/pinned public key is REQUIRED. Verification
    establishes a *historic signed event*, NOT an active A2A credential.
    Fresh nonce replay decisions require a future privileged atomic ledger.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if (
        not isinstance(receipt, Mapping)
        or set(receipt) != {
            "payload", "signature_hex", "public_key_hex", "key_issued",
            "trusted_collaboration_registration", "no_live_a2a_message_signed",
            "root_observation_only",
        }
        or not isinstance(trusted_public_key, Ed25519PublicKey)
        or not isinstance(now, datetime) or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise RootSigningCustodyDenied("trusted_public_origin_review_required")
    payload = receipt["payload"]
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {
            "schema_version", "agent_id", "unit", "pid", "scope",
            "tenant_scope", "nonce", "issued_at", "expires_at",
            "trusted_collaboration_registration",
            "message_transport_activated", "queue_authority",
            "execution_authority",
        }
        or payload["schema_version"] != "empire.agent-os.root-origin-observe.v1"
        or payload["agent_id"] != CODER_AGENT
        or payload["unit"] != CODER_UNIT
        or type(payload["pid"]) is not int or payload["pid"] <= 1
        or payload["scope"] != "ROOT_ATTESTED_PROCESS_OBSERVATION_ONLY"
        or payload["tenant_scope"] != "unbound"
        or not isinstance(payload["nonce"], str)
        or NONCE_RE.fullmatch(payload["nonce"]) is None
        or payload["trusted_collaboration_registration"] is not False
        or payload["message_transport_activated"] is not False
        or payload["queue_authority"] is not False
        or payload["execution_authority"] != "none"
        or receipt["key_issued"] is not False
        or receipt["trusted_collaboration_registration"] is not False
        or receipt["no_live_a2a_message_signed"] is not True
        or receipt["root_observation_only"] is not True
    ):
        raise RootSigningCustodyDenied("untrusted_root_origin_receipt_shape")
    try:
        issued = datetime.fromisoformat(payload["issued_at"])
        expires = datetime.fromisoformat(payload["expires_at"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise RootSigningCustodyDenied("invalid_root_origin_timestamp") from exc
    if (
        issued.tzinfo is None or expires.tzinfo is None
        or issued.utcoffset() is None or expires.utcoffset() is None
        or expires - issued != timedelta(seconds=60)
        or issued.astimezone(timezone.utc) > now.astimezone(timezone.utc)
        or expires.astimezone(timezone.utc) <= now.astimezone(timezone.utc)
    ):
        raise RootSigningCustodyDenied("expired_or_future_root_origin_receipt")
    public = trusted_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    try:
        public_hex, sig_hex = receipt["public_key_hex"], receipt["signature_hex"]
        if (
            not isinstance(public_hex, str) or not isinstance(sig_hex, str)
            or len(public_hex) != 64 or len(sig_hex) != 128
            or bytes.fromhex(public_hex) != public
        ):
            raise RootSigningCustodyDenied("public_signer_registry_mismatch")
        trusted_public_key.verify(
            bytes.fromhex(sig_hex), _canonical_observation_bytes(payload),
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise RootSigningCustodyDenied("invalid_pinned_root_origin_signature") from exc
    return {
        "root_origin_signature_verified": True,
        "historical_observation_only": True,
        "agent_id": CODER_AGENT,
        "pid": payload["pid"],
        "registered_agent": False,
        "message_transport_activated": False,
        "nonce_replay_ledger_active": False,
        "execution_authority": "none",
    }
