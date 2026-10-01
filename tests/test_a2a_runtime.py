from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.a2a_discovery import commerce_discovery_manifest
from empire_os.a2a_runtime import (
    IDENTITY_DSN_ENV,
    INTENT_DSN_ENV,
    KEYS_ENV,
    load_a2a_runtime,
)


def configured_env():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, {
        KEYS_ENV: json.dumps({"agent-key-1": base64.b64encode(public).decode()}),
        IDENTITY_DSN_ENV: "postgresql://identity",
        INTENT_DSN_ENV: "postgresql://intent",
    }


def test_missing_config_fails_closed():
    runtime = load_a2a_runtime({})
    assert runtime.configured is False
    assert runtime.authentication_status == "not_activated"
    assert "trusted_ed25519_keys_missing" in runtime.blockers
    assert "identity_dsn_missing" in runtime.blockers
    assert "intent_dsn_missing" in runtime.blockers
    assert runtime.verifier is None
    assert runtime.repository is None
    assert runtime.nonce_registry is None


def test_valid_ed25519_config_builds_governed_runtime():
    private, env = configured_env()
    runtime = load_a2a_runtime(env)
    assert runtime.configured is True
    assert runtime.authentication_status == "configured_unverified"
    assert runtime.blockers == ()
    assert runtime.trusted_key_ids == frozenset({"agent-key-1"})

    payload = b"agent\nagent-key-1\nnonce\n2026-10-01T12:00:00Z\ncommerce.intent"
    signature = base64.b64encode(private.sign(payload)).decode()
    assert runtime.verifier is not None
    assert runtime.verifier("agent-key-1", payload, signature) is True
    assert runtime.verifier("wrong-key", payload, signature) is False


def test_invalid_key_material_never_activates():
    runtime = load_a2a_runtime({
        KEYS_ENV: json.dumps({"k1": "not-base64!!"}),
        IDENTITY_DSN_ENV: "postgresql://identity",
        INTENT_DSN_ENV: "postgresql://intent",
    })
    assert runtime.configured is False
    assert "trusted_ed25519_keys_invalid" in runtime.blockers


def test_discovery_reports_runtime_status_without_execution_authority():
    manifest = commerce_discovery_manifest(
        public_base_url="https://empire-ai.co.uk",
        public_capability_names=["market.lookup"],
        authentication_status="configured_unverified",
    )
    commercial = manifest["commercial_discovery"]
    assert commercial["authentication_status"] == "configured_unverified"
    assert manifest["privileged_actions_exposed"] is False
    assert manifest["payments_exposed"] is False
    assert manifest["allocations_exposed"] is False


def test_live_verified_config_reports_activated():
    _, env = configured_env()
    env["EMPIRE_A2A_LIVE_VERIFIED"] = "true"
    runtime = load_a2a_runtime(env)
    assert runtime.configured is True
    assert runtime.authentication_status == "activated"
    assert runtime.public_status()["execution_authority"] == "none"
