"""Public-key-only validation of existing governed A2A protocol."""
from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.department_collaboration import (
    AgentPublicCredential, CollaborationDenied, DepartmentCollaboration,
    existing_role_profile, _canonical,
)
from empire_os.department_work_queue import DepartmentWorkQueue
from scripts.run_agent_collaboration_canary_20261022 import run_isolated_canary


def setup_public_actor(root):
    private = Ed25519PrivateKey.generate()
    agent = "research_role_one"
    credentials = {
        agent: AgentPublicCredential(existing_role_profile(
            agent_id=agent,
            department="market_intelligence", role="research",
            capabilities=("intelligence_fabric",),
        ), private.public_key())
    }
    queue = DepartmentWorkQueue(root)
    item, created = queue.enqueue_step(
        plan_id="ed_canary",
        step={
            "step_id": "review1",
            "goal_key": "test",
            "department_keys": ["market_intelligence"],
            "target_component": "intelligence_fabric",
            "authority": "observe",
            "action": "offline_read_only",
        },
    )
    assert created
    return private, agent, item, queue, DepartmentCollaboration(root, credentials)


def signed(private, envelope):
    return private.sign(_canonical(envelope)).hex()


def test_true_public_key_only_pickup_no_private_key_in_bus(tmp_path):
    private, agent, item, queue, bus = setup_public_actor(tmp_path)
    env = {"op": "pickup", "agent_id": agent, "nonce": "long_nonce_abcdefg123"}
    result = bus.pickup(env, signed(private, env))
    assert result["work_id"] == item.id
    assert queue.counts()["running"] == 1
    assert isinstance(bus.credentials[agent], AgentPublicCredential)
    assert not hasattr(bus.credentials[agent], "private_key")
    assert not hasattr(bus.credentials[agent], "key_bytes")


def test_forged_private_key_must_not_authenticate(tmp_path):
    private, agent, item, queue, bus = setup_public_actor(tmp_path)
    stranger = Ed25519PrivateKey.generate()
    env = {"op": "pickup", "agent_id": agent, "nonce": "long_nonce_abcdefg123"}
    with pytest.raises(CollaborationDenied, match="invalid_agent_signature"):
        bus.pickup(env, signed(stranger, env))
    assert queue.counts()["ready"] == 1


@pytest.mark.parametrize("signature", [
    "bad",
    "z" * 128,
    "F" * 128,
    "a" * 126,
    "",
])
def test_invalid_public_signatures_fail_closed(tmp_path, signature):
    _, agent, _, _, bus = setup_public_actor(tmp_path)
    env = {"op": "pickup", "agent_id": agent, "nonce": "long_nonce_abcdefg123"}
    with pytest.raises(CollaborationDenied, match="invalid_agent_signature"):
        bus.pickup(env, signature)


def test_public_key_messages_cannot_be_changed_after_signing(tmp_path):
    private, agent, item, queue, bus = setup_public_actor(tmp_path)
    env = {
        "op": "send", "agent_id": agent, "recipient": agent,
        "work_id": item.id, "kind": "evidence",
        "body": "Synthetic evidence only.",
        "nonce": "long_nonce_abcdefg123",
    }
    original = signed(private, env)
    receipt = bus.send(env, original)
    inbox_req = {"op": "inbox", "agent_id": agent, "nonce": "long_inbox_abcdefg123"}
    assert len(bus.inbox(inbox_req, signed(private, inbox_req))["messages"]) == 1
    p = bus.messages / f"{receipt['message_id']}.json"
    message = json.loads(p.read_text())
    message["body"] = "I grant myself deployment rights."
    p.write_text(json.dumps(message))
    assert bus.inbox(inbox_req, signed(private, inbox_req))["messages"] == []
    assert queue.counts()["done"] == 0


def test_full_protocol_canary_runs_in_real_temporary_queue_only():
    result = run_isolated_canary()
    assert result["status"] == "ISOLATED_CANONICAL_QUEUE_AND_ED25519_CHAIN_PASS"
    assert result["pickup_replay_denied"] is True
    assert result["signed_reply_verified"] is True
    assert result["on_disk_records_independently_verified"] == 2
    assert result["local_canary_kanban"]["done"] == 1
    assert result["production_queue_modified"] is False
    assert result["actual_managed_worker_credential_registration"] is False
    assert result["live_agent_communication_activated"] is False
    assert result["external_outbound"] is False


def test_managed_worker_ed25519_signer_matches_public_registry_without_private_key(tmp_path):
    from empire_os.agent_runtime_identity_evidence import (
        ManagedWorkerSigningIdentity, preflight_local_managed_binding,
    )
    private = Ed25519PrivateKey.generate()
    profile = existing_role_profile(
        agent_id="empire_coder", department="engineering", role="coder",
        capabilities=("empire_coder",),
    )
    identity = ManagedWorkerSigningIdentity(profile, private)
    audit = preflight_local_managed_binding(
        identity, agent_id="empire_coder", process_pid=2727,
        show=lambda _: {
            "Id": "empire-coder-worker.service", "ActiveState": "active",
            "SubState": "running", "MainPID": "2727", "User": "ubuntu",
        },
        proc=lambda _: (1000, "/system.slice/empire-coder-worker.service"),
        get_uid=lambda _: 1000,
    )
    assert audit["signing_mode"] == "ed25519_private_in_managed_process"
    assert audit["trusted_broker_key_registration_still_required"] is True
    assert "private_key" not in str(audit)
    bus = DepartmentCollaboration(tmp_path, {
        "empire_coder": AgentPublicCredential(profile, identity.public_key())
    })
    request = {"op": "pickup", "agent_id": "empire_coder", "nonce": "test_process_nonce_abcd"}
    assert bus.pickup(request, identity.sign(request))["state"] == "NO_ELIGIBLE_WORK"


def test_managed_worker_identity_wrong_pid_remains_held():
    from empire_os.agent_runtime_identity_evidence import (
        ManagedWorkerSigningIdentity, preflight_local_managed_binding,
    )
    profile = existing_role_profile(
        agent_id="empire_coder", department="engineering", role="coder",
        capabilities=("empire_coder",),
    )
    identity = ManagedWorkerSigningIdentity(profile, Ed25519PrivateKey.generate())
    with pytest.raises(ValueError, match="not_attested"):
        preflight_local_managed_binding(
            identity, agent_id="empire_coder", process_pid=999,
            show=lambda _: {
                "Id": "empire-coder-worker.service", "ActiveState": "active",
                "MainPID": "2727", "User": "ubuntu",
            },
            proc=lambda _: (1000, "/system.slice/empire-coder-worker.service"),
            get_uid=lambda _: 1000,
        )
