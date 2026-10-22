"""Trusted per-unit peer origin policies; no root service or keys touched."""
from __future__ import annotations

import os
import socket
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from empire_os.agent_peer_identity import (
    AgentPeerDenied, KernelPeer, _kernel_peer, _kernel_bound_request,
    _proc_ids_and_cgroup,
    _proc_start_ticks, attest_connected_managed_worker,
    validate_managed_peer_binding,
)

UNIT = "empire-coder-worker.service"
CGROUP = f"/system.slice/{UNIT}"
PEER = KernelPeer(pid=4123, uid=1000, gid=1000)
UNIT_STATE = {
    "Id": UNIT, "MainPID": "4123", "ActiveState": "activating",
    "SubState": "start", "User": "ubuntu", "Group": "ubuntu",
}


def verified(**changes):
    values = {
        "agent_id": "empire_coder",
        "peer": PEER,
        "unit_state": UNIT_STATE,
        "proc_uid": 1000, "proc_gid": 1000,
        "cgroup": CGROUP, "start_before": 125675,
        "start_after": 125675,
        "expected_uid": 1000, "expected_gid": 1000,
    }
    values.update(changes)
    return validate_managed_peer_binding(**values)


def test_exact_real_coder_main_process_provenance_is_observe_only():
    status = verified()
    assert status["process_origin_verified"] is True
    assert status["agent_id"] == "empire_coder"
    assert status["department"] == "engineering"
    assert status["allowed_component"] == "empire_coder"
    for blocked in ("signing_key_issued", "trusted_broker_registration",
                    "message_transport_activated", "queue_write_authority"):
        assert status[blocked] is False
    assert status["execution_authority"] == "none"


@pytest.mark.parametrize("change", [
    {"agent_id": "invented_agent"},
    {"agent_id": "jev"},
    {"peer": KernelPeer(pid=4124, uid=1000, gid=1000)},
    {"peer": KernelPeer(pid=4123, uid=0, gid=1000)},
    {"peer": KernelPeer(pid=4123, uid=1000, gid=0)},
    {"proc_uid": 0},
    {"proc_gid": 0},
    {"expected_uid": 999},
    {"expected_gid": 999},
    {"cgroup": "/system.slice/empire-department-cycle.service"},
    {"cgroup": "/system.slice/empire-coder-worker.service-fake"},
    {"cgroup": "/system.slice/empire-coder-worker.service/nested"},
    {"start_before": 0},
    {"start_after": 125676},
])
def test_wrong_peer_unit_role_or_kernel_identity_is_held(change):
    with pytest.raises(AgentPeerDenied):
        verified(**change)


@pytest.mark.parametrize("key,value", [
    ("Id", "empire-department-cycle.service"),
    ("MainPID", "0"),
    ("MainPID", "4124"),
    ("MainPID", "bad"),
    ("ActiveState", "active"),
    ("ActiveState", "inactive"),
    ("SubState", "start-pre"),
    ("SubState", "start-post"),
    ("SubState", "dead"),
    ("User", "root"),
    ("Group", "root"),
])
def test_incorrect_service_phase_or_config_denied(key, value):
    spec = dict(UNIT_STATE, **{key: value})
    with pytest.raises(AgentPeerDenied):
        verified(unit_state=spec)


def test_socket_peer_identity_read_from_kernel_instead_of_message():
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        peer = _kernel_peer(parent)
        assert peer.pid == os.getpid()
        assert peer.uid == os.getuid()
        assert peer.gid == os.getgid()
        assert child.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    finally:
        parent.close()
        child.close()


def test_syscall_denied_outside_existing_root_helper_before_socket_use(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    class HostileSocket:
        def getsockopt(self, *args):
            raise AssertionError("must never use socket before root check")
    with pytest.raises(AgentPeerDenied, match="root_owned_helper_required"):
        attest_connected_managed_worker(HostileSocket(), agent_id="empire_coder")


def test_linux_stat_parser_accounts_for_parenthesized_command(tmp_path):
    pid = tmp_path / "4123"
    pid.mkdir()
    # PID + comm, followed by fields 3..22. Start time = final field.
    fields = ["S"] + ["0"] * 18 + ["123456"]
    (pid / "stat").write_text("4123 (coder (main) worker) " + " ".join(fields))
    assert _proc_start_ticks(4123, tmp_path) == 123456
    (pid / "status").write_text(
        "Name:\tpython\nUid:\t1000\t1000\t1000\t1000\n"
        "Gid:\t1000\t1000\t1000\t1000\n"
    )
    (pid / "cgroup").write_text(f"0::{CGROUP}\n")
    assert _proc_ids_and_cgroup(4123, tmp_path) == (1000, 1000, CGROUP)


def test_no_kernel_cgroup_or_start_time_fails_closed(tmp_path):
    pid = tmp_path / "4123"
    pid.mkdir()
    with pytest.raises(AgentPeerDenied, match="start_unavailable"):
        _proc_start_ticks(4123, tmp_path)
    (pid / "status").write_text("Uid:\t1000\nGid:\t1000\n")
    (pid / "cgroup").write_text("1:memory:/system.slice/other\n")
    with pytest.raises(AgentPeerDenied, match="identity_unavailable"):
        _proc_ids_and_cgroup(4123, tmp_path)


def test_real_root_broker_policy_with_synthetic_controlled_peer(monkeypatch, tmp_path):
    """No real root service, no systemd change: socket and OS checks stubbed."""
    from empire_os import agent_peer_identity as impl
    fake = object()
    fd = os.open("/dev/null", os.O_RDONLY)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        impl, "_kernel_bound_request",
        lambda _: (PEER, {"op": "identity_preflight",
                         "agent_id": "empire_coder", "nonce": "validnonce_abcdefghij"}),
    )
    monkeypatch.setattr(pwd := impl.pwd, "getpwnam",
                        lambda _: SimpleNamespace(pw_uid=1000, pw_gid=1000))
    monkeypatch.setattr(os, "pidfd_open", lambda pid, flags=0: os.dup(fd))
    monkeypatch.setattr(impl, "_proc_start_ticks", lambda *args: 125675)
    monkeypatch.setattr(impl, "_proc_ids_and_cgroup", lambda *args: (1000, 1000, CGROUP))
    try:
        receipt = attest_connected_managed_worker(
            fake, agent_id="empire_coder",
            show=lambda _: UNIT_STATE,
        )
    finally:
        os.close(fd)
    assert receipt["process_origin_verified"] is True
    assert receipt["trusted_broker_registration"] is False


def test_foreign_agent_cannot_pass_even_with_valid_sock(monkeypatch):
    from empire_os import agent_peer_identity as impl
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        impl, "_kernel_bound_request",
        lambda _: (PEER, {"op": "identity_preflight",
                         "agent_id": "unregistered", "nonce": "validnonce_abcdefghij"}),
    )
    with pytest.raises(AgentPeerDenied, match="allowlist"):
        attest_connected_managed_worker(object(), agent_id="unregistered")


def test_unix_message_has_current_sender_kernel_credentials():
    from empire_os.agent_peer_identity import _kernel_bound_request
    server, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.settimeout(2)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        sender.sendall(
            b'{"op":"identity_preflight","agent_id":"empire_coder",'
            b'"nonce":"strict_nonce_0123456789"}' + bytes((10,))
        )
        peer, request = _kernel_bound_request(server)
        assert peer.pid == os.getpid()
        assert peer.uid == os.getuid()
        assert peer.gid == os.getgid()
        assert request["op"] == "identity_preflight"
        assert request["agent_id"] == "empire_coder"
    finally:
        server.close()
        sender.close()


@pytest.mark.parametrize("payload", [
    b'{"op":"identity_preflight","agent_id":"empire_coder","nonce":"too_short"}',
    b'{"op":"identity_preflight","agent_id":"empire_coder","nonce":"validnonce_abcdefghij","authority":"send"}',
    b'{"op":"payment","agent_id":"empire_coder","nonce":"validnonce_abcdefghij"}',
    b'{"op":"identity_preflight","agent_id":"empire_coder","nonce":"validnonce_abcdefghij"}' + bytes((10,10)),
])
def test_incorrect_frame_or_extra_authority_denied(payload):
    from empire_os.agent_peer_identity import _kernel_bound_request
    server, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.settimeout(2)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        sender.sendall(payload + (bytes((10,)) if not payload.endswith(bytes((10,))) else b""))
        with pytest.raises(AgentPeerDenied):
            _kernel_bound_request(server)
    finally:
        server.close()
        sender.close()


def test_per_message_credential_mismatch_is_held(monkeypatch):
    from empire_os import agent_peer_identity as impl
    from types import SimpleNamespace
    fake = SimpleNamespace(
        family=socket.AF_UNIX, type=socket.SOCK_STREAM,
        setsockopt=lambda *_a: None,
        settimeout=lambda *_a: None,
        recvmsg=lambda *_a: (
            b'{"op":"identity_preflight","agent_id":"empire_coder",'
            b'"nonce":"validnonce_abcdefghij"}' + bytes((10,)),
            [(socket.SOL_SOCKET, socket.SCM_CREDENTIALS,
              struct.pack("3i", 4124, 1000, 1000))], 0, None,
        ),
    )
    monkeypatch.setattr(impl, "_kernel_peer", lambda _: PEER)
    with pytest.raises(AgentPeerDenied, match="per_message_kernel_sender_mismatch"):
        _kernel_bound_request(fake)


def test_file_descriptor_transfer_or_truncated_ancillary_is_never_authorised():
    from empire_os.agent_peer_identity import _kernel_bound_request
    server, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    fd = os.open("/dev/null", os.O_RDONLY)
    try:
        server.settimeout(2)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        payload = (
            b'{"op":"identity_preflight","agent_id":"empire_coder",'
            b'"nonce":"validnonce_abcdefghij"}' + bytes((10,))
        )
        sender.sendmsg(
            [payload],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", fd))],
        )
        with pytest.raises(AgentPeerDenied):
            _kernel_bound_request(server)
    finally:
        os.close(fd)
        server.close()
        sender.close()
