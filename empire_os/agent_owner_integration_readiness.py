"""Read-only acceptance inventory for the ORIGINAL Agent & Tool Execution Plane.

Static source inspection is evidence of missing adoption, NOT proof of security
when a string or wrapper exists. Does not modify workers, leases, policy or
systemd; never promotes the private candidate to production authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
from typing import Any

ENTRY_POINTS = {
    "hermes": "empire_os/hermes_control.py",
    "pi": "empire_os/pi_sandbox_runner.py",
    "empire_coder_sandbox": "empire_os/empire_coder_sandbox_runner.py",
    "empire_coder_worker": "empire_os/coder/worker.py",
}
DIRECT_LEASE = re.compile(r"(?:lease_manager|manager|self\._execution_lease_manager\(\))\.acquire\s*\(")
REGISTER = "docs/handoffs/FOUNDER_WORKSTREAM_OWNER_REGISTER_DRAFT_20261027.json"


def _bounded_file(path: Path, limit: int) -> str | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _read_only_direct_write_inventory(root: Path) -> dict[str, Any]:
    """Record direct local filesystem bypass exposure without touching files.

    Does not claim to audit GitHub/connector credentials or systemd mount
    namespace restrictions; those must be accepted independently.
    """
    try:
        current_euid = os.geteuid()
    except OSError:
        current_euid = None
    entries = []
    candidates = (
        ("source_repository", root),
        ("git_history", root / ".git"),
        ("source_package", root / "empire_os"),
        ("runtime", root / "runtime"),
        ("lease_state_directory", root / "runtime/execution_plane"),
        ("lease_state_file", root / "runtime/execution_plane/leases.json"),
        ("owner_ticket_receipt", root / "runtime/execution_plane/.owner_ticket_consumption.json"),
    )
    for role, path in candidates:
        row: dict[str, Any] = {
            "role": role, "exists": False, "owner_uid": None,
            "mode_octal": None, "is_symlink": None,
            "current_process_can_write": None,
        }
        try:
            info = path.lstat()
            row.update({
                "exists": True, "owner_uid": info.st_uid,
                "mode_octal": oct(stat.S_IMODE(info.st_mode)),
                "is_symlink": stat.S_ISLNK(info.st_mode),
                "current_process_can_write": bool(os.access(
                    path, os.W_OK, effective_ids=True,
                )),
            })
        except (OSError, ValueError):
            pass
        entries.append(row)
    exposure = [x["role"] for x in entries if x["current_process_can_write"] is True]
    return {
        "current_effective_uid": current_euid,
        "inspected_roles": entries,
        "observed_direct_write_exposures": exposure,
        "direct_write_boundary_status": (
            "LOCAL_DIRECT_WRITE_BYPASS_OBSERVED" if exposure else
            "LOCAL_DIRECT_WRITE_BYPASS_NOT_OBSERVED_EXTERNAL_GATES_UNKNOWN"
        ),
        "external_git_and_plugin_authorization_verified": False,
        "method": "READ_ONLY_CURRENT_PROCESS_DAC_CHECK_NOT_SERVICE_NAMESPACE_ATTESTATION",
    }


def inspect_original_owner_integration(root: Path) -> dict[str, Any]:
    """Never return production enforcement=PASS from source scanning alone."""
    root = Path(root)
    rows = []
    for name, relpath in ENTRY_POINTS.items():
        raw = _bounded_file(root / relpath, 2_000_000)
        rows.append({
            "worker": name,
            "source_file": relpath,
            "readable_source": raw is not None,
            "original_direct_lease_call_observed": (
                bool(DIRECT_LEASE.search(raw)) if raw is not None else None
            ),
            "signed_owner_adapter_reference_observed": (
                "acquire_owner_authorized_lease(" in raw if raw is not None else False
            ),
            "independent_owner_approval_verified": False,
        })
    draft_raw = _bounded_file(root / REGISTER, 80_000)
    approved_count = None
    verified_principals = None
    draft_safe = False
    if draft_raw is not None:
        try:
            draft = json.loads(draft_raw)
            rows_draft = draft.get("candidate_assignments")
            if (
                draft.get("schema_version")
                == "empire.execution.owner_register_review_draft.v1"
                and isinstance(rows_draft, list) and len(rows_draft) <= 50
            ):
                approved_count = sum(x.get("approved") is True for x in rows_draft if isinstance(x, dict))
                verified_principals = sum(
                    bool(x.get("authenticated_principal"))
                    for x in rows_draft if isinstance(x, dict)
                )
                draft_safe = draft.get("policy_signed") is False and draft.get("production_enforcement_enabled") is False
        except (ValueError, AttributeError, TypeError):
            pass
    missing = [x["worker"] for x in rows if not x["readable_source"]]
    direct = [x["worker"] for x in rows if x["original_direct_lease_call_observed"] is True]
    return {
        "schema_version": "empire.execution.owner_integration_readiness.v1",
        "status": "ORIGINAL_OWNER_INTEGRATION_HOLD",
        "mode": "READ_ONLY_STATIC_ADOPTION_CHECK",
        "worker_entry_points": rows,
        "direct_write_custody_audit": _read_only_direct_write_inventory(root),
        "unreadable_worker_sources": missing,
        "direct_lease_entry_points": direct,
        "founder_draft_present_unapproved": draft_safe,
        "draft_approved_owner_count": approved_count,
        "draft_authenticated_principal_count": verified_principals,
        "sealed_policy_verified": False,
        "trusted_worker_identity_binding_verified": False,
        "ticket_replay_protection_verified": False,
        "direct_shell_plugin_write_boundary_verified": False,
        "production_enforcement_verified": False,
        "production_write_performed": False,
        "agent_reassigned": False,
        "new_timer_created": False,
        "next_action": "ORIGINAL_EXECUTION_OWNER_REVIEW_AND_ATTEST_BEFORE_GUARDED_RELEASE",
    }
