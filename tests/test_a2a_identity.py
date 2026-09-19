from datetime import datetime, timezone

import pytest

from empire_os.a2a_identity import (
    AgentIdentityClaim,
    InMemoryNonceRegistry,
    verify_agent_identity,
)


NOW = datetime(2026, 9, 19, 20, 30, tzinfo=timezone.utc)


def claim(scope="discovery", nonce="nonce-1", issued_at="2026-09-19T20:29:00+00:00"):
    return AgentIdentityClaim(
        agent_id="agent-buyer-1",
        key_id="key-1",
        nonce=nonce,
        issued_at=issued_at,
        signature="sig-1",
        requested_scope=scope,
    )


def verify(c, *, registry=None, verifier=None, trusted=None):
    return verify_agent_identity(
        c,
        verifier=verifier or (lambda *args: True),
        trusted_key_ids=trusted or {"key-1"},
        nonce_registry=registry or InMemoryNonceRegistry(),
        now=lambda: NOW,
    )


def test_trusted_valid_signature_grants_discovery_only():
    decision = verify(
        claim(),
        verifier=lambda key_id, payload, signature: (
            key_id == "key-1"
            and signature == "sig-1"
            and b"discovery" in payload
        ),
    )
    assert decision.authenticated is True
    assert decision.agent_id == "agent-buyer-1"
    assert decision.granted_scope == "discovery"
    assert decision.execution_authority == "none"


def test_untrusted_key_fails_closed_before_verifier():
    called = False

    def verifier(key_id, payload, signature):
        nonlocal called
        called = True
        return True

    decision = verify(
        claim(),
        verifier=verifier,
        trusted={"another-key"},
    )
    assert decision.authenticated is False
    assert decision.reason == "untrusted_key_id"
    assert called is False


def test_invalid_signature_fails_closed():
    decision = verify(claim(), verifier=lambda *args: False)
    assert decision.authenticated is False
    assert decision.granted_scope is None
    assert decision.reason == "signature_invalid"


def test_expired_claim_fails_before_signature():
    called = False

    def verifier(*args):
        nonlocal called
        called = True
        return True

    decision = verify(
        claim(issued_at="2026-09-19T20:20:00+00:00"),
        verifier=verifier,
    )
    assert decision.authenticated is False
    assert decision.reason == "claim_expired"
    assert called is False


def test_claim_too_far_in_future_fails():
    decision = verify(
        claim(issued_at="2026-09-19T20:32:00+00:00"),
    )
    assert decision.authenticated is False
    assert decision.reason == "claim_from_future"


def test_issued_at_requires_timezone():
    with pytest.raises(ValueError, match="include timezone"):
        verify(claim(issued_at="2026-09-19T20:29:00"))


def test_nonce_replay_fails_after_first_valid_claim():
    registry = InMemoryNonceRegistry()
    first = verify(claim(), registry=registry)
    second = verify(claim(), registry=registry)
    assert first.authenticated is True
    assert second.authenticated is False
    assert second.reason == "nonce_replayed"


def test_commerce_intent_scope_authenticates_without_execution_authority():
    decision = verify(
        claim("commerce.intent"),
        verifier=lambda key_id, payload, signature: (
            key_id == "key-1"
            and signature == "sig-1"
            and b"commerce.intent" in payload
        ),
    )
    assert decision.authenticated is True
    assert decision.granted_scope == "commerce.intent"
    assert decision.reason == "authenticated_commerce_intent_only"
    assert decision.execution_authority == "none"


def test_commercial_execution_scope_is_not_supported():
    with pytest.raises(
        ValueError,
        match="only discovery and commerce.intent scopes",
    ):
        verify(claim("commerce.execute"))


def test_nonce_registry_failure_is_distinct_from_replay():
    class BrokenRegistry:
        def consume(self, **kwargs):
            raise RuntimeError("database unavailable")

    decision = verify_agent_identity(
        claim(),
        verifier=lambda *args: True,
        trusted_key_ids={"key-1"},
        nonce_registry=BrokenRegistry(),
        now=lambda: NOW,
    )
    assert decision.authenticated is False
    assert decision.reason == "nonce_registry_unavailable"
