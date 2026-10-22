"""Opt-in, one-shot Ed25519 provenance observation INSIDE existing Coder.

No persistent private key, credential issuer, broker registration, trust
grant, extra task claim or model execution. An untrusted self-issued public
key cannot authorize peer messages; this is solely an internal observation.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

from empire_os.agent_runtime_identity_evidence import (
    ManagedWorkerSigningIdentity,
    preflight_local_managed_binding,
)
from empire_os.department_collaboration import existing_role_profile

SCHEMA = "empire.agents.managed_coder_identity_observe.v1"
AGENT_ID = "empire_coder"


def inspect_actual_coder_signing_process() -> dict[str, Any]:
    """Run in the Coder systemd ExecStart main process, never a sibling.

    The ephemeral private key is not serialised, returned, saved, or shared.
    The output is publicly verifiable self-signed *evidence*, not permission.
    """
    profile = existing_role_profile(
        agent_id=AGENT_ID,
        department="engineering",
        role="coder",
        capabilities=("empire_coder",),
    )
    signer = ManagedWorkerSigningIdentity(profile, Ed25519PrivateKey.generate())
    attested = preflight_local_managed_binding(
        signer, agent_id=AGENT_ID,
    )  # no faked PID/OS callback; actual running kernel process only
    if (
        attested.get("local_process_scope_attested") is not True
        or attested.get("trusted_broker_key_registration_still_required") is not True
        or attested.get("signing_mode") != "ed25519_private_in_managed_process"
    ):
        raise ValueError("managed_process_identity_not_attested")
    payload = {
        "schema_version": SCHEMA,
        "agent_id": AGENT_ID,
        "unit": "empire-coder-worker.service",
        "pid": os.getpid(),
        "scope": "PROCESS_LOCAL_OBSERVE_ONLY",
        "nonce": secrets.token_urlsafe(24),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "privileged_action": False,
    }
    public_bytes = signer.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    receipt = {
        "payload": payload,
        "signature_hex": signer.sign(payload),
        "public_key_hex": public_bytes.hex(),
        "kernel_cgroup_uid_pid_checked_locally": True,
        "trusted_broker_registration": False,
        "persistent_agent_credential": False,
        "production_collaboration_activated": False,
        "external_outbound": False,
        "payment_authority": "none",
    }
    if not verify_untrusted_signing_receipt(receipt):
        raise ValueError("self_signature_verification_failed")
    return receipt


def verify_untrusted_signing_receipt(receipt: object) -> bool:
    """Verify shape and signature. Cannot authenticate an unpinned key."""
    if not isinstance(receipt, dict) or set(receipt) != {
        "payload", "signature_hex", "public_key_hex",
        "kernel_cgroup_uid_pid_checked_locally",
        "trusted_broker_registration", "persistent_agent_credential",
        "production_collaboration_activated", "external_outbound",
        "payment_authority",
    }:
        return False
    payload = receipt.get("payload")
    if (
        not isinstance(payload, dict)
        or set(payload) != {
            "schema_version", "agent_id", "unit", "pid", "scope",
            "nonce", "timestamp_utc", "privileged_action",
        }
        or payload.get("schema_version") != SCHEMA
        or payload.get("agent_id") != AGENT_ID
        or payload.get("unit") != "empire-coder-worker.service"
        or type(payload.get("pid")) is not int or payload["pid"] <= 0
        or payload.get("scope") != "PROCESS_LOCAL_OBSERVE_ONLY"
        or type(payload.get("nonce")) is not str
        or not 18 <= len(payload["nonce"]) <= 128
        or type(payload.get("timestamp_utc")) is not str
        or payload.get("privileged_action") is not False
        or receipt.get("kernel_cgroup_uid_pid_checked_locally") is not True
        or receipt.get("trusted_broker_registration") is not False
        or receipt.get("persistent_agent_credential") is not False
        or receipt.get("production_collaboration_activated") is not False
        or receipt.get("external_outbound") is not False
        or receipt.get("payment_authority") != "none"
    ):
        return False
    try:
        public_hex, signature_hex = receipt["public_key_hex"], receipt["signature_hex"]
        if (
            not isinstance(public_hex, str)
            or not isinstance(signature_hex, str)
            or len(public_hex) != 64 or len(signature_hex) != 128
        ):
            return False
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
        signature = bytes.fromhex(signature_hex)
        public.verify(
            signature,
            json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True).encode(),
        )
    except (ValueError, TypeError, InvalidSignature):
        return False
    return True
