"""One-shot READ ONLY original Coder service -> existing root helper origin proof.

No agent registration, key creation, task pickup, runtime activation,
message delivery, payment or outbound. No service is started by this code.
"""
from __future__ import annotations

import json
import os
import secrets
import socket

UNIT = "empire-coder-worker.service"
AGENT = "empire_coder"
SOCKET = "/run/empire-ops/agent-identity-readonly.sock"
READY = b"EMPIRE_AGENT_IDENTITY_READY_V1" + bytes((10,))
MAX_REPLY = 2048


class CoderIdentityProofHeld(ValueError):
    pass


def probe_current_coder_process() -> dict[str, object]:
    """Trust a positive verdict ONLY when received directly from protected root socket.

    Must be invoked from Coder's original ExecStart Python main process.
    A successful response only establishes current-process provenance.
    """
    envelope = {
        "op": "identity_preflight", "agent_id": AGENT,
        "nonce": secrets.token_urlsafe(24),
    }
    wire = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode() + bytes((10,))
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(3.0)
            conn.connect(SOCKET)
            ready = bytearray()
            while len(ready) <= len(READY) and bytes((10,)) not in ready:
                chunk = conn.recv(len(READY) + 1 - len(ready))
                if not chunk:
                    break
                ready.extend(chunk)
            if bytes(ready) != READY:
                raise CoderIdentityProofHeld("root_identity_protocol_not_ready")
            conn.sendall(wire)
            response = bytearray()
            while len(response) <= MAX_REPLY and bytes((10,)) not in response:
                data = conn.recv(512)
                if not data:
                    break
                response.extend(data)
            if (
                len(response) > MAX_REPLY
                or response.count(bytes((10,))) != 1
                or not response.endswith(bytes((10,)))
            ):
                raise CoderIdentityProofHeld("invalid_root_identity_reply_frame")
    except (OSError, TimeoutError) as exc:
        raise CoderIdentityProofHeld("root_identity_socket_unavailable") from exc
    try:
        obj = json.loads(response)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise CoderIdentityProofHeld("invalid_root_identity_json") from exc
    expected = {
        "ok": True,
        "schema_version": "empire.agents.root_peer_scope.v1",
        "agent_id": AGENT, "unit": UNIT,
        "process_origin_verified": True,
        "signing_key_issued": False,
        "trusted_broker_registration": False,
        "message_transport_activated": False,
        "queue_write_authority": False,
        "execution_authority": "none",
    }
    if obj != expected:
        raise CoderIdentityProofHeld("real_coder_process_not_authorised")
    return {
        "status": "VERIFIED_CURRENT_CODER_MAIN_PROCESS_BY_ROOT_HELPER",
        "agent_id": AGENT, "unit": UNIT,
        "actual_worker_pid": os.getpid(),
        "root_helper_identity_preflight": True,
        "persistent_signing_key_issued": False,
        "registered_agent": False,
        "live_collaboration_activated": False,
        "canonical_task_claimed": False,
        "execution_authority": "none",
    }
