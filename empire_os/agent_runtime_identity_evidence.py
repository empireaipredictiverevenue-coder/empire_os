"""Read-only OS evidence for binding EXISTING managed workers to Agent OS.

Never issues credentials, registers an agent, runs models, or makes live task
claims. Process evidence is NOT proof of a dedicated per-agent signing key.
Only canonical systemd units explicitly inventoried here can be observed.
"""
from __future__ import annotations

import os
import pwd
import re
import hashlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.departments import default_departments


@dataclass(frozen=True)
class ExistingWorkerBinding:
    agent_id: str
    unit: str
    department: str
    role: str
    component: str
    expected_user: str = "ubuntu"


@dataclass(frozen=True)
class ManagedWorkerSigningIdentity:
    """Private Ed25519 signer provided by trusted worker bootstrap only.

    Never serialize, log, register automatically or share with peer workers.
    """

    profile: Any
    private_key: Ed25519PrivateKey

    def sign(self, envelope: Mapping[str, Any]) -> str:
        from empire_os.department_collaboration import _canonical
        return self.private_key.sign(_canonical(envelope)).hex()

    def public_key(self):
        return self.private_key.public_key()


# These are workload candidates, not dynamically minted authenticated agents.
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
# JEV/TypeSafe is a provider binding; no separate local agent process is
# proven. Laya is an inference sidecar, not a department work-claim agent.
# Research agent workers need a separately verified managed process/identity.


def _fields(stdout: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {
            "Id", "ActiveState", "SubState", "MainPID", "User",
        } and key not in result:
            result[key] = value.strip()
    return result


def systemd_show(unit: str) -> Mapping[str, str]:
    """Bounded read of a *pinned* unit; never accept arbitrary user unit text."""
    if unit not in {spec.unit for spec in MANAGED_WORKERS}:
        return {}
    try:
        completed = subprocess.run(
            ["systemctl", "show", unit,
             "-p", "Id", "-p", "ActiveState", "-p", "SubState",
             "-p", "MainPID", "-p", "User", "--no-pager"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if completed.returncode:
        return {}
    return _fields(completed.stdout[:8192])


def proc_identity(pid: int, proc_root: Path = Path("/proc")) -> tuple[int | None, str]:
    """Inspect Linux kernel process credentials/cgroup, never cmdline/env."""
    if pid <= 0:
        return None, ""
    status_path = proc_root / str(pid) / "status"
    cgroup_path = proc_root / str(pid) / "cgroup"
    try:
        status = status_path.read_text(encoding="utf-8")[:16384]
        cgroups = cgroup_path.read_text(encoding="utf-8")[:16384]
    except (OSError, UnicodeError):
        return None, ""
    match = re.search(r"^Uid:\s*(\d+)", status, re.MULTILINE)
    uid = int(match.group(1)) if match else None
    paths = [line.split("::", 1)[1] for line in cgroups.splitlines()
             if line.startswith("0::")]
    return uid, paths[0] if paths else ""


def inspect_existing_worker(
    binding: ExistingWorkerBinding,
    *,
    show: Callable[[str], Mapping[str, str]] = systemd_show,
    proc: Callable[[int], tuple[int | None, str]] = proc_identity,
    get_uid: Callable[[str], int] | None = None,
) -> dict[str, Any]:
    """Return process provenance, never authentication or execution authority."""
    inventory = {spec.agent_id: spec for spec in MANAGED_WORKERS}
    if inventory.get(binding.agent_id) != binding:
        raise ValueError("unregistered_existing_worker_binding")
    catalog = {spec.key: spec for spec in default_departments()}
    department = catalog.get(binding.department)
    if (
        department is None or binding.role not in department.agent_roles
        or binding.component not in department.components
    ):
        raise ValueError("existing_department_role_capability_mismatch")
    data = dict(show(binding.unit))
    if data.get("Id") != binding.unit:
        data = {}
    try:
        pid = int(data.get("MainPID", "0"))
    except (ValueError, TypeError):
        pid = 0
    if pid < 1 or pid > 2**31:
        pid = 0
    try:
        expected_uid = (
            get_uid(binding.expected_user) if get_uid is not None
            else pwd.getpwnam(binding.expected_user).pw_uid
        )
    except (KeyError, ValueError, OSError):
        expected_uid = -1
    uid, cgroup = proc(pid) if pid else (None, "")
    valid_cgroup = (
        cgroup == f"/system.slice/{binding.unit}"
        or cgroup.startswith(f"/system.slice/{binding.unit}/")
    )
    service_active = data.get("ActiveState") == "active"
    # oneshot unit's MainPID disappears; do not infer a durable principal.
    observed = (
        service_active and pid > 0
        and data.get("User") == binding.expected_user
        and uid == expected_uid
        and expected_uid >= 0 and valid_cgroup
    )
    return {
        **asdict(binding),
        "unit_active": service_active,
        "main_pid_observed": pid > 0,
        "process_uid_verified": uid == expected_uid and expected_uid >= 0,
        "process_unit_cgroup_verified": valid_cgroup,
        "managed_process_evidence": observed,
        "dedicated_agent_key_verified": False,
        "authenticated_collaboration_activated": False,
        "tenant_identity_bound": False,
        "execution_authority": "none",
    }


def preflight_local_managed_binding(
    credential: object,
    *,
    agent_id: str,
    show: Callable[[str], Mapping[str, str]] = systemd_show,
    proc: Callable[[int], tuple[int | None, str]] = proc_identity,
    get_uid: Callable[[str], int] | None = None,
    process_pid: int | None = None,
) -> dict[str, Any]:
    """Check a credential-bearing *current service main process*, fail closed.

    Called INSIDE the existing workload by a privileged trusted bootstrap.
    Its OS evidence cannot register a key in the trusted broker by itself.
    Never expose as HTTP, and never use a caller-provided PID in production.
    """
    from empire_os.department_collaboration import AgentCredential, validate_profile
    mapping = {entry.agent_id: entry for entry in MANAGED_WORKERS}
    entry = mapping.get(agent_id)
    if entry is None or not isinstance(
        credential, (AgentCredential, ManagedWorkerSigningIdentity)
    ):
        raise ValueError("managed_credential_binding_not_registered")
    profile = credential.profile
    validate_profile(profile)
    if (
        profile.agent_id != entry.agent_id
        or profile.department != entry.department
        or profile.role != entry.role
        or profile.tenant_id is not None
        or profile.allowed_components != (entry.component,)
    ):
        raise ValueError("managed_role_or_key_scope_mismatch")
    if isinstance(credential, AgentCredential):
        if len(credential.key) < 32:
            raise ValueError("managed_role_or_key_scope_mismatch")
    elif not isinstance(credential.private_key, Ed25519PrivateKey):
        raise ValueError("managed_role_or_key_scope_mismatch")
    data = dict(show(entry.unit))
    evidence = inspect_existing_worker(
        entry, show=lambda _: data, proc=proc, get_uid=get_uid,
    )
    try:
        main_pid = int(data.get("MainPID", "0"))
    except (TypeError, ValueError):
        main_pid = 0
    actual_pid = os.getpid() if process_pid is None else process_pid
    if (
        not evidence["managed_process_evidence"]
        or main_pid < 1 or main_pid != actual_pid
    ):
        raise ValueError("current_managed_process_identity_not_attested")
    signer_metadata = {"signing_mode": "legacy_hmac"}
    if isinstance(credential, ManagedWorkerSigningIdentity):
        public = credential.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        signer_metadata = {
            "signing_mode": "ed25519_private_in_managed_process",
            "public_key_sha256": hashlib.sha256(public).hexdigest(),
        }
    return {
        "agent_id": entry.agent_id,
        "unit": entry.unit,
        "local_process_scope_attested": True,
        "credential_shape_checked": True,
        "trusted_broker_key_registration_still_required": True,
        "execution_authority": "none",
        **signer_metadata,
    }


def inspect_agent_team() -> dict[str, Any]:
    workers = [inspect_existing_worker(spec) for spec in MANAGED_WORKERS]
    return {
        "schema_version": "empire.existing_agent_runtime_identity.v1",
        "managed_worker_candidates": workers,
        "managed_process_evidence_count": sum(
            int(item["managed_process_evidence"]) for item in workers
        ),
        "authenticated_agent_count": 0,
        "service_unit_is_not_agent_credential": True,
        "other_runtime_holds": {
            "jev": "model_provider_not_independent_agent_process",
            "research": "managed_worker_identity_not_verified",
            "hermes": "not_activated_as_department_agent",
            "laya": "model_sidecar_not_department_task_agent",
        },
        "communication_activated": False,
        "execution_authority": "none",
    }
