import pytest

from empire_os.a2a_identity_transport import (
    A2AIdentityTransportError,
    PostgresA2AIdentityNonceRpc,
    RpcNonceRegistry,
)


def test_rpc_nonce_registry_maps_single_allowed_rpc():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return True

    registry = RpcNonceRegistry(rpc)
    assert registry.consume(
        agent_id="agent-1",
        key_id="key-1",
        nonce="nonce-1",
        issued_at="2026-09-19T20:29:00+00:00",
    ) is True
    assert calls == [
        (
            "consume_a2a_identity_nonce",
            {
                "p_agent_id": "agent-1",
                "p_key_id": "key-1",
                "p_nonce": "nonce-1",
                "p_issued_at": "2026-09-19T20:29:00+00:00",
            },
        )
    ]


def test_rpc_nonce_registry_rejects_non_boolean_result():
    registry = RpcNonceRegistry(lambda name, params: {"ok": True})
    with pytest.raises(
        A2AIdentityTransportError,
        match="non-boolean",
    ):
        registry.consume(
            agent_id="a",
            key_id="k",
            nonce="n",
            issued_at="2026-09-19T20:29:00+00:00",
        )


def test_postgres_nonce_transport_rejects_other_rpc_before_connect():
    rpc = PostgresA2AIdentityNonceRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        A2AIdentityTransportError,
        match="cannot execute",
    ):
        rpc("approve_a2a_commercial_intent", {})


def test_postgres_nonce_transport_validates_parameter_contract():
    rpc = PostgresA2AIdentityNonceRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        A2AIdentityTransportError,
        match="unexpected",
    ):
        rpc(
            "consume_a2a_identity_nonce",
            {"p_agent_id": "a"},
        )
