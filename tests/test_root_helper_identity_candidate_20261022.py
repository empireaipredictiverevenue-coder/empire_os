"""Exercise exact protected-release candidate, never the active root daemon."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest

from scripts.stage_root_helper_agent_identity_20261022 import (
    DEST, FILES, NEW, ORIGINAL, PINNED_HASH,
    digest, render_candidate, validate_candidate,
)


def test_candidate_exact_pinned_delta_and_untouched_original():
    expected = render_candidate()
    receipt = validate_candidate(DEST, expected)
    assert receipt["status"] == "PINNED_ROOT_HELPER_IDENTITY_READONLY_CANDIDATE_VERIFIED"
    assert digest(ORIGINAL / "empire_os/ops_privileged_helper.py") == PINNED_HASH
    assert set(expected) == FILES | NEW
    assert receipt["original_root_service_modified"] is False
    assert receipt["identity_socket_running"] is False
    assert receipt["persistent_keys_issued"] is False
    assert "SO_PASSCRED" in (
        DEST / "empire_os/agent_peer_identity.py"
    ).read_text()
    source = (ORIGINAL / "empire_os/ops_privileged_helper.py").read_text()
    candidate = (DEST / "empire_os/ops_privileged_helper.py").read_text()
    # Preserve the existing full legacy RPC handler exactly.
    def legacy_handler(text):
        return text.split("def _serve_connection(", 1)[1].split("def serve(", 1)[0]
    assert legacy_handler(candidate) == legacy_handler(source)


def _rpc(sock: Path, payload: dict, *, identity: bool = False) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(str(sock))
        if identity:
            # Root may send READY after enabling SO_PASSCRED, or a non-root
            # test process may reject immediately without authentication.
            try:
                handshake = conn.recv(2048)
            except ConnectionResetError:
                handshake = b""
            if handshake != b"EMPIRE_AGENT_IDENTITY_READY_V1" + bytes((10,)):
                if handshake:
                    return json.loads(handshake)
                return {"ok": False, "error": "root_gate_closed_before_request",
                        "signing_key_issued": False, "message_transport_activated": False}
        try:
            conn.sendall(json.dumps(payload, sort_keys=True).encode() + bytes((10,)))
        except BrokenPipeError:
            return {"ok": False, "error": "root_gate_closed_before_request",
                    "signing_key_issued": False, "message_transport_activated": False}
        raw = bytearray()
        while bytes((10,)) not in raw and len(raw) < 8192:
            chunk = conn.recv(1024)
            if not chunk:
                break
            raw.extend(chunk)
        return json.loads(raw)


def test_candidate_same_existing_helper_both_sockets_no_privilege(tmp_path):
    legacy = tmp_path / "privileged.sock"
    identity = tmp_path / "agent-identity-readonly.sock"
    env = dict(os.environ, PYTHONPATH=str(DEST), PYTHONNOUSERSITE="1",
               PYTHONDONTWRITEBYTECODE="1")
    with subprocess.Popen(
        ["/usr/bin/python3", "-B", "-P", "-m", "empire_os.ops_privileged_helper",
         "--socket", str(legacy), "--allowed-user", "ubuntu"],
        cwd=str(tmp_path), env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, text=True,
    ) as proc:
        try:
            for _ in range(50):
                if legacy.is_socket() and identity.is_socket():
                    break
                if proc.poll() is not None:
                    raise AssertionError("candidate_helper_exited_before_listening")
                time.sleep(0.04)
            assert legacy.is_socket() and identity.is_socket()
            old = _rpc(legacy, {
                "request_id": "offline-legacy-check",
                "action": "service_status",
                "unit": "empire-public-gateway.service",
            })
            assert old["request_id"] == "offline-legacy-check"
            assert old["action"] == "service_status"
            assert old["unit"] == "empire-public-gateway.service"

            # Neither a UID match nor an agent_id field grants authority.
            refused = _rpc(identity, {
                "op": "identity_preflight", "agent_id": "empire_coder",
                "nonce": "approved_nonce_abcdefgh",
            }, identity=True)
            assert refused["ok"] is False
            assert refused["error"] in {
                "trusted_managed_main_process_required",
                "root_gate_closed_before_request",
            }
            assert refused["signing_key_issued"] is False
            assert refused["message_transport_activated"] is False

            forbidden = _rpc(legacy, {
                "request_id": "offline-legacy-reject",
                "action": "identity_preflight",
                "unit": "empire-coder-worker.service",
            })
            assert forbidden["ok"] is False
            assert "allowlist" in forbidden["error"]

            wrong_action = _rpc(identity, {
                "op": "sign", "agent_id": "empire_coder",
                "nonce": "approved_nonce_abcdefgh",
            }, identity=True)
            assert wrong_action["ok"] is False
            assert wrong_action["signing_key_issued"] is False
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
