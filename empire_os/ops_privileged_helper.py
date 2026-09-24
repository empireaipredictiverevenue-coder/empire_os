"""Root-owned narrow privileged helper for Empire Ops MCP.

The helper exposes no shell. Requests arrive over a local Unix socket and are
validated against explicit action/unit allowlists before systemctl is called.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import socket
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

SOCKET_PATH = Path("/run/empire-ops/privileged.sock")
ALLOWED_ACTIONS = frozenset({"service_status", "service_restart", "service_start"})
ALLOWED_UNITS = frozenset({
    "empire-public-gateway.service",
    "empire-self-serve-checkout.service",
    "empire-ops-mcp.service",
    "empire-revenue-pulse.service",
    "empire-revenue-pulse.timer",
    "empire-conversation-recovery.service",
    "empire-buyer-capacity-readiness.service",
    "empire-acquisition.service",
    "empire-acquisition.timer",
    "empire-qualification.service",
    "empire-qualification.timer",
    "empire-commercial-product-catalog.service",
    "empire-commercial-product-catalog.timer",
    "empire-commercial-exchange.service",
    "empire-commercial-exchange.timer",
    "empire-buyer-acquisition-team.service",
    "empire-buyer-acquisition-team.timer",
    "empire-source-health.service",
    "empire-source-health.timer",
    "empire-hermes-control.timer",
    "empire-coder-worker.service",
    "empire-coder-worker.timer",
})
START_ONLY_UNITS = frozenset({
    "empire-revenue-pulse.service",
    "empire-conversation-recovery.service",
    "empire-buyer-capacity-readiness.service",
    "empire-acquisition.service",
    "empire-qualification.service",
    "empire-commercial-product-catalog.service",
    "empire-commercial-exchange.service",
    "empire-buyer-acquisition-team.service",
    "empire-source-health.service",
    "empire-coder-worker.service",
})
MAX_REQUEST_BYTES = 8192


class PrivilegedHelperPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class HelperRequest:
    request_id: str
    action: str
    unit: str


def validate_request(payload: Mapping[str, Any]) -> HelperRequest:
    request_id = str(payload.get("request_id") or "").strip()
    action = str(payload.get("action") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    if not request_id or len(request_id) > 128:
        raise PrivilegedHelperPolicyError("valid request_id required")
    if action not in ALLOWED_ACTIONS:
        raise PrivilegedHelperPolicyError("action not allowlisted")
    if unit not in ALLOWED_UNITS:
        raise PrivilegedHelperPolicyError("unit not allowlisted")
    if action == "service_start" and unit not in START_ONLY_UNITS:
        raise PrivilegedHelperPolicyError("unit not allowlisted for start")
    return HelperRequest(request_id=request_id, action=action, unit=unit)


def _systemctl_argv(request: HelperRequest) -> list[str]:
    if request.action == "service_status":
        return [
            "systemctl",
            "show",
            request.unit,
            "--property=ActiveState,SubState,UnitFileState",
        ]
    if request.action == "service_restart":
        return ["systemctl", "restart", request.unit]
    if request.action == "service_start":
        return ["systemctl", "start", request.unit]
    raise PrivilegedHelperPolicyError("unsupported action")


def execute_request(
    payload: Mapping[str, Any],
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    request = validate_request(payload)
    argv = _systemctl_argv(request)
    completed = runner(
        argv,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    return {
        "request_id": request.request_id,
        "action": request.action,
        "unit": request.unit,
        "returncode": int(completed.returncode),
        "stdout": (completed.stdout or "")[-4000:],
        "stderr": (completed.stderr or "")[-2000:],
        "ok": completed.returncode == 0,
    }


def _peer_uid(conn: socket.socket) -> int:
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    _pid, uid, _gid = struct.unpack("3i", raw)
    return int(uid)


def _allowed_uid(user: str) -> int:
    return int(pwd.getpwnam(user).pw_uid)


def _serve_connection(
    conn: socket.socket,
    *,
    allowed_uid: int,
) -> None:
    if _peer_uid(conn) not in {0, allowed_uid}:
        conn.sendall(
            (json.dumps({"ok": False, "error": "peer_not_authorized"}) + "\n").encode()
        )
        return
    data = b""
    while b"\n" not in data and len(data) <= MAX_REQUEST_BYTES:
        chunk = conn.recv(2048)
        if not chunk:
            break
        data += chunk
    if len(data) > MAX_REQUEST_BYTES:
        response = {"ok": False, "error": "request_too_large"}
    else:
        try:
            payload = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
            if not isinstance(payload, dict):
                raise PrivilegedHelperPolicyError("request must be an object")
            response = execute_request(payload)
        except Exception as exc:
            response = {
                "ok": False,
                "error": f"{type(exc).__name__}:{str(exc)[:300]}",
            }
    conn.sendall((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


def serve(
    *,
    socket_path: Path = SOCKET_PATH,
    allowed_user: str = "ubuntu",
) -> None:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)
    allowed_uid = _allowed_uid(allowed_user)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o660)
        server.listen(8)
        while True:
            conn, _ = server.accept()
            with conn:
                _serve_connection(conn, allowed_uid=allowed_uid)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default=str(SOCKET_PATH))
    parser.add_argument("--allowed-user", default="ubuntu")
    args = parser.parse_args()
    serve(
        socket_path=Path(args.socket),
        allowed_user=args.allowed_user,
    )


if __name__ == "__main__":
    main()
