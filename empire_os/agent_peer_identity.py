"""Root-broker, socket-scoped provenance for EXISTING EmpireOS workers.

No credential generation, broker activation, new daemon, model execution,
outbound, or queue mutation. This is an OPTIONAL primitive for the existing
root-owned Empire Ops helper's future guarded collaboration adapter.

Crucial: SO_PEERCRED binds a Unix socket to kernel PID/UID/GID at connect.
Checking only UID=ubuntu is INSUFFICIENT because many services share it.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import socket
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

# Deliberately self-contained: root-pinned helper releases MUST NOT import
# the editable /srv/empire_os agent catalogue at runtime. Pin this exact
# allowlist in the independent protected helper release.
@dataclass(frozen=True)
class ExistingWorkerBinding:
    agent_id: str
    unit: str
    department: str
    role: str
    component: str
    expected_user: str = "ubuntu"


MANAGED_WORKERS = (
    ExistingWorkerBinding(
        "empire_coder", "empire-coder-worker.service",
        "engineering", "coder", "empire_coder",
    ),
    ExistingWorkerBinding(
        "department_executive", "empire-department-cycle.service",
        "strategy", "executive_operations", "astra_executive",
    ),
)

PEER_SIZE = struct.calcsize("3i")
SYSTEM_UNIT = re.compile(r"^[a-z0-9][a-z0-9@_.-]{1,127}\.service$")
CLIENT_NONCE = re.compile(r"^[A-Za-z0-9_-]{16,96}$")
MAX_IDENTITY_FRAME = 1024


class AgentPeerDenied(ValueError):
    pass


@dataclass(frozen=True)
class KernelPeer:
    pid: int
    uid: int
    gid: int


def _kernel_peer(conn: socket.socket) -> KernelPeer:
    if conn.family != socket.AF_UNIX or conn.type & 0xF != socket.SOCK_STREAM:
        raise AgentPeerDenied("unix_stream_peer_required")
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, PEER_SIZE)
    if len(raw) != PEER_SIZE:
        raise AgentPeerDenied("kernel_peer_credentials_required")
    pid, uid, gid = struct.unpack("3i", raw)
    if pid <= 1 or uid < 0 or gid < 0:
        raise AgentPeerDenied("invalid_kernel_peer")
    return KernelPeer(pid=pid, uid=uid, gid=gid)


def _kernel_bound_request(conn: socket.socket) -> tuple[KernelPeer, dict[str, str]]:
    """One framed request carrying *current sender* Linux SCM_CREDENTIALS.

    SO_PEERCRED alone can be reused if an already-connected FD is passed
    between same-UID processes. Requiring SCM_CREDENTIALS bound to EACH
    recvmsg prevents that socket-FD delegation from impersonating a worker.
    """
    if conn.family != socket.AF_UNIX or conn.type & 0xF != socket.SOCK_STREAM:
        raise AgentPeerDenied("unix_stream_peer_required")
    try:
        conn.settimeout(3.0)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        connected_peer = _kernel_peer(conn)
        # Protocol readiness is NOT an auth response. It ensures that
        # SO_PASSCRED is active before the peer sends its ONE request.
        conn.sendall(b"EMPIRE_AGENT_IDENTITY_READY_V1" + bytes((10,)))
        frame, controls, flags, _addr = conn.recvmsg(
            MAX_IDENTITY_FRAME + 1, socket.CMSG_SPACE(PEER_SIZE),
            socket.MSG_CMSG_CLOEXEC,
        )
    except OSError as exc:
        raise AgentPeerDenied("kernel_bound_peer_request_unavailable") from exc
    # Never accept or retain transferred file descriptors from an agent.
    # Close any SCM_RIGHTS fds even if the frame also failed other checks.
    other_ancillary = False
    for level, kind, data in controls:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            for offset in range(0, len(data) - len(data) % 4, 4):
                try:
                    os.close(struct.unpack("i", data[offset:offset + 4])[0])
                except OSError:
                    pass
            other_ancillary = True
        elif level != socket.SOL_SOCKET or kind != socket.SCM_CREDENTIALS:
            other_ancillary = True
    if (
        other_ancillary
        or flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC)
        or not 1 <= len(frame) <= MAX_IDENTITY_FRAME
        or not frame.endswith(bytes((10,)))
        or frame.count(bytes((10,))) != 1
    ):
        raise AgentPeerDenied("invalid_or_truncated_identity_frame")
    credentials = []
    for level, kind, data in controls:
        if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS:
            if len(data) != PEER_SIZE:
                raise AgentPeerDenied("invalid_message_peer_credentials")
            credentials.append(KernelPeer(*struct.unpack("3i", data)))
        else:
            raise AgentPeerDenied("unexpected_unix_ancillary_data")
    if len(credentials) != 1 or credentials[0] != connected_peer:
        raise AgentPeerDenied("per_message_kernel_sender_mismatch")
    try:
        request = json.loads(frame.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise AgentPeerDenied("malformed_identity_request") from exc
    if (
        not isinstance(request, dict)
        or set(request) != {"op", "agent_id", "nonce"}
        or request.get("op") != "identity_preflight"
        or not isinstance(request.get("agent_id"), str)
        or not isinstance(request.get("nonce"), str)
        or not CLIENT_NONCE.fullmatch(request["nonce"])
    ):
        raise AgentPeerDenied("unexpected_identity_preflight_fields")
    return connected_peer, request


def _systemd_main(unit: str) -> dict[str, str]:
    if unit not in {binding.unit for binding in MANAGED_WORKERS}:
        raise AgentPeerDenied("unit_not_allowlisted")
    try:
        output = subprocess.run(
            ["systemctl", "show", unit, "-p", "Id", "-p", "MainPID",
             "-p", "ActiveState", "-p", "SubState", "-p", "User",
             "-p", "Group", "--no-pager"],
            capture_output=True, text=True, check=False, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AgentPeerDenied("systemd_identity_unavailable") from exc
    if output.returncode != 0:
        raise AgentPeerDenied("systemd_identity_unavailable")
    result: dict[str, str] = {}
    for line in output.stdout[:4096].splitlines():
        name, separator, value = line.partition("=")
        if separator and name in {
            "Id", "MainPID", "ActiveState", "SubState", "User", "Group",
        } and name not in result:
            result[name] = value.strip()
    return result


def _proc_start_ticks(pid: int, proc_root: Path) -> int:
    """Linux /proc/[pid]/stat field 22; safe against spaces in (comm)."""
    try:
        text = (proc_root / str(pid) / "stat").read_text(
            encoding="utf-8"
        )[:4096]
        marker = text.rfind(") ")
        if marker < 0:
            raise ValueError("invalid_stat_comm")
        fields = text[marker + 2:].split()  # starts at Linux stat field 3
        ticks = int(fields[19])  # Linux stat field 22
        if ticks <= 0:
            raise ValueError("invalid_starttime")
        return ticks
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        raise AgentPeerDenied("kernel_process_start_unavailable") from exc


def _proc_ids_and_cgroup(pid: int, proc_root: Path) -> tuple[int, int, str]:
    try:
        status = (proc_root / str(pid) / "status").read_text(
            encoding="utf-8"
        )[:16384]
        cgroup = (proc_root / str(pid) / "cgroup").read_text(
            encoding="utf-8"
        )[:16384]
        uid_match = re.search(r"^Uid:\s*(\d+)", status, re.MULTILINE)
        gid_match = re.search(r"^Gid:\s*(\d+)", status, re.MULTILINE)
        paths = [
            line.split("::", 1)[1]
            for line in cgroup.splitlines() if line.startswith("0::")
        ]
        if not uid_match or not gid_match or len(paths) != 1:
            raise ValueError("missing_proc_binding")
        return int(uid_match.group(1)), int(gid_match.group(1)), paths[0]
    except (OSError, UnicodeError, ValueError) as exc:
        raise AgentPeerDenied("kernel_process_identity_unavailable") from exc


def validate_managed_peer_binding(
    *,
    agent_id: str,
    peer: KernelPeer,
    unit_state: Mapping[str, str],
    proc_uid: int,
    proc_gid: int,
    cgroup: str,
    start_before: int,
    start_after: int,
    expected_uid: int,
    expected_gid: int,
) -> dict[str, object]:
    """Pure fail-closed policy over kernel/systemd facts supplied by ROOT.

    Never accept network/client claims as any of these trusted inputs.
    """
    mapping = {item.agent_id: item for item in MANAGED_WORKERS}
    spec: ExistingWorkerBinding | None = mapping.get(agent_id)
    if spec is None or not SYSTEM_UNIT.fullmatch(spec.unit):
        raise AgentPeerDenied("agent_not_in_existing_worker_allowlist")
    expected_cgroup = f"/system.slice/{spec.unit}"
    try:
        unit_main_pid = int(unit_state.get("MainPID", "0"))
    except (TypeError, ValueError) as exc:
        raise AgentPeerDenied("invalid_systemd_main_pid") from exc
    if (
        unit_state.get("Id") != spec.unit
        or unit_state.get("User") != spec.expected_user
        or unit_state.get("Group") != spec.expected_user
        or unit_state.get("ActiveState") != "activating"
        or unit_state.get("SubState") != "start"
        or unit_main_pid <= 1 or unit_main_pid != peer.pid
        or peer.uid != expected_uid or proc_uid != expected_uid
        or peer.gid != expected_gid or proc_gid != expected_gid
        or cgroup != expected_cgroup
        or start_before <= 0 or start_after != start_before
    ):
        raise AgentPeerDenied("managed_main_process_provenance_mismatch")
    return {
        "schema_version": "empire.agents.root_peer_scope.v1",
        "agent_id": spec.agent_id,
        "department": spec.department,
        "existing_role": spec.role,
        "allowed_component": spec.component,
        "unit": spec.unit,
        "process_origin_verified": True,
        "signing_key_issued": False,
        "trusted_broker_registration": False,
        "message_transport_activated": False,
        "queue_write_authority": False,
        "execution_authority": "none",
    }


def attest_connected_managed_worker(
    conn: socket.socket, *, agent_id: str | None = None,
    proc_root: Path = Path("/proc"),
    show: Callable[[str], Mapping[str, str]] = _systemd_main,
) -> dict[str, object]:
    """Call ONLY from the pre-existing root-owned privileged helper.

    Peer PID/UID/GID come from matching kernel SO_PEERCRED and current
    per-message SCM_CREDENTIALS, not from any untrusted caller JSON claim.
    A pidfd pins the task identity while /proc and systemd are checked.
    This function never signs or grants any action.
    """
    if os.geteuid() != 0:
        raise AgentPeerDenied("root_owned_helper_required")
    peer, request = _kernel_bound_request(conn)
    claimed_agent_id = request["agent_id"]
    if agent_id is not None and claimed_agent_id != agent_id:
        raise AgentPeerDenied("identity_preflight_agent_mismatch")
    spec = {item.agent_id: item for item in MANAGED_WORKERS}.get(claimed_agent_id)
    if spec is None:
        raise AgentPeerDenied("agent_not_in_existing_worker_allowlist")
    try:
        account = pwd.getpwnam(spec.expected_user)
    except KeyError as exc:
        raise AgentPeerDenied("expected_systemd_user_missing") from exc
    try:
        pidfd = os.pidfd_open(peer.pid, 0)
    except (OSError, AttributeError) as exc:
        raise AgentPeerDenied("kernel_pidfd_required") from exc
    try:
        first_ticks = _proc_start_ticks(peer.pid, proc_root)
        proc_uid, proc_gid, cgroup = _proc_ids_and_cgroup(
            peer.pid, proc_root,
        )
        unit_state = show(spec.unit)
        second_ticks = _proc_start_ticks(peer.pid, proc_root)
        return validate_managed_peer_binding(
            agent_id=claimed_agent_id, peer=peer,
            unit_state=unit_state,
            proc_uid=proc_uid, proc_gid=proc_gid, cgroup=cgroup,
            start_before=first_ticks, start_after=second_ticks,
            expected_uid=account.pw_uid, expected_gid=account.pw_gid,
        )
    finally:
        os.close(pidfd)
