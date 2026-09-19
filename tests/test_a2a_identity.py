import pytest

from empire_os.a2a_identity import (
    AgentIdentityClaim,
    verify_agent_identity,
)


def claim(scope="discovery"):
    return AgentIdentityClaim(
        agent_id="agent-buyer-1",
        key_id="key-1",
        nonce="nonce-1",
        issued_at="2026-09-19T22:40:00+00:00",
        signature="sig-1",
        requested_scope=scope,
    )


def test_trusted_valid_signature_grants_discovery_only():
    decision = verify_agent_identity(
        claim(),
        verifier=lambda key_id, payload, signature: (
            key_id == "key-1"
            and signature == "sig-1"
            and b"discovery" in payload
        ),
        trusted_key_ids={"key-1"},
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

    decision = verify_agent_identity(
        claim(),
        verifier=verifier,
        trusted_key_ids={"another-key"},
    )
    assert decision.authenticated is False
    assert decision.reason == "untrusted_key_id"
    assert called is False


def test_invalid_signature_fails_closed():
    decision = verify_agent_identity(
        claim(),
        verifier=lambda *args: False,
        trusted_key_ids={"key-1"},
    )
    assert decision.authenticated is False
    assert decision.granted_scope is None
    assert decision.reason == "signature_invalid"


def test_verifier_exception_fails_closed():
    def broken(*args):
        raise RuntimeError("verification unavailable")

    decision = verify_agent_identity(
        claim(),
        verifier=broken,
        trusted_key_ids={"key-1"},
    )
    assert decision.authenticated is False
    assert decision.reason == "signature_invalid"


def test_commercial_scope_is_not_supported():
    with pytest.raises(ValueError, match="only discovery scope"):
        verify_agent_identity(
            claim("commerce.execute"),
            verifier=lambda *args: True,
            trusted_key_ids={"key-1"},
        )
