"""The existing ROOT privileged helper's read-only per-worker identity socket.

No key issuance, signature operation, queue lease, external communication
or registration. Never route this through the legacy shared-UID RPC reader.
"""
from __future__ import annotations

import json
import socket

from empire_os.agent_peer_identity import (
    AgentPeerDenied,
    attest_connected_managed_worker,
)

IDENTITY_SOCKET_BASENAME = "agent-identity-readonly.sock"


def serve_identity_preflight(conn: socket.socket) -> None:
    """Bounded one-frame, kernel-credentialled root-side identity observation."""
    try:
        result = attest_connected_managed_worker(conn)
        response = {
            "ok": True,
            "schema_version": "empire.agents.root_peer_scope.v1",
            "agent_id": result["agent_id"],
            "unit": result["unit"],
            "process_origin_verified": True,
            "signing_key_issued": False,
            "trusted_broker_registration": False,
            "message_transport_activated": False,
            "queue_write_authority": False,
            "execution_authority": "none",
        }
    except (AgentPeerDenied, ValueError, OSError, TypeError):
        response = {
            "ok": False,
            "error": "trusted_managed_main_process_required",
            "signing_key_issued": False,
            "message_transport_activated": False,
        }
    try:
        conn.sendall(
            (json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )
    except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
        pass
