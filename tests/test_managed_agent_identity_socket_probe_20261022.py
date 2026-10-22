"""Read-only Coder client protocol and unchanged one-shot worker semantics."""
from __future__ import annotations

import json
import os
import socket
import threading

import pytest

from empire_os import managed_agent_identity_socket_probe as probe
from scripts import run_graphify_coder_worker_20261020 as worker


GOOD_REPLY = {
    "ok": True, "schema_version": "empire.agents.root_peer_scope.v1",
    "agent_id": "empire_coder", "unit": "empire-coder-worker.service",
    "process_origin_verified": True, "signing_key_issued": False,
    "trusted_broker_registration": False,
    "message_transport_activated": False, "queue_write_authority": False,
    "execution_authority": "none",
}


def run_local_test_server(monkeypatch, tmp_path, *, response=GOOD_REPLY,
                          give_handshake=True):
    path = tmp_path / "identity-only.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    captured = {}
    def server_worker():
        try:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(2)
                if not give_handshake:
                    conn.sendall(b"WRONG_READY" + bytes((10,)))
                    return
                conn.sendall(probe.READY)
                incoming = bytearray()
                while bytes((10,)) not in incoming:
                    chunk = conn.recv(1024)
                    if not chunk:
                        return
                    incoming.extend(chunk)
                captured["message"] = json.loads(incoming)
                conn.sendall(json.dumps(response).encode()+bytes((10,)))
        except (OSError, TimeoutError) as exc:
            captured["server_error"] = type(exc).__name__
        finally:
            server.close()
    thread = threading.Thread(target=server_worker, daemon=True)
    thread.start()
    monkeypatch.setattr(probe, "SOCKET", str(path))
    return captured, thread


def test_current_process_success_is_identity_only(tmp_path, monkeypatch):
    captured, thread = run_local_test_server(monkeypatch, tmp_path)
    result = probe.probe_current_coder_process()
    thread.join(3)
    assert not thread.is_alive()
    assert result["status"] == "VERIFIED_CURRENT_CODER_MAIN_PROCESS_BY_ROOT_HELPER"
    assert result["actual_worker_pid"] == os.getpid()
    assert result["registered_agent"] is False
    assert result["persistent_signing_key_issued"] is False
    assert result["live_collaboration_activated"] is False
    assert result["canonical_task_claimed"] is False
    assert set(captured["message"]) == {"op", "agent_id", "nonce"}
    assert captured["message"]["op"] == "identity_preflight"
    assert captured["message"]["agent_id"] == "empire_coder"
    assert len(captured["message"]["nonce"]) >= 16


@pytest.mark.parametrize("alter", [
    {"ok": False}, {"agent_id": "department_executive"},
    {"unit": "other.service"}, {"signing_key_issued": True},
    {"trusted_broker_registration": True},
    {"message_transport_activated": True},
    {"queue_write_authority": True},
    {"execution_authority": "send"},
    {"process_origin_verified": False},
])
def test_wrong_or_unexpected_authority_is_never_accepted(monkeypatch,tmp_path,alter):
    reply = dict(GOOD_REPLY, **alter)
    _, thread = run_local_test_server(monkeypatch,tmp_path,response=reply)
    with pytest.raises(probe.CoderIdentityProofHeld):
        probe.probe_current_coder_process()
    thread.join(3)


def test_missing_ready_handshake_fail_closed(monkeypatch,tmp_path):
    _, thread = run_local_test_server(monkeypatch,tmp_path,give_handshake=False)
    with pytest.raises(probe.CoderIdentityProofHeld,match="not_ready"):
        probe.probe_current_coder_process()
    thread.join(3)


def test_marker_one_shot_strict_owner_and_exact_scope(tmp_path):
    marker=tmp_path/"root_probe.flag"
    exact=b"EMPIRE_CODER_ROOT_IDENTITY_PREFLIGHT_ONLY_V1"+bytes((10,))
    marker.write_bytes(exact)
    marker.chmod(0o600)
    assert worker._consume_once_identity_probe_marker(marker,expected=exact) is True
    assert not marker.exists()
    assert worker._consume_once_identity_probe_marker(marker,expected=exact) is False
    marker.write_bytes(b"EMPIRE_CODER_PROCESS_SIGNING_OBSERVE_ONLY_V1"+bytes((10,)))
    marker.chmod(0o600)
    assert worker._consume_once_identity_probe_marker(marker,expected=exact) is False
    assert marker.exists()


def test_one_shot_hook_is_disabled_without_marker(monkeypatch):
    from pathlib import Path
    from empire_os import managed_agent_identity_socket_probe as p
    monkeypatch.setattr(worker, "_consume_once_identity_probe_marker",lambda *a,**kw: False)
    monkeypatch.setattr(p,"probe_current_coder_process",lambda: (_ for _ in ()).throw(AssertionError("unexpected RPC")))
    worker._observe_existing_root_identity_preflight()


def test_one_shot_hook_does_not_interrupt_existing_job(monkeypatch,capsys):
    from empire_os import managed_agent_identity_socket_probe as p
    monkeypatch.setattr(worker, "_consume_once_identity_probe_marker",lambda *a,**kw: True)
    def reject():
        raise probe.CoderIdentityProofHeld("private_data_do_not_log")
    monkeypatch.setattr(p,"probe_current_coder_process",reject)
    worker._observe_existing_root_identity_preflight()
    text=capsys.readouterr().err
    assert "CODER_ROOT_IDENTITY_PREFLIGHT_HELD_CoderIdentityProofHeld" in text
    assert "private_data_do_not_log" not in text


def test_identity_preflight_alone_is_not_auth_activation(monkeypatch,capsys):
    from empire_os import managed_agent_identity_socket_probe as p
    monkeypatch.setattr(worker, "_consume_once_identity_probe_marker",lambda *a,**kw: True)
    monkeypatch.setattr(p,"probe_current_coder_process",
                        lambda: {"status":"VERIFIED_CURRENT_CODER_MAIN_PROCESS_BY_ROOT_HELPER",
                                 "registered_agent":False,"live_collaboration_activated":False})
    worker._observe_existing_root_identity_preflight()
    report=json.loads(capsys.readouterr().err.split(" ",1)[1])
    assert report["registered_agent"] is False
    assert report["live_collaboration_activated"] is False
