"""Unprivileged client for the Empire Ops privileged Unix-socket helper."""
from __future__ import annotations

import json
import socket
import uuid
from pathlib import Path
from typing import Any

from empire_os.ops_privileged_helper import ALLOWED_ACTIONS, ALLOWED_UNITS, SOCKET_PATH


class PrivilegedHelperUnavailable(RuntimeError):
    pass


def privileged_request(
    action: str,
    unit: str,
    *,
    socket_path: Path = SOCKET_PATH,
    timeout: float = 5.0,
) -> dict[str, Any]:
    action = str(action or "").strip()
    unit = str(unit or "").strip()
    if action not in ALLOWED_ACTIONS:
        raise ValueError("action not allowlisted")
    if unit not in ALLOWED_UNITS:
        raise ValueError("unit not allowlisted")
    payload = {
        "request_id": uuid.uuid4().hex,
        "action": action,
        "unit": unit,
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(max(0.5, min(float(timeout), 15.0)))
            conn.connect(str(socket_path))
            conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            raw = b""
            while b"\n" not in raw and len(raw) <= 16384:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                raw += chunk
    except (OSError, TimeoutError) as exc:
        raise PrivilegedHelperUnavailable(
            f"privileged helper unavailable:{type(exc).__name__}"
        ) from exc
    try:
        result = json.loads(raw.split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrivilegedHelperUnavailable("invalid privileged helper response") from exc
    if not isinstance(result, dict):
        raise PrivilegedHelperUnavailable("invalid privileged helper response")
    return result
