"""Bounded Founder Console health and orphan-port recovery.

Repairs only the exact failure observed in production: a stale Next.js process
owned by the EmpireOS user keeps port 3001 after the systemd unit is unhealthy.

The tool refuses to kill anything unless process identity, working directory,
port ownership and cgroup evidence all match the Founder Console contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from typing import Any, Callable
import urllib.error
import urllib.request


FOUNDER_CONSOLE_UNIT = "empire-founder-console.service"
FOUNDER_CONSOLE_APP = Path(
    "/srv/empire_os/apps/search-command-centre"
)
FOUNDER_CONSOLE_PORT = 3001
FOUNDER_CONSOLE_URL = "http://127.0.0.1:3001/founder"


@dataclass(frozen=True)
class FounderConsoleObservation:
    service_state: str
    http_ok: bool
    port_pid: int | None
    port_process_verified: bool
    port_process_cwd: str | None
    port_process_command: str | None
    port_process_cgroup: str | None
    legacy_user_scope: bool


def _service_state(
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> str:
    result = runner(
        ["systemctl", "is-active", FOUNDER_CONSOLE_UNIT],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return (
        (result.stdout or result.stderr or "").strip()
        or "unknown"
    )


def _http_ok() -> bool:
    request = urllib.request.Request(
        FOUNDER_CONSOLE_URL,
        headers={"Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return int(response.status) == 200
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ):
        return False


def _listener_pid(
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> int | None:
    result = runner(
        ["ss", "-ltnp"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    for line in (result.stdout or "").splitlines():
        if f":{FOUNDER_CONSOLE_PORT}" not in line:
            continue
        match = re.search(r"pid=(\d+)", line)
        if match:
            return int(match.group(1))
    return None


def _process_identity(pid: int) -> dict[str, Any]:
    proc = Path("/proc") / str(int(pid))
    try:
        cwd = str((proc / "cwd").resolve())
        command = (
            (proc / "cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode("utf-8", errors="replace")
            .strip()
        )
        cgroup = (proc / "cgroup").read_text(
            encoding="utf-8",
            errors="replace",
        )
        stat = (proc / "stat").read_text(
            encoding="utf-8",
            errors="replace",
        ).split()
        start_ticks = stat[21] if len(stat) > 21 else None
        uid = proc.stat().st_uid
    except (OSError, IndexError):
        return {
            "exists": False,
            "cwd": None,
            "command": None,
            "cgroup": None,
            "start_ticks": None,
            "uid": None,
        }
    return {
        "exists": True,
        "cwd": cwd,
        "command": command,
        "cgroup": cgroup,
        "start_ticks": start_ticks,
        "uid": uid,
    }


def _legacy_user_scope(identity: dict[str, Any]) -> bool:
    cgroup = str(identity.get("cgroup") or "")
    return bool(
        "/user.slice/" in cgroup
        and FOUNDER_CONSOLE_UNIT in cgroup
    )


def _canonical_system_scope(identity: dict[str, Any]) -> bool:
    cgroup = str(identity.get("cgroup") or "")
    return (
        f"/system.slice/{FOUNDER_CONSOLE_UNIT}" in cgroup
    )


def _verified_console_process(
    identity: dict[str, Any],
) -> bool:
    command = str(identity.get("command") or "").casefold()
    return bool(
        identity.get("exists")
        and identity.get("uid") == os.getuid()
        and identity.get("cwd") == str(FOUNDER_CONSOLE_APP)
        and ("next-server" in command or "next" in command)
        and not _canonical_system_scope(identity)
    )


def observe_founder_console(
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> FounderConsoleObservation:
    state = _service_state(runner=runner)
    pid = _listener_pid(runner=runner)
    identity = _process_identity(pid) if pid else {}
    return FounderConsoleObservation(
        service_state=state,
        http_ok=_http_ok(),
        port_pid=pid,
        port_process_verified=(
            _verified_console_process(identity)
            if pid
            else False
        ),
        port_process_cwd=identity.get("cwd"),
        port_process_command=identity.get("command"),
        port_process_cgroup=identity.get("cgroup"),
        legacy_user_scope=_legacy_user_scope(identity),
    )


def _stop_legacy_user_unit(
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    uid = os.getuid()
    runtime_dir = f"/run/user/{uid}"
    env = dict(os.environ)
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["DBUS_SESSION_BUS_ADDRESS"] = (
        f"unix:path={runtime_dir}/bus"
    )
    completed = runner(
        [
            "systemctl",
            "--user",
            "disable",
            "--now",
            FOUNDER_CONSOLE_UNIT,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        env=env,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": int(completed.returncode),
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def clear_verified_orphan(
    observation: FounderConsoleObservation,
    *,
    sleep: Callable[[float], None] = time.sleep,
    user_unit_stopper: Callable[..., dict[str, Any]] = (
        _stop_legacy_user_unit
    ),
    process_identity: Callable[[int], dict[str, Any]] = (
        _process_identity
    ),
    process_exists: Callable[[int], bool] = (
        lambda pid: (Path("/proc") / str(pid)).exists()
    ),
    kill_process: Callable[[int, int], None] = os.kill,
) -> dict[str, Any]:
    if observation.service_state == "active":
        return {
            "ok": True,
            "state": "NO_ACTION_SERVICE_ACTIVE",
            "killed": False,
        }
    if observation.port_pid is None:
        return {
            "ok": True,
            "state": "NO_ORPHAN_PORT_OWNER",
            "killed": False,
        }
    if not observation.port_process_verified:
        return {
            "ok": False,
            "state": "PORT_OWNER_NOT_VERIFIED",
            "killed": False,
        }

    if observation.legacy_user_scope:
        stopped = user_unit_stopper()
        if stopped.get("ok") is not True:
            return {
                "ok": False,
                "state": "LEGACY_USER_UNIT_STOP_FAILED",
                "killed": False,
                "legacy_user_unit_stop": stopped,
            }

    pid = int(observation.port_pid)

    # systemctl --user disable --now may terminate the stale process itself.
    # That is already the desired bounded recovery outcome.
    if not process_exists(pid):
        return {
            "ok": True,
            "state": "ORPHAN_TERMINATED_BY_USER_UNIT_STOP",
            "killed": False,
            "pid": pid,
        }

    before = process_identity(pid)
    if not _verified_console_process(before):
        return {
            "ok": False,
            "state": "PROCESS_IDENTITY_CHANGED",
            "killed": False,
        }

    kill_process(pid, signal.SIGTERM)
    for _ in range(20):
        if not process_exists(pid):
            return {
                "ok": True,
                "state": "ORPHAN_TERMINATED",
                "killed": True,
                "signal": "TERM",
                "pid": pid,
            }
        sleep(0.1)

    after = process_identity(pid)
    if (
        not _verified_console_process(after)
        or after.get("start_ticks") != before.get("start_ticks")
    ):
        return {
            "ok": False,
            "state": "PROCESS_IDENTITY_CHANGED_AFTER_TERM",
            "killed": False,
            "pid": pid,
        }

    kill_process(pid, signal.SIGKILL)
    sleep(0.1)
    gone = not process_exists(pid)
    return {
        "ok": gone,
        "state": (
            "ORPHAN_KILLED"
            if gone
            else "ORPHAN_KILL_FAILED"
        ),
        "killed": gone,
        "signal": "KILL" if gone else None,
        "pid": pid,
    }


def as_dict(
    observation: FounderConsoleObservation,
) -> dict[str, Any]:
    return asdict(observation)
